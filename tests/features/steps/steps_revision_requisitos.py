# -*- coding: utf-8 -*-
"""
Steps para la característica de Validación de documentos (Revisión de requisitos).
Implementa los pasos BDD para los escenarios de aprobación y rechazo de documentos.
"""
from behave import given, when, then
from django.core.exceptions import ValidationError as DjValidationError

from migration.models import (
    Solicitante,
    Agente,
    Documento,
    ESTADO_DOCUMENTO_PENDIENTE,
    ESTADO_DOCUMENTO_REVISADO,
    ESTADO_DOCUMENTO_FALTANTE,
    ESTADO_CARPETA_APROBADO,
)
from migration.services.revision import (
    aprobar_documento,
    rechazar_documento,
    es_ultimo_documento_pendiente,
    marcar_carpeta_aprobada,
    verificar_todos_documentos_revisados,
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
        nombre="Agente Revision",
        defaults={"activo": True}
    )
    return agente


def crear_documento_pendiente(
    solicitante: Solicitante,
    nombre_requisito: str = "DocumentoPrueba"
) -> Documento:
    """
    Crea un documento pendiente de revisión para un solicitante.

    Args:
        solicitante: El solicitante propietario del documento.
        nombre_requisito: Nombre del requisito.

    Returns:
        Instancia de Documento en estado pendiente.
    """
    # Crear requisito
    requisito = obtener_o_crear_requisito(
        solicitante=solicitante,
        nombre_requisito=nombre_requisito
    )

    # Crear documento pendiente
    version = requisito.obtener_ultima_version() + 1
    documento = Documento.objects.create(
        requisito=requisito,
        version=version,
        estado=ESTADO_DOCUMENTO_PENDIENTE,
        nombre_archivo=f"{nombre_requisito}_v{version}.pdf",
        ruta_archivo=f"Documentos/{solicitante.cedula}/trabajo/{nombre_requisito}/version_{version}/"
    )

    # Deshabilitar carga mientras está pendiente
    requisito.deshabilitar_carga()

    return documento


# ==================== Antecedentes ====================


@given("que existe un documento pendiente por revisar")
def paso_documento_pendiente_por_revisar(context):
    """Prepara un documento pendiente de revisión."""
    context.solicitante = crear_solicitante_con_datos()
    context.agente = obtener_o_crear_agente()

    # Crear carpeta del solicitante
    context.carpeta = obtener_o_crear_carpeta(context.solicitante)

    # Crear documento pendiente
    context.documento = crear_documento_pendiente(
        solicitante=context.solicitante,
        nombre_requisito="DocumentoPrueba"
    )

    # Verificar que el documento está pendiente
    assert context.documento.estado == ESTADO_DOCUMENTO_PENDIENTE, (
        f"El documento debe estar pendiente, pero está en '{context.documento.estado}'"
    )


# ==================== Escenario 1: Aprobación de un documento ====================


@when("el agente marca como aprobado el documento")
def paso_agente_aprueba_documento(context):
    """El agente aprueba el documento pendiente."""
    context.error = None

    try:
        context.resultado = aprobar_documento(context.documento)
    except DjValidationError as e:
        context.error = e
        context.resultado = None


@then('el documento queda marcado como "{estado}" sin observaciones')
def paso_documento_marcado_sin_observaciones(context, estado: str):
    """Verifica que el documento quedó marcado con el estado correcto sin observaciones."""
    assert context.error is None, f"No debería haber error: {context.error}"
    assert context.resultado is not None, "Debe existir un resultado"
    assert context.resultado.exitoso, f"La operación debe ser exitosa: {context.resultado.mensaje}"

    # Refrescar documento desde BD
    context.documento.refresh_from_db()

    estado_esperado = estado.lower()
    assert context.documento.estado == estado_esperado, (
        f"El estado debe ser '{estado_esperado}', pero es '{context.documento.estado}'"
    )

    # Verificar que no hay observaciones
    requisito = context.documento.requisito
    requisito.refresh_from_db()
    assert requisito.observaciones == "", (
        f"No debe haber observaciones, pero tiene: '{requisito.observaciones}'"
    )


@then("el solicitante es notificado de la aprobación")
def paso_solicitante_notificado_aprobacion(context):
    """Verifica que el solicitante fue notificado de la aprobación."""
    assert context.resultado.notificacion is not None, (
        "Debe existir una notificación"
    )
    assert context.resultado.notificacion.tipo == "aprobacion", (
        f"La notificación debe ser de tipo 'aprobacion', "
        f"pero es '{context.resultado.notificacion.tipo}'"
    )
    assert context.resultado.notificacion.enviada, (
        "La notificación debe haber sido enviada"
    )


# ==================== Escenario 2: Aprobación de documento final ====================


@given("que existe un unico documento por aprobar")
def paso_unico_documento_por_aprobar(context):
    """Prepara un escenario donde solo hay un documento pendiente por aprobar."""
    # Verificar que ya existe un documento en el contexto
    assert hasattr(context, "documento"), "Debe existir un documento en el contexto"

    # Verificar que es el único pendiente
    es_unico = es_ultimo_documento_pendiente(context.documento)
    assert es_unico, (
        "Debe ser el único documento pendiente para este escenario"
    )


