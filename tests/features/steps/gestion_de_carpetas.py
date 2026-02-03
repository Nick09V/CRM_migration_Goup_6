import os
import sys
import django

# Configurar Django antes de importar modelos
ruta_proyecto = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ruta_proyecto)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')
django.setup()

from behave import given, when, then
from django.core.exceptions import ValidationError as DjValidationError
from django.contrib.auth.models import User

from migration.models import (
    Solicitante,
    Agente,
    Documento,
    Carpeta,
    ESTADO_DOCUMENTO_REVISADO,
    ESTADO_CARPETA_APROBADO,
    ESTADO_CARPETA_CERRADA_ACEPTADA,
    ESTADO_CARPETA_CERRADA_RECHAZADA,
    EstadoDocumento
)
from migration.services.revision import (
    marcar_carpeta_aprobada,
)
from migration.services.documentos import (
    obtener_o_crear_requisito,
    obtener_o_crear_carpeta,
)
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================


def crear_solicitante_con_datos() -> Solicitante:
    """
    Crea un nuevo solicitante con datos aleatorios.

    Returns:
        Instancia de Solicitante guardada en la base de datos.
    """
    return Solicitante.objects.create(
        nombre=faker.unique.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email(),
        tipo_visa="trabajo"
    )


def obtener_o_crear_agente() -> Agente:
    """
    Asegura que exista un agente activo en el sistema.

    Returns:
        Instancia de Agente activo.
    """
    agente, _ = Agente.objects.get_or_create(
        nombre="Agente Carpetas",
        defaults={"activo": True}
    )
    return agente


def crear_documento_revisado(
    solicitante: Solicitante,
    nombre_requisito: str = "DocumentoRevisado"
) -> Documento:
    """
    Crea un documento ya revisado/aprobado para un solicitante.

    Args:
        solicitante: El solicitante propietario del documento.
        nombre_requisito: Nombre del requisito.

    Returns:
        Instancia de Documento en estado revisado.
    """
    requisito = obtener_o_crear_requisito(
        solicitante=solicitante,
        nombre_requisito=nombre_requisito
    )

    version = requisito.obtener_ultima_version() + 1
    documento = Documento.objects.create(
        requisito=requisito,
        version=version,
        estado=EstadoDocumento.DOCUMENTO_REVISADO_APROBADO,
        nombre_archivo=f"{nombre_requisito}_v{version}.pdf",
        ruta_archivo=f"Documentos/{solicitante.cedula}/trabajo/{nombre_requisito}/version_{version}/"
    )

    return documento


def verificar_carpeta_aprobada(carpeta: Carpeta) -> bool:
    """
    Verifica si la carpeta puede ser aprobada (todos los documentos revisados).

    Args:
        carpeta: La carpeta a verificar.

    Returns:
        True si todos los documentos están revisados.
    """
    return carpeta.todos_documentos_revisados()


def cerrar_carpeta_aceptada(carpeta: Carpeta) -> Carpeta:
    """
    Cierra la carpeta como aceptada cuando la visa es aprobada.

    Args:
        carpeta: La carpeta a cerrar.

    Returns:
        La carpeta actualizada.
    """
    carpeta.estado = ESTADO_CARPETA_CERRADA_ACEPTADA
    carpeta.save(update_fields=["estado"])
    return carpeta


def cerrar_carpeta_rechazada(carpeta: Carpeta, motivo: str) -> Carpeta:
    """
    Cierra la carpeta como rechazada cuando la visa es rechazada.

    Args:
        carpeta: La carpeta a cerrar.
        motivo: El motivo del rechazo.

    Returns:
        La carpeta actualizada.
    """
    carpeta.estado = ESTADO_CARPETA_CERRADA_RECHAZADA
    carpeta.observaciones = motivo
    carpeta.save(update_fields=["estado", "observaciones"])
    return carpeta


# ==================== Escenario 1: Carpeta aprobada cuando todos los documentos están validados ====================


@given("que todos los documentos del solicitante están en estado aprobado")
def paso_todos_documentos_aprobados(context):
    """Prepara un solicitante con todos sus documentos aprobados."""
    context.solicitante = crear_solicitante_con_datos()
    context.agente = obtener_o_crear_agente()

    # Crear carpeta del solicitante
    context.carpeta = obtener_o_crear_carpeta(context.solicitante)

    # Crear documentos ya revisados/aprobados
    context.documento1 = crear_documento_revisado(
        solicitante=context.solicitante,
        nombre_requisito="Pasaporte"
    )
    context.documento2 = crear_documento_revisado(
        solicitante=context.solicitante,
        nombre_requisito="CertificadoAntecedentes"
    )

    # Verificar que los documentos están revisados
    assert context.documento1.esta_documento_aprobado(), (
        "El documento 1 debe estar revisado"
    )
    assert context.documento2.esta_documento_aprobado(), (
        "El documento 2 debe estar revisado"
    )


