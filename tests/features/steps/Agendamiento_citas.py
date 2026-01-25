"""
Steps para la característica de Agendamiento de citas migratorias.
Implementa los pasos BDD para los escenarios de agendamiento.
"""
from behave import step
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from datetime import timedelta, time

from migration.models import Agente, Cita, Solicitante, HORA_INICIO_ATENCION
from migration.services.scheduling import agendar_cita, SolicitudAgendamiento
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================

def obtener_proximo_dia_laboral():
    """
    Obtiene el próximo día laboral (lunes a sábado) a partir de mañana.
    Evita usar el día actual para evitar problemas con fechas pasadas.
    """
    fecha = dj_timezone.localtime(dj_timezone.now()).date() + timedelta(days=1)

    # Si cae domingo, avanzar al lunes
    while fecha.weekday() == 6:  # 6 = domingo
        fecha += timedelta(days=1)

    return fecha


def crear_horario_valido(hora=9):
    """
    Crea un horario válido para agendar citas.

    Args:
        hora: Hora del día (entre 8 y 11).

    Returns:
        DateTime con zona horaria para el próximo día laboral.
    """
    fecha_laboral = obtener_proximo_dia_laboral()
    horario_naive = dj_timezone.datetime.combine(fecha_laboral, time(hora, 0))
    return dj_timezone.make_aware(horario_naive)


def crear_solicitante():
    """
    Crea un nuevo solicitante con datos aleatorios.

    Returns:
        Instancia de Solicitante guardada en la base de datos.
    """
    return Solicitante.objects.create(
        nombre=faker.name(),
        telefono=faker.phone_number(),
        email=faker.email()
    )


def obtener_o_crear_agentes():
    """
    Asegura que existan agentes activos en el sistema.

    Returns:
        QuerySet de agentes activos.
    """
    Agente.objects.get_or_create(nombre="Agente A", defaults={"activo": True})
    Agente.objects.get_or_create(nombre="Agente B", defaults={"activo": True})
    return Agente.objects.filter(activo=True)


# ==================== Escenario 1: Agendamiento exitoso ====================

@step("que el solicitante no tiene una cita")
def paso_solicitante_sin_cita(context):
    """Prepara un solicitante sin citas pendientes."""
    context.solicitante = crear_solicitante()

    # Verificar que no tenga citas pendientes
    tiene_pendiente = context.solicitante.tiene_cita_pendiente()
    assert not tiene_pendiente, "El solicitante no debería tener citas pendientes"


@step("el solicitante selecciona un horario")
def paso_seleccionar_horario(context):
    """El solicitante selecciona un horario válido para la cita."""
    context.inicio = crear_horario_valido(hora=HORA_INICIO_ATENCION + 1)  # 9:00

    # Asegurar que existan agentes
    agentes = obtener_o_crear_agentes()
    assert agentes.count() >= 1, "Debe existir al menos un agente activo"


@step("el sistema agenda la cita con un agente disponible en dicho horario")
def paso_agendar_cita(context):
    """El sistema asigna la cita a un agente disponible."""
    solicitud = SolicitudAgendamiento(
        solicitante=context.solicitante,
        inicio=context.inicio
    )
    context.cita = agendar_cita(solicitud)

    # Verificar que se asignó un agente
    assert context.cita.agente is not None, "La cita debe tener un agente asignado"

    # Verificar que el agente no tenga otra cita en el mismo horario
    citas_mismo_horario = Cita.objects.filter(
        agente=context.cita.agente,
        inicio=context.inicio,
        estado=Cita.ESTADO_PENDIENTE
    ).exclude(pk=context.cita.pk)

    assert not citas_mismo_horario.exists(), (
        "El agente no debe tener otra cita en el mismo horario"
    )


@step("la cita queda pendiente para su resolución")
def paso_verificar_cita_pendiente(context):
    """Verifica que la cita esté correctamente agendada."""
    cita = context.cita

    # Verificar estado pendiente
    assert cita.estado == Cita.ESTADO_PENDIENTE, "La cita debe estar pendiente"

    # Verificar que el fin se calculó automáticamente (inicio + 1 hora)
    duracion_esperada = timedelta(hours=1)
    duracion_real = cita.fin - cita.inicio
    assert duracion_real == duracion_esperada, (
        f"La duración debe ser 1 hora, pero es {duracion_real}"
    )

    # Verificar horario de atención (8:00 - 11:59)
    hora_inicio = dj_timezone.localtime(cita.inicio).hour
    assert 8 <= hora_inicio < 12, (
        f"La hora de inicio debe estar entre 8:00 y 11:59, pero es {hora_inicio}:00"
    )


# ==================== Escenario 2: Intento con cita existente ====================

@step("que el solicitante ya tiene una cita pendiente")
def paso_solicitante_con_cita_pendiente(context):
    """Prepara un solicitante que ya tiene una cita pendiente."""
    context.solicitante = crear_solicitante()
    agentes = obtener_o_crear_agentes()
    agente = agentes.first()

    # Crear una cita pendiente para el solicitante
    inicio_cita_existente = crear_horario_valido(hora=10)
    context.cita_existente = Cita(
        solicitante=context.solicitante,
        agente=agente,
        inicio=inicio_cita_existente,
        estado=Cita.ESTADO_PENDIENTE
    )
    context.cita_existente.save()

    # Verificar que la cita pendiente existe
    assert context.solicitante.tiene_cita_pendiente(), (
        "El solicitante debe tener una cita pendiente"
    )


@step("intenta agendar una nueva cita")
def paso_intentar_nueva_cita(context):
    """El solicitante intenta agendar una segunda cita."""
    context.error = None

    try:
        # Intentar agendar en un horario diferente
        nuevo_inicio = crear_horario_valido(hora=11)
        solicitud = SolicitudAgendamiento(
            solicitante=context.solicitante,
            inicio=nuevo_inicio
        )
        agendar_cita(solicitud)
    except DjValidationError as error:
        context.error = error


@step("el sistema rechaza el agendamiento")
def paso_verificar_rechazo(context):
    """Verifica que el sistema rechazó la solicitud."""
    assert context.error is not None, (
        "El sistema debería haber rechazado el agendamiento"
    )


@step("se le notifica que debe cancelar una cita antes de agendar una nueva")
def paso_verificar_mensaje_error(context):
    """Verifica que se muestre el mensaje de error apropiado."""
    mensaje_error = str(context.error)

    palabras_clave = ["ya tiene una cita pendiente", "cancelar"]
    contiene_mensaje = any(
        palabra.lower() in mensaje_error.lower()
        for palabra in palabras_clave
    )

    assert contiene_mensaje, (
        f"El mensaje debe indicar que ya tiene cita pendiente. "
        f"Mensaje recibido: {mensaje_error}"
    )
