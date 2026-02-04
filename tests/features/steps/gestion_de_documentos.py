from behave import given, when, then
from django.core.exceptions import ValidationError as DjValidationError

from migration.models import (
    Solicitante,
    Requisito,
    Documento,
    Carpeta,
    TipoVisa
)
from migration.services.documentos import (
    subir_documento,
    rechazar_documento,
    eliminar_carpeta_solicitante,
    obtener_o_crear_requisito,
)
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================


def crear_solicitante_con_visa(tipo_visa: str) -> Solicitante:
    """Crea un solicitante con el tipo de visa especificado."""
    tipo_visa_obj = TipoVisa.objects.get(codigo=tipo_visa, activo=True)

    return Solicitante.objects.create(
        nombre=faker.unique.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email(),
        tipo_visa=tipo_visa_obj.codigo
    )


def limpiar_solicitante(context) -> None:
    """Limpia los datos del solicitante al finalizar el escenario."""
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


@given("los tipos de visa soportados son: {tipos_visa}")
def paso_tipos_visa_soportados(context, tipos_visa: str):
    """Agrega los tipos de visa especificados directamente a la clase TipoVisa."""
    tipos = [t.strip() for t in tipos_visa.split(",")]
    
    for tipo in tipos:
        TipoVisa.objects.get_or_create(
            codigo=tipo,
            defaults={"nombre": tipo.capitalize(), "activo": True}
        )
    
    context.tipos_visa = tipos
    assert len(context.tipos_visa) == 4


# ==================== Escenario 1: Carga inicial de un documento ====================


@given('que un solicitante de visa de "{tipo_visa}" no ha subido su "{nombre_requisito}"')
def paso_solicitante_sin_documento(context, tipo_visa: str, nombre_requisito: str):
    """Prepara un solicitante que no ha subido el documento especificado."""
    context.solicitante = crear_solicitante_con_visa(tipo_visa)
    context.nombre_requisito = nombre_requisito
    context.tipo_visa = tipo_visa

    # Verificar que el solicitante tiene el tipo de visa asignado
    assert context.solicitante.tiene_tipo_visa(tipo_visa), (
        f"El solicitante debe tener el tipo de visa '{tipo_visa}'"
    )

    # Crear el requisito sin documentos
    context.requisito = obtener_o_crear_requisito(
        solicitante=context.solicitante,
        nombre_requisito=nombre_requisito
    )

    # Verificar que no tiene documentos usando método del requisito
    documento_actual = context.requisito.obtener_documento_actual()
    assert documento_actual is None, (
        "El requisito no debe tener documentos previos"
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

    documento = context.resultado.documento

    ultima_version = documento.requisito.obtener_ultima_version()
    assert ultima_version == version_num, (
        f"La última versión del requisito debe ser {version_num}, pero es {ultima_version}"
    )

    context.documento = documento


@then('el documento queda pendiente para su revisión')
def paso_verificar_estado_documento(context):
    """Verifica que el documento tenga estado pendiente."""
    context.documento.refresh_from_db()
    assert context.documento.esta_documento_pendiente(), (
        "El documento debe estar en estado pendiente"
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

    # Verificar la versión usando método del requisito
    ultima_version = context.requisito.obtener_ultima_version()
    assert ultima_version == version_previa, (
        f"La última versión debe ser {version_previa}, pero es {ultima_version}"
    )


@given("dicho documento ha sido rechazado")
def paso_rechazar_documento(context):
    """Rechaza el documento actual para permitir nueva versión."""
    context.documento.refresh_from_db()

    # Rechazar el documento
    rechazar_documento(context.documento, "Documento rechazado para prueba")

    # Verificar estado usando método encapsulado
    context.documento.refresh_from_db()
    assert context.documento.esta_documento_rechazado(), (
        "El documento debe estar en estado rechazado"
    )

    # Verificar que se puede subir nueva versión usando método encapsulado
    context.requisito.refresh_from_db()
    assert context.requisito.tiene_carga_habilitada(), (
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
    """Verifica que el documento tenga estado pendiente."""
    context.documento.refresh_from_db()

    assert context.documento.esta_documento_pendiente(), (
        "El documento debe estar en estado pendiente"
    )
