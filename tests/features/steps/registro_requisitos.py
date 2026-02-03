from behave import given, when, then, step
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from datetime import time

from migration.models import (
    Solicitante,
    Agente,
    Cita,
    ESTADO_DOCUMENTO_FALTANTE,
    EstadoDocumento
)
from migration.services.requisitos import (
    registrar_tipo_visa,
    asignar_requisitos,
    verificar_requisitos_pendientes,
    marcar_cita_exitosa,
)
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================


def crear_solicitante() -> Solicitante:
    return Solicitante.objects.create(
        nombre=faker.unique.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email()
    )


def obtener_o_crear_agente() -> Agente:
    agente, _ = Agente.objects.get_or_create(
        nombre="Agente Requisitos",
        defaults={"activo": True}
    )
    return agente


def crear_horario_hoy(hora: int = 9) -> dj_timezone.datetime:
    hoy = dj_timezone.localtime(dj_timezone.now()).date()
    horario_naive = dj_timezone.datetime.combine(hoy, time(hora, 0))
    return dj_timezone.make_aware(horario_naive)


def crear_cita_pendiente_hoy() -> Cita:
    solicitante = crear_solicitante()
    agente = obtener_o_crear_agente()
    horario = crear_horario_hoy(hora=9)

    # Crear la cita sin validación de rango de fechas para pruebas
    cita = Cita(
        solicitante=solicitante,
        agente=agente,
        inicio=horario,
        estado=Cita.ESTADO_PENDIENTE,
    )
    # Guardar sin full_clean para evitar validaciones de fecha pasada en tests
    cita.fin = cita._calcular_fin()
    super(Cita, cita).save()
    return cita


def parsear_lista_requisitos(requisitos_str: str) -> list[str]:
    return [req.strip() for req in requisitos_str.split(",") if req.strip()]


# ==================== Escenario: Registro de requisitos migratorios ====================


@given("que se tiene una cita pendiente")
def paso_tiene_cita_pendiente(context):
    """Prepara un solicitante con una cita pendiente para hoy."""
    context.cita = crear_cita_pendiente_hoy()
    context.solicitante = context.cita.solicitante
    context.agente = context.cita.agente

    # Verificar que la cita está pendiente
    assert context.cita.estado == Cita.ESTADO_PENDIENTE, (
        f"La cita debe estar pendiente, pero está en estado '{context.cita.estado}'"
    )

    # Verificar que la cita es para hoy
    assert context.cita.es_fecha_cita_hoy(), (
        "La cita debe estar programada para hoy"
    )


@step("que el agente ha registrado que el cliente necesita la visa {tipo_visa}")
def paso_agente_registra_tipo_visa(context, tipo_visa: str):
    """El agente registra el tipo de visa que necesita el cliente."""
    context.tipo_visa = tipo_visa.strip()

    # Si no existe solicitante, crearlo con cita
    if not hasattr(context, 'solicitante') or context.solicitante is None:
        context.cita = crear_cita_pendiente_hoy()
        context.solicitante = context.cita.solicitante

    # Registrar el tipo de visa para el solicitante
    registrar_tipo_visa(context.solicitante, context.tipo_visa)

    # Verificar que el tipo de visa fue asignado
    context.solicitante.refresh_from_db()
    assert context.solicitante.tipo_visa == context.tipo_visa, (
        f"El tipo de visa debe ser '{context.tipo_visa}', "
        f"pero es '{context.solicitante.tipo_visa}'"
    )


@step("se tienen los siguientes requisitos cargados")
def paso_requisitos_cargados(context):
    """Carga la lista global de requisitos disponibles en el sistema."""
    context.requisitos_cargados = []

    for row in context.table:
        requisito = row["requisitos_cargado"].strip()
        context.requisitos_cargados.append(requisito)

    assert len(context.requisitos_cargados) == 8


