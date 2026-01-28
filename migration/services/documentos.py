"""
Servicio de gestión de documentos migratorios.
Gestiona la lógica de negocio para subir, versionar y almacenar documentos.
"""
from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.core.exceptions import ValidationError
from django.conf import settings

from migration.models import (
    Solicitante,
    Requisito,
    Documento,
    Carpeta,
    TipoVisa,
    ESTADO_DOCUMENTO_PENDIENTE,
    ESTADO_DOCUMENTO_FALTANTE,
    ESTADO_DOCUMENTO_REVISADO,
    ESTADOS_DOCUMENTO,
)


# Ruta base para documentos (raíz del proyecto)
RUTA_BASE_DOCUMENTOS = Path(settings.BASE_DIR) / "Documentos"


@dataclass
class ResultadoSubidaDocumento:
    """Representa el resultado de una subida de documento."""
    exitoso: bool
    mensaje: str
    documento: Optional[Documento] = None
    ruta_archivo: Optional[str] = None
    version: Optional[int] = None


def obtener_estados_revision_permitidos() -> list[str]:
    """
    Obtiene la lista de estados de revisión permitidos.

    Returns:
        Lista de estados permitidos.
    """
    return [estado[0] for estado in ESTADOS_DOCUMENTO]


def obtener_tipos_visa_soportados() -> list[str]:
    """
    Obtiene la lista de tipos de visa soportados.

    Returns:
        Lista de códigos de tipos de visa activos.
    """
    return TipoVisa.obtener_tipos_activos()


def crear_estructura_carpetas(
    cedula: str,
    tipo_visa: str,
    nombre_requisito: str,
    version: int
) -> Path:
    """
    Crea la estructura de carpetas para almacenar un documento.

    Estructura: Documentos/CI_solicitante/tipoVisa/documentoCarpeta/version_n/

    Args:
        cedula: Cédula del solicitante.
        tipo_visa: Tipo de visa del solicitante.
        nombre_requisito: Nombre del requisito/documento.
        version: Número de versión del documento.

    Returns:
        Path de la carpeta creada.
    """
    nombre_requisito_limpio = nombre_requisito.replace(" ", "_")
    ruta = RUTA_BASE_DOCUMENTOS / cedula / tipo_visa / nombre_requisito_limpio / f"version_{version}"

    # Crear las carpetas si no existen
    ruta.mkdir(parents=True, exist_ok=True)

    return ruta


def guardar_archivo_fisico(
    ruta_carpeta: Path,
    nombre_archivo: str,
    contenido: bytes = b""
) -> Path:
    """
    Guarda un archivo físico en la carpeta especificada.

    Args:
        ruta_carpeta: Ruta de la carpeta donde guardar.
        nombre_archivo: Nombre del archivo a guardar.
        contenido: Contenido del archivo (bytes).

    Returns:
        Path del archivo guardado.
    """
    ruta_archivo = ruta_carpeta / nombre_archivo

    with open(ruta_archivo, "wb") as f:
        f.write(contenido)

    return ruta_archivo


def eliminar_carpeta_solicitante(cedula: str) -> bool:
    """
    Elimina la carpeta completa de un solicitante.

    Args:
        cedula: Cédula del solicitante.

    Returns:
        True si se eliminó correctamente, False si no existía.
    """
    ruta = RUTA_BASE_DOCUMENTOS / cedula

    if ruta.exists():
        shutil.rmtree(ruta)
        return True
    return False


def limpiar_carpeta_documentos() -> bool:
    """
    Elimina todos los documentos de la carpeta base.

    Returns:
        True si se limpió correctamente.
    """
    if RUTA_BASE_DOCUMENTOS.exists():
        shutil.rmtree(RUTA_BASE_DOCUMENTOS)
    return True


