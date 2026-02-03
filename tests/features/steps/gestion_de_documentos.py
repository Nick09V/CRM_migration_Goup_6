from behave import given, when, then
from django.core.exceptions import ValidationError as DjValidationError

from migration.models import (
    Solicitante,
    Requisito,
    Documento,
    Carpeta,
    TipoVisa,
    EstadoDocumento,
)
from migration.services.documentos import (
    subir_documento,
    rechazar_documento,
    aprobar_documento,
    eliminar_carpeta_solicitante,
    obtener_o_crear_requisito,
)
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================


def inicializar_tipos_visa_si_vacio() -> None:
    """Inicializa los tipos de visa si están vacíos."""
    if not TipoVisa.objects.filter(activo=True).exists():
        TipoVisa.inicializar_tipos_default()


def obtener_codigos_tipos_visa_activos() -> list[str]:
    """Obtiene los códigos de tipos de visa activos desde el modelo."""
    inicializar_tipos_visa_si_vacio()
    return list(TipoVisa.objects.filter(activo=True).values_list('codigo', flat=True))


def obtener_estados_documento_permitidos() -> list[str]:
    """Obtiene los estados de documento permitidos desde el modelo EstadoDocumento."""
    return [estado.value for estado in EstadoDocumento]


def obtener_tipo_visa_valido(codigo: str) -> TipoVisa:
    """Obtiene un tipo de visa válido del modelo o lanza error."""
    inicializar_tipos_visa_si_vacio()
    try:
        return TipoVisa.objects.get(codigo=codigo, activo=True)
    except TipoVisa.DoesNotExist:
        tipos_disponibles = obtener_codigos_tipos_visa_activos()
        raise AssertionError(
            f"El tipo de visa '{codigo}' no existe o no está activo. "
            f"Tipos disponibles: {tipos_disponibles}"
        )


def crear_solicitante_con_visa(tipo_visa: str) -> Solicitante:
    # Validar que el tipo de visa existe en el modelo
    tipo_visa_obj = obtener_tipo_visa_valido(tipo_visa)

    return Solicitante.objects.create(
        nombre=faker.unique.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email(),
        tipo_visa=tipo_visa_obj.codigo
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


@given("los estados de revisión permitidos son: pendiente, revisado, rechazado")
def paso_estados_permitidos(context):
    """Verifica que los estados de revisión permitidos estén configurados en el modelo."""
    estados = obtener_estados_documento_permitidos()

    # Verificar estados según EstadoDocumento
    assert EstadoDocumento.DOCUMENTO_PENDIENTE_POR_REVISION.value in estados, (
        "Debe existir el estado 'pendiente'"
    )
    assert EstadoDocumento.DOCUMENTO_REVISADO_APROBADO.value in estados, (
        "Debe existir el estado 'revisado'"
    )
    assert EstadoDocumento.DOCUMENTO_REVISADO_RECHAZADO.value in estados, (
        "Debe existir el estado 'rechazado'"
    )

    context.estados_permitidos = estados


@given("los tipos de visa soportados son: estudiantil, trabajo, residencial, turista")
def paso_tipos_visa_soportados(context):
    """Verifica que los tipos de visa soportados estén configurados en el modelo."""
    tipos = obtener_codigos_tipos_visa_activos()

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

    assert context.resultado.version == version_num, (
        f"La versión debe ser {version_num}, pero es {context.resultado.version}"
    )

    # Verificar que el documento existe en la BD
    documento = context.resultado.documento
    assert documento is not None, "Debe existir el documento en la BD"

    # Usar método del requisito para verificar la versión
    ultima_version = documento.requisito.obtener_ultima_version()
    assert ultima_version == version_num, (
        f"La última versión del requisito debe ser {version_num}, pero es {ultima_version}"
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
    """Verifica que el documento tenga el estado final esperado."""
    context.documento.refresh_from_db()

    assert context.documento.esta_documento_pendiente(), (
        "El estado debe estar con estado pendiente"
    )
