from behave import given, when, then, step
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from datetime import time
import random

from migration.models import (
    Solicitante,
    Agente,
    Cita,
    CatalogoRequisito,
    TipoVisa,
)
from migration.services.requisitos import (
    registrar_tipo_visa,
    asignar_requisitos,
    verificar_requisitos_pendientes,
    marcar_cita_exitosa,
    obtener_catalogo_requisitos,
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


def crear_horario_hoy(hora: int = None) -> dj_timezone.datetime:
    if hora is None:
        # Generar hora aleatoria entre 8 y 11 con minutos aleatorios para evitar colisiones
        hora = random.randint(8, 11)
        minutos = random.randint(0, 59)
    else:
        minutos = 0
    hoy = dj_timezone.localtime(dj_timezone.now()).date()
    horario_naive = dj_timezone.datetime.combine(hoy, time(hora, minutos))
    return dj_timezone.make_aware(horario_naive)


def crear_cita_pendiente_hoy() -> Cita:
    solicitante = crear_solicitante()
    agente = obtener_o_crear_agente()
    horario = crear_horario_hoy()  # Hora aleatoria para evitar colisiones

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


def obtener_nombres_requisitos_catalogo() -> list[str]:
    """Obtiene los nombres de requisitos activos desde el catálogo."""
    catalogo = obtener_catalogo_requisitos()
    return [req.nombre for req in catalogo]


def inicializar_catalogo_si_vacio() -> None:
    """Inicializa el catálogo de requisitos si está vacío."""
    if not CatalogoRequisito.objects.filter(activo=True).exists():
        CatalogoRequisito.inicializar_catalogo()


def inicializar_tipos_visa_si_vacio() -> None:
    """Inicializa los tipos de visa si están vacíos."""
    if not TipoVisa.objects.filter(activo=True).exists():
        TipoVisa.inicializar_tipos_default()


def obtener_tipo_visa_valido(codigo: str) -> TipoVisa:
    """Obtiene un tipo de visa válido del modelo o lanza error."""
    try:
        return TipoVisa.objects.get(codigo=codigo, activo=True)
    except TipoVisa.DoesNotExist:
        tipos_disponibles = list(TipoVisa.objects.filter(activo=True).values_list('codigo', flat=True))
        raise AssertionError(
            f"El tipo de visa '{codigo}' no existe o no está activo. "
            f"Tipos disponibles: {tipos_disponibles}"
        )


# ==================== Escenario: Registro de requisitos migratorios ====================


@given("que se tiene una cita pendiente")
def paso_tiene_cita_pendiente(context):
    """Prepara un solicitante con una cita pendiente para hoy."""
    # Asegurar que el catálogo y tipos de visa estén inicializados
    inicializar_catalogo_si_vacio()
    inicializar_tipos_visa_si_vacio()

    context.cita = crear_cita_pendiente_hoy()
    context.solicitante = context.cita.solicitante
    context.agente = context.cita.agente

    # Verificar que la cita está pendiente usando método encapsulado
    assert context.cita.esta_pendiente(), (
        f"La cita debe estar pendiente"
    )

    # Verificar que la cita es para hoy
    assert context.cita.es_fecha_cita_hoy(), (
        "La cita debe estar programada para hoy"
    )


@step("que el agente ha registrado que el cliente necesita la visa {tipo_visa}")
def paso_agente_registra_tipo_visa(context, tipo_visa: str):
    """El agente registra el tipo de visa que necesita el cliente."""
    codigo_visa = tipo_visa.strip()

    # Inicializar tipos de visa si están vacíos
    inicializar_tipos_visa_si_vacio()

    # Validar que el tipo de visa existe en el modelo
    tipo_visa_obj = obtener_tipo_visa_valido(codigo_visa)
    context.tipo_visa = tipo_visa_obj.codigo

    # Si no existe solicitante, crearlo con cita
    if not hasattr(context, 'solicitante') or context.solicitante is None:
        inicializar_catalogo_si_vacio()
        context.cita = crear_cita_pendiente_hoy()
        context.solicitante = context.cita.solicitante

    # Registrar el tipo de visa para el solicitante
    registrar_tipo_visa(context.solicitante, context.tipo_visa)

    # Verificar que el tipo de visa fue asignado usando método encapsulado
    context.solicitante.refresh_from_db()
    assert context.solicitante.tiene_tipo_visa(context.tipo_visa), (
        f"El solicitante debe tener el tipo de visa '{context.tipo_visa}'"
    )


@step("se tienen los siguientes requisitos cargados")
def paso_requisitos_cargados(context):
    """Carga la lista de requisitos desde el catálogo del sistema."""
    # Inicializar catálogo si está vacío
    inicializar_catalogo_si_vacio()

    # Obtener requisitos esperados de la tabla Gherkin
    requisitos_esperados = []
    for row in context.table:
        requisito = row["requisitos_cargado"].strip()
        requisitos_esperados.append(requisito)

    # Obtener requisitos desde el catálogo
    requisitos_catalogo = obtener_nombres_requisitos_catalogo()

    # Verificar que todos los requisitos de la tabla existen en el catálogo
    for req_esperado in requisitos_esperados:
        assert req_esperado in requisitos_catalogo, (
            f"El requisito '{req_esperado}' no existe en el catálogo. "
            f"Requisitos disponibles: {requisitos_catalogo}"
        )

    # Guardar los requisitos cargados desde el catálogo
    context.requisitos_cargados = requisitos_catalogo

    # Verificar cantidad mínima esperada
    assert len(context.requisitos_cargados) >= len(requisitos_esperados), (
        f"Se esperaban al menos {len(requisitos_esperados)} requisitos en el catálogo, "
        f"pero hay {len(context.requisitos_cargados)}"
    )


@then('el agente asigna los siguientes requisitos al cliente "{requisitos}"')
def paso_asignar_requisitos(context, requisitos: str):
    """El agente asigna los requisitos correspondientes al tipo de visa."""
    context.error = None

    # Parsear los requisitos esperados
    requisitos_esperados = parsear_lista_requisitos(requisitos)

    # Obtener requisitos desde el catálogo
    requisitos_cargados = obtener_nombres_requisitos_catalogo()

    # Verificar que los requisitos a asignar existen en el catálogo
    for req in requisitos_esperados:
        assert req in requisitos_cargados, (
            f"El requisito '{req}' no está disponible en el catálogo. "
            f"Requisitos disponibles: {requisitos_cargados}"
        )

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
    """Los documentos quedan como pendientes por subir."""
    # Verificar que todos los requisitos están pendientes
    todos_pendientes = verificar_requisitos_pendientes(context.solicitante)
    assert todos_pendientes, "Todos los requisitos deben estar pendientes por subir"

    # Verificar estado individual de cada requisito usando métodos encapsulados
    for requisito in context.requisitos:
        requisito.refresh_from_db()
        assert requisito.esta_pendiente_de_subir(), (
            f"El requisito '{requisito.nombre}' debe estar pendiente por subir"
        )
        assert requisito.tiene_carga_habilitada(), (
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

    # Verificar que la cita está en estado exitosa usando método encapsulado
    context.cita.refresh_from_db()
    assert context.cita.esta_exitosa(), (
        "La cita debe estar en estado exitosa"
    )