def validar_solicitante_para_carga(solicitante: Solicitante) -> None:
    """
    Valida que el solicitante tenga los datos necesarios para subir documentos.

    Args:
        solicitante: El solicitante a validar.

    Raises:
        ValidationError: Si faltan datos requeridos.
    """
    if not solicitante.cedula:
        raise ValidationError("El solicitante debe tener una cédula registrada.")

    if not solicitante.tipo_visa:
        raise ValidationError("El solicitante debe tener un tipo de visa asignado.")


def validar_carga_documento(requisito: Requisito) -> None:
    """
    Valida si se puede subir un documento al requisito.

    Args:
        requisito: El requisito donde se quiere subir.

    Raises:
        ValidationError: Si no se puede subir el documento.
    """
    if not requisito.carga_habilitada:
        raise ValidationError(
            f"La carga de documentos está deshabilitada para '{requisito.nombre}'."
        )

    if not requisito.puede_subir_nuevo_documento():
        documento_actual = requisito.obtener_documento_actual()
        if documento_actual and documento_actual.estado == ESTADO_DOCUMENTO_PENDIENTE:
            raise ValidationError(
                f"El documento '{requisito.nombre}' ya tiene una versión pendiente de revisión. "
                "Debe esperar la revisión antes de subir una nueva versión."
            )
        elif documento_actual and documento_actual.estado == ESTADO_DOCUMENTO_REVISADO:
            raise ValidationError(
                f"El documento '{requisito.nombre}' ya fue revisado y aprobado. "
                "No se pueden subir más versiones."
            )


def obtener_o_crear_requisito(
    solicitante: Solicitante,
    nombre_requisito: str
) -> Requisito:
    """
    Obtiene o crea un requisito para el solicitante.

    Args:
        solicitante: El solicitante.
        nombre_requisito: Nombre del requisito.

    Returns:
        Instancia de Requisito.
    """
    requisito, _ = Requisito.objects.get_or_create(
        solicitante=solicitante,
        nombre=nombre_requisito,
        defaults={
            "estado": ESTADO_DOCUMENTO_FALTANTE,
            "carga_habilitada": True,
        }
    )
    return requisito


def obtener_o_crear_carpeta(solicitante: Solicitante) -> Carpeta:
    """
    Obtiene o crea la carpeta del solicitante.

    Args:
        solicitante: El solicitante.

    Returns:
        Instancia de Carpeta.
    """
    carpeta, _ = Carpeta.objects.get_or_create(solicitante=solicitante)
    return carpeta


def subir_documento(
    solicitante: Solicitante,
    nombre_requisito: str,
    nombre_archivo: str,
    contenido: bytes = b""
) -> ResultadoSubidaDocumento:
    """
    Sube un documento para un requisito del solicitante.

    Reglas de negocio:
    - Si es la primera versión, se crea como versión 1.
    - Si el último documento fue rechazado, se crea la siguiente versión.
    - Si hay un documento pendiente, no se puede subir.
    - Si el documento fue aprobado, no se puede subir nueva versión.

    Args:
        solicitante: El solicitante que sube el documento.
        nombre_requisito: Nombre del requisito/documento.
        nombre_archivo: Nombre del archivo a subir.
        contenido: Contenido del archivo en bytes.

    Returns:
        ResultadoSubidaDocumento con el estado de la operación.

    Raises:
        ValidationError: Si no se cumplen las condiciones para subir.
    """
    # Validar solicitante
    validar_solicitante_para_carga(solicitante)

    # Obtener o crear el requisito
    requisito = obtener_o_crear_requisito(solicitante, nombre_requisito)

    # Validar si puede subir
    validar_carga_documento(requisito)

    # Calcular la nueva versión
    nueva_version = requisito.obtener_ultima_version() + 1

    # Crear estructura de carpetas físicas
    ruta_carpeta = crear_estructura_carpetas(
        cedula=solicitante.cedula,
        tipo_visa=solicitante.tipo_visa,
        nombre_requisito=nombre_requisito,
        version=nueva_version
    )

    # Guardar archivo físico
    ruta_archivo = guardar_archivo_fisico(
        ruta_carpeta=ruta_carpeta,
        nombre_archivo=nombre_archivo,
        contenido=contenido
    )

    # Crear registro en base de datos
    documento = Documento.objects.create(
        requisito=requisito,
        version=nueva_version,
        estado=ESTADO_DOCUMENTO_PENDIENTE,
        nombre_archivo=nombre_archivo,
        ruta_archivo=str(ruta_archivo.relative_to(RUTA_BASE_DOCUMENTOS.parent))
    )

    # Deshabilitar carga hasta revisión
    requisito.deshabilitar_carga()
    requisito.actualizar_estado_segun_documento()

    # Asegurar que existe la carpeta del solicitante
    obtener_o_crear_carpeta(solicitante)

    return ResultadoSubidaDocumento(
        exitoso=True,
        mensaje=f"Documento '{nombre_archivo}' guardado como Versión {nueva_version}.",
        documento=documento,
        ruta_archivo=str(ruta_archivo),
        version=nueva_version
    )


