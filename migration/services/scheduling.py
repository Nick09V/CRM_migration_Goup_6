from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone
from django.core.exceptions import ValidationError

from migration.models import Agente, Cita, Solicitante

#reglas de negocio
DIAS_MINIMOS_CANCELACION = 4
DIAS_MINIMOS_REPROGRAMACION = 8


@dataclass
class SolicitudAgendamiento:
    """Representa una solicitud para agendar una cita."""
    solicitante: Solicitante
    inicio: datetime


def buscar_agente_disponible(inicio: datetime) -> Agente | None:
    return (
        Agente.objects.filter(activo=True)
        .exclude(citas__inicio=inicio, citas__estado=Cita.ESTADO_PENDIENTE)
        .order_by("nombre")
        .first()
    )


def validar_solicitante_sin_cita_pendiente(solicitante: Solicitante) -> None:
    if solicitante.tiene_cita_pendiente():
        raise ValidationError(
            "El solicitante ya tiene una cita pendiente. "
            "Debe cancelar la cita existente antes de agendar una nueva."
        )


def agendar_cita(solicitud: SolicitudAgendamiento) -> Cita:
    validar_solicitante_sin_cita_pendiente(solicitud.solicitante)

    agente = buscar_agente_disponible(solicitud.inicio)
    if not agente:
        raise ValidationError("No hay agentes disponibles para ese horario.")

    cita = Cita(
        solicitante=solicitud.solicitante,
        agente=agente,
        inicio=solicitud.inicio,
        estado=Cita.ESTADO_PENDIENTE,
    )
    # El fin se calcula automáticamente en el metodo save() del modelo
    cita.save()
    return cita


@dataclass
class ResultadoCancelacion:
    """Representa el resultado de un intento de cancelación."""
    exitoso: bool
    mensaje: str
    dias_minimos: int = DIAS_MINIMOS_CANCELACION



def calcular_dias_restantes(cita: Cita) -> int:
    ahora = timezone.localtime(timezone.now())
    fecha_cita = timezone.localtime(cita.inicio)
    return (fecha_cita.date() - ahora.date()).days


def validar_tiempo_cancelacion(cita: Cita) -> bool:
    dias_restantes = calcular_dias_restantes(cita)

    if dias_restantes < DIAS_MINIMOS_CANCELACION:
        return False
    return True

def cancelar_cita(cita: Cita) -> ResultadoCancelacion:
    if cita.estado != Cita.ESTADO_PENDIENTE:
        raise ValidationError("Solo se pueden cancelar citas pendientes.")

    if validar_tiempo_cancelacion(cita) is False:
        raise ValidationError(
            f"No se puede cancelar la cita. Las cancelaciones deben realizarse "
            f"con al menos {DIAS_MINIMOS_CANCELACION} días de anticipación."
        )

    # Eliminar la cita para liberar el horario
    cita.delete()

    return ResultadoCancelacion(
        exitoso=True,
        mensaje="La cita ha sido cancelada exitosamente."
    )


# ==================== Reprogramación de Citas ====================


@dataclass
class ResultadoReprogramacion:
    """Representa el resultado de un intento de reprogramación."""
    exitoso: bool
    mensaje: str
    cita: Cita | None = None


def validar_tiempo_reprogramacion(cita: Cita) -> bool:
    dias_restantes = calcular_dias_restantes(cita)

    if dias_restantes < DIAS_MINIMOS_REPROGRAMACION:
        return False
    return True


def validar_cita_pendiente(cita: Cita) -> None:
    if cita.estado != Cita.ESTADO_PENDIENTE:
        raise ValidationError("Solo se pueden reprogramar citas pendientes.")


def reprogramar_cita(cita: Cita, nuevo_inicio: datetime) -> ResultadoReprogramacion:
    # Validar que la cita esté pendiente
    validar_cita_pendiente(cita)

    # Validar tiempo mínimo de anticipación
    if validar_tiempo_reprogramacion(cita) is False:
        raise ValidationError(f"No se puede reprogramar la cita. Las reprogramaciones deben realizarse "
            f"con al menos {DIAS_MINIMOS_REPROGRAMACION} días de anticipación.")


    # Buscar agente disponible para el nuevo horario
    agente_disponible = buscar_agente_disponible(nuevo_inicio)

    if not agente_disponible:
        raise ValidationError(
            "No hay agentes disponibles para el nuevo horario seleccionado."
        )

    # Actualizar la cita con el nuevo horario y agente
    cita.inicio = nuevo_inicio
    cita.agente = agente_disponible
    cita.save()

    return ResultadoReprogramacion(
        exitoso=True,
        mensaje="La cita ha sido reprogramada exitosamente.",
        cita=cita
    )


