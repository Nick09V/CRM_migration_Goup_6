"""
Steps para la característica de Reprogramación de citas migratorias.
Implementa los pasos BDD para los escenarios de reprogramación.
"""
from behave import given, when, step
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from datetime import timedelta, time

from migration.models import Agente, Cita, Solicitante
from migration.services.scheduling import (
    reprogramar_cita,
    calcular_dias_restantes,
    DIAS_MINIMOS_REPROGRAMACION,
)
from faker import Faker


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


def crear_horario_con_anticipacion(dias_anticipacion: int, hora: int = 9) -> dj_timezone.datetime:
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


def crear_solicitante() -> Solicitante:
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


def obtener_o_crear_agente() -> Agente:
    """
    Asegura que exista un agente activo en el sistema.

    Returns:
        Instancia de Agente.
    """
    agente, _ = Agente.objects.get_or_create(
        nombre="Agente Reprogramaciones",
        defaults={"activo": True}
    )
    return agente


def crear_cita_pendiente(dias_anticipacion: int, hora: int = 9) -> Cita:
    """
    Crea una cita pendiente con la anticipación especificada.

    Args:
        dias_anticipacion: Número de días desde hoy para la cita.
        hora: Hora del día para la cita.

    Returns:
        Instancia de Cita pendiente.
    """
    solicitante = crear_solicitante()
    agente = obtener_o_crear_agente()
    horario = crear_horario_con_anticipacion(dias_anticipacion, hora)

    cita = Cita(
        solicitante=solicitante,
        agente=agente,
        inicio=horario,
        estado=Cita.ESTADO_PENDIENTE,
    )
    cita.save()
    return cita


# ==================== Escenario 1: Reprogramación exitosa ====================


@given("que el solicitante tiene una cita pendiente")
def paso_solicitante_tiene_cita_pendiente(context):
    """Prepara un solicitante con una cita pendiente con suficiente anticipación."""
    # Crear cita con 5 días de anticipación (más de los 3 requeridos)
    context.cita = crear_cita_pendiente(dias_anticipacion=5)
    context.solicitante = context.cita.solicitante
    context.agente_original = context.cita.agente
    context.horario_original = context.cita.inicio


@step("faltan más de dos días para la cita")
def paso_faltan_mas_de_dos_dias(context):
    """Verifica que faltan más de 2 días para la cita (ya configurado en paso anterior)."""
    dias_restantes = calcular_dias_restantes(context.cita)
    assert dias_restantes > 2, (
        f"La cita debe tener más de 2 días de anticipación. "
        f"Días restantes: {dias_restantes}"
    )


@step("el solicitante selecciona un nuevo horario disponible")
def paso_solicitante_selecciona_horario(context):
    """El solicitante selecciona un nuevo horario para reprogramar."""
    # Seleccionar un nuevo horario diferente (6 días de anticipación, hora diferente)
    context.nuevo_horario = crear_horario_con_anticipacion(dias_anticipacion=6, hora=10)

    try:
        context.resultado = reprogramar_cita(context.cita, context.nuevo_horario)
        context.error = None
    except DjValidationError as e:
        context.resultado = None
        context.error = e


@step("el sistema actualiza la fecha y hora de la cita")
def paso_sistema_actualiza_cita(context):
    """Verifica que la cita fue actualizada correctamente."""
    assert context.error is None, f"Error inesperado: {context.error}"
    assert context.resultado is not None, "No se obtuvo resultado de reprogramación"
    assert context.resultado.exitoso is True, "La reprogramación debió ser exitosa"

    # Refrescar la cita desde la base de datos
    cita_actualizada = Cita.objects.get(pk=context.cita.pk)

    assert cita_actualizada.inicio == context.nuevo_horario, (
        f"El horario de la cita debió actualizarse. "
        f"Esperado: {context.nuevo_horario}, Actual: {cita_actualizada.inicio}"
    )
    assert cita_actualizada.estado == Cita.ESTADO_PENDIENTE, (
        "La cita debe mantener su estado pendiente después de reprogramar"
    )


@step("el horario del agente anterior queda disponible para otro agendamiento")
def paso_horario_agente_disponible(context):
    """Verifica que el horario anterior quedó liberado."""
    # Verificar que no existe ninguna cita pendiente en el horario original
    citas_en_horario_original = Cita.objects.filter(
        inicio=context.horario_original,
        estado=Cita.ESTADO_PENDIENTE
    ).count()

    assert citas_en_horario_original == 0, (
        f"El horario original debería estar disponible. "
        f"Se encontraron {citas_en_horario_original} citas en ese horario."
    )


# ==================== Escenario 2: Reprogramación fuera del tiempo ====================


@given("que faltan dos días para la cita")
def paso_faltan_dos_dias(context):
    """Prepara una cita que tiene exactamente 2 días de anticipación."""
    context.cita = crear_cita_pendiente(dias_anticipacion=2)
    context.solicitante = context.cita.solicitante

    dias_restantes = calcular_dias_restantes(context.cita)
    assert dias_restantes == 2, (
        f"La cita debe tener exactamente 2 días de anticipación. "
        f"Días restantes: {dias_restantes}"
    )


@step("el solicitante intenta reprogramar la cita")
def paso_solicitante_intenta_reprogramar(context):
    """Intenta reprogramar la cita cuando no hay suficiente anticipación."""
    nuevo_horario = crear_horario_con_anticipacion(dias_anticipacion=7, hora=10)

    try:
        context.resultado = reprogramar_cita(context.cita, nuevo_horario)
        context.error = None
    except DjValidationError as e:
        context.resultado = None
        context.error = e


@step("el sistema rechaza la reprogramación")
def paso_sistema_rechaza_reprogramacion(context):
    """Verifica que el sistema rechazó la reprogramación."""
    assert context.error is not None, (
        "El sistema debió rechazar la reprogramación con un error de validación"
    )
    assert context.resultado is None, "No debió haber resultado exitoso"

    # Verificar que la cita original no fue modificada
    cita_sin_cambios = Cita.objects.get(pk=context.cita.pk)
    assert cita_sin_cambios.inicio == context.cita.inicio, (
        "La cita no debió ser modificada al rechazar la reprogramación"
    )


@step("se notifica que no se pudo hacer el reagendamiento")
def paso_notifica_error_reprogramacion(context):
    """Verifica que se notifica correctamente el error de reprogramación."""
    assert context.error is not None, "Debió haber un error de validación"

    mensaje_error = str(context.error.message)
    assert "reprogramar" in mensaje_error.lower(), (
        f"El mensaje de error debe mencionar la reprogramación. "
        f"Mensaje recibido: {mensaje_error}"
    )
    assert str(DIAS_MINIMOS_REPROGRAMACION) in mensaje_error, (
        f"El mensaje debe mencionar los días mínimos de anticipación. "
        f"Mensaje recibido: {mensaje_error}"
    )

