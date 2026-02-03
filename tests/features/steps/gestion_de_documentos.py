from behave import given, when, then
from django.core.exceptions import ValidationError as DjValidationError

from migration.models import (
    Solicitante,
    Requisito,
    Documento,
    Carpeta,
    ESTADO_DOCUMENTO_FALTANTE,
)
from migration.services.documentos import (
    subir_documento,
    rechazar_documento,
    aprobar_documento,
    eliminar_carpeta_solicitante,
    obtener_estados_revision_permitidos,
    obtener_tipos_visa_soportados,
    obtener_o_crear_requisito,
)
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================


def crear_solicitante_con_visa(tipo_visa: str) -> Solicitante:
    return Solicitante.objects.create(
        nombre=faker.unique.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email(),
        tipo_visa=tipo_visa
    )


def limpiar_solicitante(context) -> None:
    if hasattr(context, "solicitante") and context.solicitante:
        # Eliminar carpeta física
        if context.solicitante.cedula:
            eliminar_carpeta_solicitante(context.solicitante.cedula)

        # Eliminar registros de BD
        Documento.objects.filter(
            requisito__solicitante=context.solicitante
        ).delete()
        Requisito.objects.filter(solicitante=context.solicitante).delete()
        Carpeta.objects.filter(solicitante=context.solicitante).delete()


# ==================== Hooks de limpieza ====================


def after_scenario(context, scenario):
    """Hook que se ejecuta después de cada escenario para limpiar."""
    limpiar_solicitante(context)


# ==================== Antecedentes ====================


@given("los estados de revisión permitidos son: pendiente, revisado, faltante")
def paso_estados_permitidos(context):
    """Verifica que los estados de revisión permitidos estén configurados."""
    estados = obtener_estados_revision_permitidos()

    assert "pendiente" in estados, "Debe existir el estado 'pendiente'"
    assert "revisado" in estados, "Debe existir el estado 'revisado'"
    assert "faltante" in estados, "Debe existir el estado 'faltante'"

    context.estados_permitidos = estados


@given("los tipos de visa soportados son: estudiantil, trabajo, residencial, turista")
def paso_tipos_visa_soportados(context):
    """Verifica que los tipos de visa soportados estén configurados."""
    tipos = obtener_tipos_visa_soportados()

    assert "estudiantil" in tipos, "Debe existir el tipo 'estudiantil'"
    assert "trabajo" in tipos, "Debe existir el tipo 'trabajo'"
    assert "residencial" in tipos, "Debe existir el tipo 'residencial'"
    assert "turista" in tipos, "Debe existir el tipo 'turista'"

    context.tipos_visa = tipos


# ==================== Escenario 1: Carga inicial de un documento ====================


@given('que un solicitante de visa de "{tipo_visa}" no ha subido su "{nombre_requisito}"')
def paso_solicitante_sin_documento(context, tipo_visa: str, nombre_requisito: str):
    """Prepara un solicitante que no ha subido el documento especificado."""
    context.solicitante = crear_solicitante_con_visa(tipo_visa)
    context.nombre_requisito = nombre_requisito
    context.tipo_visa = tipo_visa

    # Crear el requisito sin documentos
    context.requisito = obtener_o_crear_requisito(
        solicitante=context.solicitante,
        nombre_requisito=nombre_requisito
    )

    # Verificar que no tiene documentos
    cantidad_docs = context.requisito.documentos.count()
    assert cantidad_docs == 0, (
        f"El requisito no debe tener documentos. Tiene {cantidad_docs}."
    )


@when('sube el archivo "{nombre_archivo}"')
def paso_subir_archivo(context, nombre_archivo: str):
    """El solicitante sube un archivo."""
    context.nombre_archivo = nombre_archivo
    context.error = None

    # Simular contenido del archivo
    contenido = f"Contenido de prueba para {nombre_archivo}".encode("utf-8")

    try:
        context.resultado = subir_documento(
            solicitante=context.solicitante,
            nombre_requisito=context.nombre_requisito,
            nombre_archivo=nombre_archivo,
            contenido=contenido
        )
    except DjValidationError as e:
        context.error = e
        context.resultado = None


