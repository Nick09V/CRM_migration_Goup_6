"""
Servicio de revisión de documentos migratorios.
Gestiona la lógica de negocio para aprobar y rechazar documentos.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from django.core.exceptions import ValidationError

from migration.models import (
    Documento,
    Carpeta,
    ESTADO_DOCUMENTO_PENDIENTE,
    ESTADO_DOCUMENTO_REVISADO,
    ESTADO_CARPETA_APROBADO,
)


@dataclass
class Notificacion:
    """Representa una notificación enviada al solicitante."""
    tipo: str
    mensaje: str
    destinatario: str
    enviada: bool = True


@dataclass
class ResultadoRevision:
    """Representa el resultado de una revisión de documento."""
    exitoso: bool
    mensaje: str
    documento: Optional[Documento] = None
    notificacion: Optional[Notificacion] = None


def validar_documento_pendiente(documento: Documento) -> None:
    """
    Valida que el documento esté en estado pendiente de revisión.

    Args:
        documento: El documento a validar.

    Raises:
        ValidationError: Si el documento no está pendiente.
    """
    if documento.estado != ESTADO_DOCUMENTO_PENDIENTE:
        raise ValidationError(
            f"Solo se pueden revisar documentos en estado 'pendiente'. "
            f"El documento está en estado '{documento.estado}'."
        )


def notificar_solicitante(
    documento: Documento,
    tipo_notificacion: str,
    mensaje: str
) -> Notificacion:
    """
    Crea y envía una notificación al solicitante.

    En una implementación real, esto enviaría un email o notificación push.
    Por ahora, simula la notificación creando un objeto Notificacion.

    Args:
        documento: El documento relacionado con la notificación.
        tipo_notificacion: Tipo de notificación ('aprobacion', 'rechazo').
        mensaje: Mensaje de la notificación.

    Returns:
        Instancia de Notificacion.
    """
    solicitante = documento.requisito.solicitante
    destinatario = solicitante.email or solicitante.nombre

    return Notificacion(
        tipo=tipo_notificacion,
        mensaje=mensaje,
        destinatario=destinatario,
        enviada=True
    )


def aprobar_documento(documento: Documento) -> ResultadoRevision:
    """
    Aprueba un documento marcándolo como revisado.

    Reglas de negocio:
    - El documento debe estar en estado pendiente.
    - Al aprobar, se marca como revisado sin observaciones.
    - Se notifica al solicitante sobre la aprobación.
    - Se deshabilita la carga de nuevas versiones.

    Args:
        documento: El documento a aprobar.

    Returns:
        ResultadoRevision con el estado de la operación.

    Raises:
        ValidationError: Si el documento no está en estado pendiente.
    """
    validar_documento_pendiente(documento)

    # Marcar como revisado
    documento.marcar_como_revisado()

    # Limpiar observaciones previas si las hubiera
    requisito = documento.requisito
    requisito.observaciones = ""
    requisito.deshabilitar_carga()
    requisito.actualizar_estado_segun_documento()

    # Notificar al solicitante
    nombre_requisito = requisito.nombre
    notificacion = notificar_solicitante(
        documento=documento,
        tipo_notificacion="aprobacion",
        mensaje=f"Su documento '{nombre_requisito}' ha sido aprobado."
    )

    return ResultadoRevision(
        exitoso=True,
        mensaje=f"Documento '{nombre_requisito}' aprobado correctamente.",
        documento=documento,
        notificacion=notificacion
    )


def rechazar_documento(
    documento: Documento,
    razones: str = ""
) -> ResultadoRevision:
    """
    Rechaza un documento y habilita la carga de una nueva versión.

    Reglas de negocio:
    - El documento debe estar en estado pendiente.
    - Se marca como faltante/rechazado.
    - Se registran las razones del rechazo.
    - Se habilita la carga de una nueva versión.
    - Se notifica al solicitante con las razones del rechazo.

    Args:
        documento: El documento a rechazar.
        razones: Razones del rechazo.

    Returns:
        ResultadoRevision con el estado de la operación.

    Raises:
        ValidationError: Si el documento no está en estado pendiente.
    """
    validar_documento_pendiente(documento)

    # Marcar como faltante/rechazado
    documento.marcar_como_faltante()

    # Actualizar requisito
    requisito = documento.requisito
    requisito.observaciones = razones
    requisito.habilitar_carga()
    requisito.save(update_fields=["observaciones", "carga_habilitada"])
    requisito.actualizar_estado_segun_documento()

    # Notificar al solicitante
    nombre_requisito = requisito.nombre
    mensaje_notificacion = (
        f"Su documento '{nombre_requisito}' ha sido rechazado. "
        f"Razones: {razones}. "
        "Por favor, suba una nueva versión corregida."
    )
    notificacion = notificar_solicitante(
        documento=documento,
        tipo_notificacion="rechazo",
        mensaje=mensaje_notificacion
    )

    return ResultadoRevision(
        exitoso=True,
        mensaje=f"Documento '{nombre_requisito}' rechazado. Se habilitó la carga de nueva versión.",
        documento=documento,
        notificacion=notificacion
    )


def es_ultimo_documento_pendiente(documento: Documento) -> bool:
    """
    Verifica si el documento es el único pendiente del solicitante.

    Args:
        documento: El documento a verificar.

    Returns:
        True si es el único documento pendiente, False en caso contrario.
    """
    solicitante = documento.requisito.solicitante

    # Obtener todos los documentos pendientes del solicitante
    documentos_pendientes = Documento.objects.filter(
        requisito__solicitante=solicitante,
        estado=ESTADO_DOCUMENTO_PENDIENTE
    )

    # Si hay exactamente 1 documento pendiente y es este, es el último
    return documentos_pendientes.count() == 1 and documentos_pendientes.first().id == documento.id


def marcar_carpeta_aprobada(documento: Documento) -> Carpeta:
    """
    Marca la carpeta del solicitante como aprobada.

    Args:
        documento: Documento cuyo solicitante tiene la carpeta a aprobar.

    Returns:
        La carpeta actualizada.

    Raises:
        ValidationError: Si la carpeta no existe.
    """
    solicitante = documento.requisito.solicitante

    try:
        carpeta = solicitante.carpeta
    except Carpeta.DoesNotExist:
        # Crear la carpeta si no existe
        carpeta = Carpeta.objects.create(solicitante=solicitante)

    carpeta.estado = ESTADO_CARPETA_APROBADO
    carpeta.save(update_fields=["estado"])

    return carpeta


def verificar_todos_documentos_revisados(documento: Documento) -> bool:
    """
    Verifica si todos los documentos del solicitante están revisados.

    Args:
        documento: Documento de referencia para obtener el solicitante.

    Returns:
        True si todos los documentos están revisados.
    """
    solicitante = documento.requisito.solicitante

    # Obtener todos los requisitos del solicitante
    requisitos = solicitante.requisitos.all()

    if not requisitos.exists():
        return False

    # Verificar que cada requisito tenga al menos un documento revisado
    for requisito in requisitos:
        documento_actual = requisito.obtener_documento_actual()
        if documento_actual is None or documento_actual.estado != ESTADO_DOCUMENTO_REVISADO:
            return False

    return True


def obtener_documento_pendiente_revision(documento_id: int) -> Documento:
    """
    Obtiene un documento pendiente de revisión por su ID.

    Args:
        documento_id: ID del documento.

    Returns:
        Instancia de Documento.

    Raises:
        ValidationError: Si el documento no existe o no está pendiente.
    """
    try:
        documento = Documento.objects.get(id=documento_id)
    except Documento.DoesNotExist:
        raise ValidationError(f"No existe un documento con ID {documento_id}.")

    validar_documento_pendiente(documento)

    return documento


def obtener_documentos_pendientes_solicitante(solicitante_id: int) -> list[Documento]:
    """
    Obtiene todos los documentos pendientes de un solicitante.

    Args:
        solicitante_id: ID del solicitante.

    Returns:
        Lista de documentos pendientes.
    """
    return list(Documento.objects.filter(
        requisito__solicitante_id=solicitante_id,
        estado=ESTADO_DOCUMENTO_PENDIENTE
    ).select_related("requisito", "requisito__solicitante"))