@when("el sistema verifica la carpeta del solicitante")
def paso_sistema_verifica_carpeta(context):
    """El sistema verifica si todos los documentos de la carpeta están revisados."""
    context.error = None

    try:
        # Verificar si todos los documentos están revisados
        if verificar_carpeta_aprobada(context.carpeta):
            context.carpeta = marcar_carpeta_aprobada(context.documento1)
    except DjValidationError as e:
        context.error = e


@then("la carpeta queda en estado aprobada")
def paso_carpeta_estado_aprobada(context):
    """Verifica que la carpeta quedó en estado aprobada."""
    assert context.error is None, f"No debería haber error: {context.error}"

    # Refrescar carpeta desde BD
    context.carpeta.refresh_from_db()

    assert context.carpeta.estado == ESTADO_CARPETA_APROBADO, (
        f"El estado de la carpeta debe ser 'aprobado', "
        f"pero es '{context.carpeta.estado}'"
    )


# ==================== Escenario 2: Carpeta cerrada por visa aprobada ====================


@given("que la carpeta del solicitante está en estado aprobada")
def paso_carpeta_aprobada(context):
    """Prepara una carpeta en estado aprobada."""
    context.solicitante = crear_solicitante_con_datos()
    context.agente = obtener_o_crear_agente()

    # Crear carpeta en estado aprobado
    context.carpeta = obtener_o_crear_carpeta(context.solicitante)
    context.carpeta.estado = ESTADO_CARPETA_APROBADO
    context.carpeta.save(update_fields=["estado"])

    # Crear al menos un documento revisado para consistencia
    context.documento = crear_documento_revisado(
        solicitante=context.solicitante,
        nombre_requisito="Pasaporte"
    )

    assert context.carpeta.estado == ESTADO_CARPETA_APROBADO, (
        "La carpeta debe estar en estado aprobado"
    )


@given("el consulado aprueba la visa")
def paso_consulado_aprueba_visa(context):
    """El consulado aprueba la solicitud de visa."""
    context.resultado_visa = "aprobada"


@when("el agente registra el resultado de la visa")
def paso_agente_registra_resultado_visa(context):
    """El agente registra el resultado positivo de la visa."""
    context.error = None

    try:
        if context.resultado_visa == "aprobada":
            context.carpeta = cerrar_carpeta_aceptada(context.carpeta)
    except DjValidationError as e:
        context.error = e


@then("la carpeta queda en estado cerrada aceptada")
def paso_carpeta_cerrada_aceptada(context):
    """Verifica que la carpeta quedó en estado cerrada aceptada."""
    assert context.error is None, f"No debería haber error: {context.error}"

    # Refrescar carpeta desde BD
    context.carpeta.refresh_from_db()

    assert context.carpeta.estado == ESTADO_CARPETA_CERRADA_ACEPTADA, (
        f"El estado de la carpeta debe ser 'cerrada_aceptada', "
        f"pero es '{context.carpeta.estado}'"
    )


# ==================== Escenario 3: Carpeta cerrada por visa rechazada ====================


@given("el consulado rechaza la visa")
def paso_consulado_rechaza_visa(context):
    """El consulado rechaza la solicitud de visa."""
    context.resultado_visa = "rechazada"
    context.motivo_rechazo = "Documentación insuficiente para demostrar solvencia económica."


@when("el agente registra el motivo del rechazo")
def paso_agente_registra_motivo_rechazo(context):
    """El agente registra el motivo del rechazo de la visa."""
    context.error = None

    try:
        if context.resultado_visa == "rechazada":
            context.carpeta = cerrar_carpeta_rechazada(
                context.carpeta,
                context.motivo_rechazo
            )
    except DjValidationError as e:
        context.error = e


@then("la carpeta queda en estado cerrada rechazada")
def paso_carpeta_cerrada_rechazada(context):
    """Verifica que la carpeta quedó en estado cerrada rechazada."""
    assert context.error is None, f"No debería haber error: {context.error}"

    # Refrescar carpeta desde BD
    context.carpeta.refresh_from_db()

    assert context.carpeta.estado == ESTADO_CARPETA_CERRADA_RECHAZADA, (
        f"El estado de la carpeta debe ser 'cerrada_rechazada', "
        f"pero es '{context.carpeta.estado}'"
    )


@then("se registra la observación del rechazo")
def paso_registra_observacion_rechazo(context):
    """Verifica que se registró la observación del rechazo."""
    # Refrescar carpeta desde BD
    context.carpeta.refresh_from_db()

    assert context.carpeta.observaciones == context.motivo_rechazo, (
        f"La observación debe ser '{context.motivo_rechazo}', "
        f"pero es '{context.carpeta.observaciones}'"
    )