@then('el agente asigna los siguientes requisitos al cliente "{requisitos}"')
def paso_asignar_requisitos(context, requisitos: str):
    """El agente asigna los requisitos correspondientes al tipo de visa."""
    context.error = None

    # Parsear los requisitos esperados
    requisitos_esperados = parsear_lista_requisitos(requisitos)

    # Obtener requisitos cargados
    requisitos_cargados = getattr(context, 'requisitos_cargados', None)

    try:
        # Asignar los requisitos específicos al solicitante
        resultado = asignar_requisitos(
            solicitante=context.solicitante,
            requisitos_a_asignar=requisitos_esperados,
            requisitos_cargados=requisitos_cargados,
            validar_fecha=True
        )
    except DjValidationError as e:
        context.error = e
        raise AssertionError(f"Error al asignar requisitos: {e}")

    assert resultado.exitoso, f"Error al asignar requisitos: {resultado.mensaje}"
    assert resultado.requisitos is not None, "No se crearon requisitos"

    # Obtener los requisitos asignados
    requisitos_asignados = [r.nombre for r in resultado.requisitos]

    # Verificar que se asignaron los requisitos correctos
    assert len(requisitos_asignados) == len(requisitos_esperados), (
        f"Se esperaban {len(requisitos_esperados)} requisitos, "
        f"pero se asignaron {len(requisitos_asignados)}"
    )

    for req_esperado in requisitos_esperados:
        assert req_esperado in requisitos_asignados, (
            f"El requisito '{req_esperado}' no fue asignado. "
            f"Requisitos asignados: {requisitos_asignados}"
        )

    context.requisitos = resultado.requisitos


@then("los documentos quedan como pendientes por subir")
def paso_documentos_pendientes(context):
    """Los documentos quedan como pendientes por subir (estado faltante)."""
    # Verificar que todos los requisitos están pendientes
    todos_pendientes = verificar_requisitos_pendientes(context.solicitante)
    assert todos_pendientes, "Todos los requisitos deben estar pendientes por subir"

    # Verificar estado individual de cada requisito
    for requisito in context.requisitos:
        requisito.refresh_from_db()
        assert requisito.esta_pendiente_de_subir(), (
            f"El requisito {requisito.nombre} debe estar en estado pendiente por subir"
        )
        assert requisito.carga_habilitada, (
            f"La carga del requisito '{requisito.nombre}' debe estar habilitada"
        )


@then("la cita se marca como exitosa")
def paso_cita_exitosa(context):
    """La cita se marca como exitosa tras asignar los requisitos."""
    try:
        cita = marcar_cita_exitosa(context.solicitante)
        context.cita = cita
    except DjValidationError:
        # Si la cita ya fue marcada como exitosa, verificar el estado
        context.cita.refresh_from_db()

    # Verificar que la cita está en estado exitosa
    context.cita.refresh_from_db()
    assert context.cita.estado == Cita.ESTADO_EXITOSA, (
        f"La cita debe estar en estado 'exitosa', "
        f"pero está en estado '{context.cita.estado}'"
    )


# ==================== Pasos adicionales para escenarios de error ====================


@given("que el solicitante tiene una cita cancelada")
def paso_tiene_cita_cancelada(context):
    """Prepara un solicitante con una cita cancelada."""
    context.cita = crear_cita_pendiente_hoy()
    context.solicitante = context.cita.solicitante

    # Cancelar la cita
    context.cita.estado = Cita.ESTADO_CANCELADA
    context.cita.save(update_fields=["estado"])


@when("el agente intenta asignar requisitos")
def paso_intenta_asignar_requisitos(context):
    """El agente intenta asignar requisitos al solicitante."""
    context.error = None

    try:
        resultado = asignar_requisitos(
            solicitante=context.solicitante,
            validar_fecha=True
        )
        context.resultado = resultado
    except DjValidationError as e:
        context.error = e


@then("el sistema rechaza la asignación")
def paso_rechaza_asignacion(context):
    """Verifica que el sistema rechazó la asignación de requisitos."""
    assert context.error is not None, (
        "El sistema debería haber rechazado la asignación de requisitos"
    )


@then("se notifica que la cita no está en estado válido")
def paso_notifica_cita_invalida(context):
    """Verifica que se muestre el mensaje de error apropiado."""
    mensaje_error = str(context.error)

    palabras_clave = ["pendiente", "estado", "no se pueden"]
    contiene_mensaje = any(
        palabra.lower() in mensaje_error.lower()
        for palabra in palabras_clave
    )

    assert contiene_mensaje, (
        f"El mensaje de error debe indicar que la cita no está en estado válido. "
        f"Mensaje recibido: {mensaje_error}"
    )

