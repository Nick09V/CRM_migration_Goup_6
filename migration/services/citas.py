from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from django.db import transaction

from migration.models import Cita, Solicitante, Agente


class DomainError(Exception):
    pass


class CitaActivaExistenteError(DomainError):
    pass


class HorarioNoDisponibleError(DomainError):
    pass


class VentanaCancelacionExpiradaError(DomainError):
    pass


@dataclass
class CitaDTO:
    id: int
    solicitante_id: int
    agente_id: Optional[int]
    fecha_hora: datetime
    estado: str


@transaction.atomic
def agendar(solicitante: Solicitante, fecha_hora: datetime) -> CitaDTO:
    """Agendar una cita si el solicitante no tiene cita pendiente.
    Asigna el agente con menor carga.
    """
    existe = Cita.objects.filter(solicitante=solicitante, estado=Cita.ESTADO_PENDIENTE).exists()
    if existe:
        raise CitaActivaExistenteError("El solicitante ya posee una cita activa")

    # seleccionar agente con menor carga_pendiente
    agente = Agente.objects.order_by('carga_pendiente', 'id').first()
    if not agente:
        raise DomainError("No hay agentes disponibles")

    cita = Cita.objects.create(
        solicitante=solicitante,
        agente=agente,
        fecha_hora=fecha_hora,
        estado=Cita.ESTADO_PENDIENTE,
    )
    # actualizar carga del agente
    Agente.objects.filter(pk=agente.pk).update(carga_pendiente=agente.carga_pendiente + 1)

    return CitaDTO(
        id=cita.id,
        solicitante_id=solicitante.id,
        agente_id=agente.id if agente else None,
        fecha_hora=cita.fecha_hora,
        estado=cita.estado,
    )


@transaction.atomic
def cancelar(solicitante: Solicitante) -> CitaDTO:
    """Cancelar la cita pendiente del solicitante.
    Disminuye carga del agente.
    """
    cita = Cita.objects.filter(solicitante=solicitante, estado=Cita.ESTADO_PENDIENTE).first()
    if not cita:
        raise DomainError("No existe una cita que cancelar")

    agente = cita.agente
    cita.delete()

    if agente:
        Agente.objects.filter(pk=agente.pk).update(carga_pendiente=max(0, agente.carga_pendiente - 1))

    return CitaDTO(
        id=0,
        solicitante_id=solicitante.id,
        agente_id=agente.id if agente else None,
        fecha_hora=datetime.now(),
        estado=Cita.ESTADO_CANCELADA,
    )


@transaction.atomic
def reprogramar(solicitante: Solicitante, nuevo_horario: datetime) -> CitaDTO:
    """Reprogramar la cita pendiente del solicitante.
    Si el agente actual no está disponible para el nuevo horario, reasignar al de menor carga.
    """
    cita = Cita.objects.filter(solicitante=solicitante, estado=Cita.ESTADO_PENDIENTE).first()
    if not cita:
        raise DomainError("No existe una cita pendiente para reprogramar")

    # Simplificación: asumimos disponibilidad si existe un agente; si no, reasignar.
    agente_actual = cita.agente
    agente_disponible = Agente.objects.order_by('carga_pendiente', 'id').first()

    if agente_actual and agente_disponible and agente_actual.id == agente_disponible.id:
        # mantiene agente
        cita.fecha_hora = nuevo_horario
        cita.save(update_fields=['fecha_hora'])
        return CitaDTO(cita.id, solicitante.id, agente_actual.id, cita.fecha_hora, cita.estado)

    # reasignar a agente con menor carga
    cita.agente = agente_disponible
    cita.fecha_hora = nuevo_horario
    cita.save(update_fields=['agente', 'fecha_hora'])
    return CitaDTO(cita.id, solicitante.id, agente_disponible.id if agente_disponible else None, cita.fecha_hora, cita.estado)

