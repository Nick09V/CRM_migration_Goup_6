from __future__ import annotations
from dataclasses import dataclass
from django.utils import timezone
from django.core.exceptions import ValidationError
from migration.models import Agente, Cita


@dataclass
class SolicitudAgendamiento:
    cliente: str
    inicio: timezone.datetime


def buscar_agente_disponible(inicio: timezone.datetime) -> Agente | None:
    # Agente activo sin cita en ese inicio
    return (
        Agente.objects.filter(activo=True)
        .exclude(citas__inicio=inicio)
        .order_by("nombre")
        .first()
    )


def agendar_cita(req: SolicitudAgendamiento) -> Cita:
    agente = buscar_agente_disponible(req.inicio)
    if not agente:
        raise ValidationError("No hay agentes disponibles para ese horario.")
    cita = Cita(
        cliente=req.cliente,
        agente=agente,
        inicio=req.inicio,
        fin=req.inicio + timezone.timedelta(hours=1),
        estado=Cita.ESTADO_PENDIENTE,
    )
    cita.full_clean()
    cita.save()
    return cita
