"""
Servicio de agendamiento de citas migratorias.
Gestiona la lógica de negocio para agendar citas con agentes disponibles.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone
from django.core.exceptions import ValidationError

from migration.models import Agente, Cita, Solicitante

# Constantes de reglas de negocio
DIAS_MINIMOS_CANCELACION = 3
DIAS_MINIMOS_REPROGRAMACION = 3


@dataclass
class SolicitudAgendamiento:
    """Representa una solicitud para agendar una cita."""
    solicitante: Solicitante
    inicio: datetime


def buscar_agente_disponible(inicio: datetime) -> Agente | None:
    """
    Busca un agente activo que esté disponible en el horario especificado.

    Args:
        inicio: Fecha y hora de inicio de la cita.

    Returns:
        Agente disponible o None si no hay ninguno.
    """
    return (
        Agente.objects.filter(activo=True)
        .exclude(citas__inicio=inicio, citas__estado=Cita.ESTADO_PENDIENTE)
        .order_by("nombre")
        .first()
    )


def validar_solicitante_sin_cita_pendiente(solicitante: Solicitante) -> None:
    """
    Valida que el solicitante no tenga una cita pendiente.

    Args:
        solicitante: El solicitante a validar.

    Raises:
        ValidationError: Si el solicitante ya tiene una cita pendiente.
    """
    if solicitante.tiene_cita_pendiente():
        raise ValidationError(
            "El solicitante ya tiene una cita pendiente. "
            "Debe cancelar la cita existente antes de agendar una nueva."
        )


def agendar_cita(solicitud: SolicitudAgendamiento) -> Cita:
    """
    Agenda una cita para el solicitante en el horario especificado.

    El fin de la cita se calcula automáticamente sumando una hora al inicio.

    Args:
        solicitud: Datos de la solicitud de agendamiento.

    Returns:
        La cita creada y guardada.

    Raises:
        ValidationError: Si no hay agentes disponibles o el solicitante
                        ya tiene una cita pendiente.
    """
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


def calcular_dias_restantes(cita: Cita) -> int:
    """
    Calcula los días restantes hasta la fecha de la cita.

    Args:
        cita: La cita a evaluar.

    Returns:
        Número de días restantes hasta la cita.
    """
    ahora = timezone.localtime(timezone.now())
    fecha_cita = timezone.localtime(cita.inicio)
    return (fecha_cita.date() - ahora.date()).days


def validar_tiempo_cancelacion(cita: Cita) -> None:
    """
    Valida que la cancelación se realice con al menos 3 días de anticipación.

    Args:
        cita: La cita a validar.

    Raises:
        ValidationError: Si faltan menos de 3 días para la cita.
    """
    dias_restantes = calcular_dias_restantes(cita)

    if dias_restantes < DIAS_MINIMOS_CANCELACION:
        raise ValidationError(
            f"No se puede cancelar la cita. Las cancelaciones deben realizarse "
            f"con al menos {DIAS_MINIMOS_CANCELACION} días de anticipación. "
            f"Faltan solo {dias_restantes} días para su cita."
        )


def cancelar_cita(cita: Cita) -> ResultadoCancelacion:
    """
    Cancela una cita pendiente.

    Args:
        cita: La cita a cancelar.

    Returns:
        ResultadoCancelacion con el estado de la operación.

    Raises:
        ValidationError: Si la cita no puede ser cancelada.
    """
    if cita.estado != Cita.ESTADO_PENDIENTE:
        raise ValidationError("Solo se pueden cancelar citas pendientes.")

    validar_tiempo_cancelacion(cita)

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


def validar_tiempo_reprogramacion(cita: Cita) -> None:
    """
    Valida que la reprogramación se realice con al menos 3 días de anticipación.

    Reutiliza la lógica de cálculo de días restantes para mantener consistencia
    con las reglas de negocio de cancelación.

    Args:
        cita: La cita a validar.

    Raises:
        ValidationError: Si faltan menos de 3 días para la cita.
    """
    dias_restantes = calcular_dias_restantes(cita)

    if dias_restantes < DIAS_MINIMOS_REPROGRAMACION:
        raise ValidationError(
            f"No se puede reprogramar la cita. Las reprogramaciones deben realizarse "
            f"con al menos {DIAS_MINIMOS_REPROGRAMACION} días de anticipación. "
            f"Faltan solo {dias_restantes} días para su cita."
        )


def validar_cita_pendiente(cita: Cita) -> None:
    """
    Valida que la cita esté en estado pendiente.

    Args:
        cita: La cita a validar.

    Raises:
        ValidationError: Si la cita no está pendiente.
    """
    if cita.estado != Cita.ESTADO_PENDIENTE:
        raise ValidationError("Solo se pueden reprogramar citas pendientes.")


def reprogramar_cita(cita: Cita, nuevo_inicio: datetime) -> ResultadoReprogramacion:
    """
    Reprograma una cita pendiente a un nuevo horario.

    Libera el horario anterior del agente y asigna el nuevo horario.
    Si no hay agente disponible en el nuevo horario, intenta buscar otro agente.

    Args:
        cita: La cita a reprogramar.
        nuevo_inicio: Nueva fecha y hora de inicio para la cita.

    Returns:
        ResultadoReprogramacion con el estado de la operación y la cita actualizada.

    Raises:
        ValidationError: Si la cita no puede ser reprogramada.
    """
    # Validar que la cita esté pendiente
    validar_cita_pendiente(cita)

    # Validar tiempo mínimo de anticipación
    validar_tiempo_reprogramacion(cita)

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
