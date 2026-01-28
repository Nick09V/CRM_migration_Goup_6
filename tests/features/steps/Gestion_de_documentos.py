from behave import given, when, then
from django.core.exceptions import ValidationError as DjValidationError

from migration.models import (
    Solicitante,
    Requisito,
    Documento,
    Carpeta,
    TipoVisa,
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
    """
    Crea un solicitante con cédula y tipo de visa asignados.

    Args:
        tipo_visa: Tipo de visa a asignar.

    Returns:
        Instancia de Solicitante.
    """
    return Solicitante.objects.create(
        nombre=faker.unique.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email(),
        tipo_visa=tipo_visa
    )


def limpiar_solicitante(context) -> None:
    """
    Limpia los datos del solicitante del contexto.
    Elimina la carpeta física y los registros de BD.
    """
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


def crear_tipos_visa_para_tests():
    """
    Crea los tipos de visa que se usan en los antecedentes.
    Esta función se llama una vez por feature.
    """
    tipos_visa = ['estudiantil', 'trabajo', 'residencial', 'turista']

    for codigo in tipos_visa:
        TipoVisa.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': codigo.title(),
                'activo': True
            }
        )


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
    """
    Crea y verifica que los tipos de visa soportados estén disponibles.

    CAMBIO CLAVE: Ahora creamos los tipos de visa directamente aquí,
    no dependemos de constantes o funciones de población.
    """
    # Crear los tipos de visa que el test necesita
    crear_tipos_visa_para_tests()

    # Obtener los tipos creados
    tipos = obtener_tipos_visa_soportados()

    # Verificar que se crearon correctamente
    assert "estudiantil" in tipos, f"Debe existir el tipo 'estudiantil'. Tipos disponibles: {tipos}"
    assert "trabajo" in tipos, f"Debe existir el tipo 'trabajo'. Tipos disponibles: {tipos}"
    assert "residencial" in tipos, f"Debe existir el tipo 'residencial'. Tipos disponibles: {tipos}"
    assert "turista" in tipos, f"Debe existir el tipo 'turista'. Tipos disponibles: {tipos}"

    context.tipos_visa = tipos


# ==================== Escenario 1: Carga inicial de un documento ====================


@given('que un solicitante de visa de "{tipo_visa}" no ha subido su "{nombre_requisito}"')
def paso_solicitante_sin_documento(context, tipo_visa: str, nombre_requisito: str):
    """
    Prepara un solicitante que no ha subido el documento especificado.

    CAMBIO CLAVE: Aseguramos que el tipo de visa existe antes de crear el solicitante.
    """
    # Asegurar que el tipo de visa existe
    TipoVisa.objects.get_or_create(
        codigo=tipo_visa,
        defaults={'nombre': tipo_visa.title(), 'activo': True}
    )

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


@then('el estado del documento cambia a "{estado_esperado}"')
def paso_verificar_estado_documento(context, estado_esperado: str):
    """Verifica que el documento tenga el estado esperado."""
    context.documento.refresh_from_db()

    estado_esperado_lower = estado_esperado.lower()
    assert context.documento.estado == estado_esperado_lower, (
        f"El estado debe ser '{estado_esperado_lower}', "
        f"pero es '{context.documento.estado}'"
    )


# ==================== Escenario 2: Carga de documento rechazado ====================


@given("que la versión del documento es: {version_previa:d}")
def paso_crear_documento_con_version(context, version_previa: int):
    """
    Crea un documento con la versión especificada.

    CAMBIO CLAVE: Aseguramos que el tipo de visa existe.
    """
    # Asegurar que el tipo de visa existe
    TipoVisa.objects.get_or_create(
        codigo='trabajo',
        defaults={'nombre': 'Trabajo', 'activo': True}
    )

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
    assert context.documento.estado == ESTADO_DOCUMENTO_FALTANTE, (
        f"El estado debe ser 'faltante', pero es '{context.documento.estado}'"
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


@then('el estado queda "{estado_esperado}"')
def paso_verificar_estado_final(context, estado_esperado: str):
    """Verifica que el documento tenga el estado final esperado."""
    context.documento.refresh_from_db()

    estado_esperado_lower = estado_esperado.lower()
    assert context.documento.estado == estado_esperado_lower, (
        f"El estado debe ser '{estado_esperado_lower}', "
        f"pero es '{context.documento.estado}'"
    )


# ==================== Pasos adicionales de utilidad ====================


@then("el archivo físico existe en la ruta correcta")
def paso_verificar_archivo_fisico(context):
    """Verifica que el archivo físico existe en el sistema de archivos."""
    from pathlib import Path

    ruta = context.resultado.ruta_archivo
    assert Path(ruta).exists(), f"El archivo debe existir en: {ruta}"


@given("que el documento anterior fue aprobado")
def paso_aprobar_documento_anterior(context):
    """Aprueba el documento anterior."""
    aprobar_documento(context.documento)

    context.documento.refresh_from_db()
    assert context.documento.estado == "revisado", (
        f"El estado debe ser 'revisado', pero es '{context.documento.estado}'"
    )


@then("el sistema rechaza la subida")
def paso_verificar_rechazo_subida(context):
    """Verifica que el sistema rechazó la subida."""
    assert context.error is not None, "Debería haber un error de validación"