@when("el agente aprueba el documento")
def paso_agente_aprueba_documento_final(context):
    """El agente aprueba el documento final."""
    context.error = None

    try:
        context.resultado = aprobar_documento(context.documento)

        # Si todos los documentos están revisados, marcar carpeta como aprobada
        if verificar_todos_documentos_revisados(context.documento):
            context.carpeta = marcar_carpeta_aprobada(context.documento)

    except DjValidationError as e:
        context.error = e
        context.resultado = None


@then("el documento queda marcado como revisado sin observaciones")
def paso_documento_revisado_sin_observaciones(context):
    """Verifica que el documento quedó marcado como revisado sin observaciones."""
    assert context.error is None, f"No debería haber error: {context.error}"
    assert context.resultado is not None, "Debe existir un resultado"
    assert context.resultado.exitoso, f"La operación debe ser exitosa: {context.resultado.mensaje}"

    # Refrescar documento desde BD
    context.documento.refresh_from_db()

    assert context.documento.estado == ESTADO_DOCUMENTO_REVISADO, (
        f"El estado debe ser 'revisado', pero es '{context.documento.estado}'"
    )

    # Verificar que no hay observaciones
    requisito = context.documento.requisito
    requisito.refresh_from_db()
    assert requisito.observaciones == "", (
        f"No debe haber observaciones, pero tiene: '{requisito.observaciones}'"
    )


@then("se notifica al solicitante sobre la aprobación")
def paso_notifica_solicitante_aprobacion(context):
    """Verifica que el solicitante fue notificado de la aprobación."""
    assert context.resultado.notificacion is not None, (
        "Debe existir una notificación"
    )
    assert context.resultado.notificacion.tipo == "aprobacion", (
        f"La notificación debe ser de tipo 'aprobacion', "
        f"pero es '{context.resultado.notificacion.tipo}'"
    )
    assert context.resultado.notificacion.enviada, (
        "La notificación debe haber sido enviada"
    )


@then("la carpeta queda marcado como aprobada")
def paso_carpeta_aprobada(context):
    """Verifica que la carpeta del solicitante queda marcada como aprobada."""
    # Refrescar carpeta desde BD
    context.carpeta.refresh_from_db()

    assert context.carpeta.estado == ESTADO_CARPETA_APROBADO, (
        f"El estado de la carpeta debe ser 'aprobado', "
        f"pero es '{context.carpeta.estado}'"
    )


# ==================== Escenario 3: Rechazo de un documento ====================


@when("el agente rechaza el documento")
def paso_agente_rechaza_documento(context):
    """El agente rechaza el documento pendiente."""
    context.error = None
    context.razones_rechazo = None

    # Preparar para el siguiente paso (escribir razones)
    # El rechazo completo se hace en el paso de escribir razones


@when("escribe las razones del rechazo")
def paso_escribe_razones_rechazo(context):
    """El agente escribe las razones del rechazo."""
    context.razones_rechazo = "El documento no cumple con los requisitos de formato. Por favor, suba el documento en formato PDF con todas las páginas legibles."

    try:
        context.resultado = rechazar_documento(
            documento=context.documento,
            razones=context.razones_rechazo
        )
    except DjValidationError as e:
        context.error = e
        context.resultado = None


@then("el sistema notifica al solicitante las razones del rechazo")
def paso_notifica_razones_rechazo(context):
    """Verifica que el sistema notificó al solicitante con las razones del rechazo."""
    assert context.error is None, f"No debería haber error: {context.error}"
    assert context.resultado is not None, "Debe existir un resultado"
    assert context.resultado.exitoso, f"La operación debe ser exitosa: {context.resultado.mensaje}"

    # Verificar notificación
    notificacion = context.resultado.notificacion
    assert notificacion is not None, "Debe existir una notificación"
    assert notificacion.tipo == "rechazo", (
        f"La notificación debe ser de tipo 'rechazo', "
        f"pero es '{notificacion.tipo}'"
    )
    assert notificacion.enviada, "La notificación debe haber sido enviada"

    # Verificar que el mensaje contiene las razones
    assert context.razones_rechazo in notificacion.mensaje, (
        "El mensaje de notificación debe contener las razones del rechazo"
    )


@then("se habilita la carga del documento")
def paso_habilita_carga_documento(context):
    """Verifica que se habilitó la carga de una nueva versión del documento."""
    # Refrescar requisito desde BD
    requisito = context.documento.requisito
    requisito.refresh_from_db()

    assert requisito.carga_habilitada, (
        "La carga del documento debe estar habilitada después del rechazo"
    )

    # Verificar que el documento quedó como faltante
    context.documento.refresh_from_db()
    assert context.documento.estado == ESTADO_DOCUMENTO_FALTANTE, (
        f"El estado del documento debe ser 'faltante', "
        f"pero es '{context.documento.estado}'"
    )

    # Verificar que las observaciones fueron guardadas
    assert requisito.observaciones == context.razones_rechazo, (
        "Las observaciones deben contener las razones del rechazo"
    )

