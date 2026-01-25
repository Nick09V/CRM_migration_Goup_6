"""
Steps para la característica de Cancelación de citas migratorias.
Implementa los pasos BDD para los escenarios de cancelación.
"""
from behave import step
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from datetime import timedelta, time

from migration.models import Agente, Cita, Solicitante
from migration.services.scheduling import (
    cancelar_cita,
    DIAS_MINIMOS_CANCELACION,
)
from faker import Faker

use_step_matcher("re")
faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================

def obtener_dia_laboral_con_anticipacion(dias_anticipacion: int):
    """
    Obtiene un día laboral con la anticipación especificada.

    Args:
        dias_anticipacion: Número de días desde hoy.

    Returns:
        Fecha del día laboral.
    """
    fecha = dj_timezone.localtime(dj_timezone.now()).date() + timedelta(days=dias_anticipacion)

    # Si cae domingo, avanzar al lunes
    while fecha.weekday() == 6:  # 6 = domingo
        fecha += timedelta(days=1)

    return fecha


def crear_horario_con_anticipacion(dias_anticipacion: int, hora: int = 9):
    """
    Crea un horario válido para una cita con anticipación específica.

    Args:
        dias_anticipacion: Número de días desde hoy.
        hora: Hora del día (entre 8 y 11).

    Returns:
        DateTime con zona horaria.
    """
    fecha_laboral = obtener_dia_laboral_con_anticipacion(dias_anticipacion)
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


def obtener_o_crear_agente():
    """
    Asegura que exista un agente activo en el sistema.

    Returns:
        Instancia de Agente.
    """
    agente, _ = Agente.objects.get_or_create(
        nombre="Agente Cancelaciones",
        defaults={"activo": True}
    )
    return agente


# ==================== Antecedentes ====================

@step("que el solicitante tiene una cita pendiente")
def paso_solicitante_tiene_cita_pendiente(context):
    """Prepara un solicitante con una cita pendiente."""
    context.solicitante = crear_solicitante()
    context.agente = obtener_o_crear_agente()

    # Crear cita con suficiente anticipación (7 días)
    context.inicio_cita = crear_horario_con_anticipacion(dias_anticipacion=7, hora=9)

    context.cita = Cita(
        solicitante=context.solicitante,
        agente=context.agente,
        inicio=context.inicio_cita,
        estado=Cita.ESTADO_PENDIENTE
    )
    context.cita.save()

    # Verificar que la cita fue creada correctamente
    assert context.solicitante.tiene_cita_pendiente(), (
        "El solicitante debe tener una cita pendiente"
    )


# ==================== Escenario 1: Cancelación exitosa ====================

@step("solicita cancelar la cita")
def paso_solicita_cancelar_cita(context):
    """El solicitante solicita cancelar su cita."""
    context.error = None
    context.resultado = None

    try:
        context.resultado = cancelar_cita(context.cita)
    except DjValidationError as error:
        context.error = error


@step("el sistema elimina la cita")
def paso_sistema_elimina_cita(context):
    """Verifica que el sistema eliminó la cita."""
    assert context.error is None, (
        f"No debería haber error al cancelar: {context.error}"
    )
    assert context.resultado is not None, "Debe existir un resultado de cancelación"
    assert context.resultado.exitoso, "La cancelación debe ser exitosa"


@step("el solicitante queda sin cita asignada")
def paso_solicitante_sin_cita(context):
    """Verifica que el solicitante ya no tiene citas pendientes."""
    # Refrescar el solicitante desde la base de datos
    context.solicitante.refresh_from_db()

    tiene_cita = context.solicitante.tiene_cita_pendiente()
    assert not tiene_cita, "El solicitante no debe tener citas pendientes"


@step("el horario del agente queda disponible para otro agendamiento")
def paso_horario_disponible(context):
    """Verifica que el horario del agente quedó libre."""
    # Verificar que no existe cita pendiente para el agente en ese horario
    cita_existente = Cita.objects.filter(
        agente=context.agente,
        inicio=context.inicio_cita,
        estado=Cita.ESTADO_PENDIENTE
    ).exists()

    assert not cita_existente, (
        "El horario del agente debe estar disponible para otro agendamiento"
    )


# ==================== Escenario 2: Cancelación fuera del tiempo permitido ====================

@step("que faltan dos días para la cita")
def paso_faltan_dos_dias(context):
    """Modifica la cita para que falten solo 2 días."""
    # Calcular nueva fecha con solo 2 días de anticipación
    context.inicio_cita = crear_horario_con_anticipacion(dias_anticipacion=2, hora=10)

    # Usar update() para evitar las validaciones del modelo
    # Esto simula una cita que fue agendada hace tiempo y ahora está próxima
    Cita.objects.filter(pk=context.cita.pk).update(
        inicio=context.inicio_cita,
        fin=context.inicio_cita + timedelta(hours=1)
    )

    # Refrescar la instancia desde la base de datos
    context.cita.refresh_from_db()

    # Verificar los días restantes
    ahora = dj_timezone.localtime(dj_timezone.now()).date()
    fecha_cita = dj_timezone.localtime(context.cita.inicio).date()
    dias_restantes = (fecha_cita - ahora).days

    assert dias_restantes < DIAS_MINIMOS_CANCELACION, (
        f"Deben faltar menos de {DIAS_MINIMOS_CANCELACION} días, "
        f"pero faltan {dias_restantes}"
    )


@step("intenta cancelar la cita")
def paso_intenta_cancelar(context):
    """El solicitante intenta cancelar su cita."""
    context.error = None
    context.resultado = None

    try:
        context.resultado = cancelar_cita(context.cita)
    except DjValidationError as error:
        context.error = error


@step("el sistema rechaza la cancelación")
def paso_sistema_rechaza_cancelacion(context):
    """Verifica que el sistema rechazó la cancelación."""
    assert context.error is not None, (
        "El sistema debería haber rechazado la cancelación"
    )

    # Verificar que la cita sigue existiendo
    cita_existe = Cita.objects.filter(pk=context.cita.pk).exists()
    assert cita_existe, "La cita debe seguir existiendo después del rechazo"


@step("notifica al solicitante la restricción")
def paso_notifica_restriccion(context):
    """Verifica que se notificó la restricción al solicitante."""
    mensaje_error = str(context.error)

    palabras_clave = ["días", "anticipación", "cancelar"]
    contiene_mensaje = any(
        palabra.lower() in mensaje_error.lower()
        for palabra in palabras_clave
    )

    assert contiene_mensaje, (
        f"El mensaje debe indicar la restricción de tiempo. "
        f"Mensaje recibido: {mensaje_error}"
    )
