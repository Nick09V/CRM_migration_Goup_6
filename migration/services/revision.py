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
    solicitante = documento.requisito.solicitante
    destinatario = solicitante.email or solicitante.nombre

    return Notificacion(
        tipo=tipo_notificacion,
        mensaje=mensaje,
        destinatario=destinatario,
        enviada=True
    )


def aprobar_documento(documento: Documento) -> ResultadoRevision:
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
    validar_documento_pendiente(documento)

    # Marcar como faltante/rechazado
    documento.marcar_como_rechazado()

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
    solicitante = documento.requisito.solicitante

    # Obtener todos los documentos pendientes del solicitante
    documentos_pendientes = Documento.objects.filter(
        requisito__solicitante=solicitante,
        estado=ESTADO_DOCUMENTO_PENDIENTE
    )

    # Si hay exactamente 1 documento pendiente y es este, es el último
    return documentos_pendientes.count() == 1 and documentos_pendientes.first().id == documento.id


def marcar_carpeta_aprobada(documento: Documento) -> Carpeta:
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
    try:
        documento = Documento.objects.get(id=documento_id)
    except Documento.DoesNotExist:
        raise ValidationError(f"No existe un documento con ID {documento_id}.")

    validar_documento_pendiente(documento)

    return documento


def obtener_documentos_pendientes_solicitante(solicitante_id: int) -> list[Documento]:
    return list(Documento.objects.filter(
        requisito__solicitante_id=solicitante_id,
        estado=ESTADO_DOCUMENTO_PENDIENTE
    ).select_related("requisito", "requisito__solicitante"))