@then('el archivo se guarda como "{version_esperada}"')
def paso_verificar_version(context, version_esperada: str):
    """Verifica que el archivo se guardó con la versión correcta."""
    assert context.error is None, f"No debería haber error: {context.error}"
    assert context.resultado is not None, "Debe existir un resultado"
    assert context.resultado.exitoso, f"La subida debe ser exitosa: {context.resultado.mensaje}"

    # Extraer número de versión del string "Versión N"
    version_num = int(version_esperada.split()[-1])

    assert context.resultado.version == version_num, (
        f"La versión debe ser {version_num}, pero es {context.resultado.version}"
    )

    # Verificar que el documento existe en la BD
    documento = context.resultado.documento
    assert documento is not None, "Debe existir el documento en la BD"
    assert documento.version == version_num, (
        f"La versión en BD debe ser {version_num}, pero es {documento.version}"
    )

    context.documento = documento


@then('el documento queda pendiente para su revisión')
def paso_verificar_estado_documento(context):
    """Verifica que el documento tenga el estado esperado."""
    context.documento.refresh_from_db()
    assert context.documento.esta_documento_pendiente(), (
        f"El estado debe estar en estado pendiente"
    )



# ==================== Escenario 2: Carga de documento rechazado ====================


@given("que la versión del documento es: {version_previa:d}")
def paso_crear_documento_con_version(context, version_previa: int):
    """Crea un documento con la versión especificada."""
    # Crear solicitante si no existe
    if not hasattr(context, "solicitante") or context.solicitante is None:
        context.solicitante = crear_solicitante_con_visa("trabajo")

    context.nombre_requisito = "DocumentoPrueba"

    # Crear el requisito
    context.requisito = obtener_o_crear_requisito(
        solicitante=context.solicitante,
        nombre_requisito=context.nombre_requisito
    )

    # Crear documentos hasta llegar a la versión especificada
    for v in range(1, version_previa + 1):
        # Habilitar carga para poder crear el documento
        context.requisito.habilitar_carga()

        # Subir documento
        resultado = subir_documento(
            solicitante=context.solicitante,
            nombre_requisito=context.nombre_requisito,
            nombre_archivo=f"documento_v{v}.pdf",
            contenido=f"Contenido versión {v}".encode()
        )

        context.documento = resultado.documento

        # Si no es la última versión, rechazar para poder subir la siguiente
        if v < version_previa:
            rechazar_documento(context.documento)

    # Verificar la versión
    context.documento.refresh_from_db()
    assert context.documento.version == version_previa, (
        f"La versión debe ser {version_previa}, pero es {context.documento.version}"
    )


@given("dicho documento ha sido rechazado")
def paso_rechazar_documento(context):
    """Rechaza el documento actual para permitir nueva versión."""
    context.documento.refresh_from_db()

    # Rechazar el documento
    rechazar_documento(context.documento, "Documento rechazado para prueba")

    # Verificar estado
    context.documento.refresh_from_db()
    assert context.documento.esta_documento_rechazado(), (
        "El estado debe estar en el estado de rechazado"
    )

    # Verificar que se puede subir nueva versión
    context.requisito.refresh_from_db()
    assert context.requisito.carga_habilitada, (
        "La carga debe estar habilitada después de rechazar"
    )


@when("el solicitante sube un documento")
def paso_solicitante_sube_documento(context):
    """El solicitante sube un nuevo documento."""
    context.error = None

    version_anterior = context.documento.version

    try:
        context.resultado = subir_documento(
            solicitante=context.solicitante,
            nombre_requisito=context.nombre_requisito,
            nombre_archivo=f"documento_v{version_anterior + 1}.pdf",
            contenido=f"Contenido nueva versión {version_anterior + 1}".encode()
        )
    except DjValidationError as e:
        context.error = e
        context.resultado = None


@then("el documento se guarda como versión {version_esperada:d}")
def paso_verificar_version_numerica(context, version_esperada: int):
    """Verifica que el documento se guardó con la versión numérica esperada."""
    assert context.error is None, f"No debería haber error: {context.error}"
    assert context.resultado is not None, "Debe existir un resultado"
    assert context.resultado.exitoso, f"La subida debe ser exitosa: {context.resultado.mensaje}"

    assert context.resultado.version == version_esperada, (
        f"La versión debe ser {version_esperada}, pero es {context.resultado.version}"
    )

    # Actualizar referencia al documento nuevo
    context.documento = context.resultado.documento


@then('el estado del documento se marca como pendiente para su revisión')
def paso_verificar_estado_final(context):
    """Verifica que el documento tenga el estado final esperado."""
    context.documento.refresh_from_db()

    assert context.documento.esta_documento_pendiente(), (
        "El estado debe estar con estado pendiente"
    )