def rechazar_documento(documento: Documento, observaciones: str = "") -> Documento:
    """
    Rechaza un documento y habilita la carga de una nueva versión.

    Args:
        documento: El documento a rechazar.
        observaciones: Observaciones del rechazo.

    Returns:
        El documento actualizado.
    """
    documento.marcar_como_faltante()

    requisito = documento.requisito
    requisito.habilitar_carga()
    requisito.observaciones = observaciones
    requisito.actualizar_estado_segun_documento()

    return documento


def aprobar_documento(documento: Documento) -> Documento:
    """
    Aprueba un documento y deshabilita la carga de nuevas versiones.

    Args:
        documento: El documento a aprobar.

    Returns:
        El documento actualizado.
    """
    documento.marcar_como_revisado()

    requisito = documento.requisito
    requisito.deshabilitar_carga()
    requisito.actualizar_estado_segun_documento()

    return documento


def verificar_archivo_existe(ruta: str) -> bool:
    """
    Verifica si un archivo existe en el sistema de archivos.

    Args:
        ruta: Ruta del archivo.

    Returns:
        True si existe, False en caso contrario.
    """
    return Path(ruta).exists()


def listar_documentos_solicitante(solicitante: Solicitante) -> list[dict]:
    """
    Lista todos los documentos de un solicitante con sus rutas.

    Args:
        solicitante: El solicitante.

    Returns:
        Lista de diccionarios con información de documentos.
    """
    documentos = Documento.objects.filter(
        requisito__solicitante=solicitante
    ).select_related("requisito")

    return [
        {
            "requisito": doc.requisito.nombre,
            "version": doc.version,
            "estado": doc.estado,
            "nombre_archivo": doc.nombre_archivo,
            "ruta": doc.ruta_archivo,
            "existe_fisicamente": verificar_archivo_existe(doc.ruta_archivo)
        }
        for doc in documentos
    ]


def puede_subir_nueva_version(requisito: Requisito) -> tuple[bool, str]:
    """
    Verifica si se puede subir una nueva versión del documento.

    Args:
        requisito: El requisito a verificar.

    Returns:
        Tupla (puede_subir, mensaje_razon).
    """
    if not requisito.carga_habilitada:
        return False, "La carga está deshabilitada."

    documento_actual = requisito.obtener_documento_actual()

    if documento_actual is None:
        return True, "No hay documentos previos."

    if documento_actual.estado == ESTADO_DOCUMENTO_PENDIENTE:
        return False, "Hay una versión pendiente de revisión."

    if documento_actual.estado == ESTADO_DOCUMENTO_REVISADO:
        return False, "El documento ya fue aprobado."

    if documento_actual.estado == ESTADO_DOCUMENTO_FALTANTE:
        return True, "La versión anterior fue rechazada."

    return False, "Estado desconocido."
