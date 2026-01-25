"""
Servicio de registro de requisitos migratorios.
Gestiona la lógica de negocio para asignar requisitos según el tipo de visa.
"""
from __future__ import annotations
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from migration.models import (
    Solicitante,
    Requisito,
    REQUISITOS_POR_VISA,
    ESTADO_DOCUMENTO_FALTANTE,
)


@dataclass
class ResultadoRegistroRequisitos:
    """Representa el resultado de un registro de requisitos."""
    exitoso: bool
    mensaje: str
    requisitos: list[Requisito] | None = None


def obtener_requisitos_por_visa(tipo_visa: str) -> list[str]:
    """
    Obtiene la lista de requisitos para un tipo de visa específico.

    Args:
        tipo_visa: El tipo de visa (estudiantil, trabajo, residencial, turista).

    Returns:
        Lista de nombres de requisitos para el tipo de visa.

    Raises:
        ValidationError: Si el tipo de visa no es válido.
    """
    requisitos = REQUISITOS_POR_VISA.get(tipo_visa)
    if requisitos is None:
        raise ValidationError(f"Tipo de visa '{tipo_visa}' no válido.")
    return requisitos


def registrar_tipo_visa(solicitante: Solicitante, tipo_visa: str) -> Solicitante:
    """
    Registra el tipo de visa para un solicitante.

    Args:
        solicitante: El solicitante al que se le asigna el tipo de visa.
        tipo_visa: El tipo de visa a registrar.

    Returns:
        El solicitante actualizado.

    Raises:
        ValidationError: Si el tipo de visa no es válido.
    """
    # Validar que el tipo de visa sea válido
    obtener_requisitos_por_visa(tipo_visa)

    solicitante.tipo_visa = tipo_visa
    solicitante.save()
    return solicitante


def asignar_requisitos(solicitante: Solicitante) -> ResultadoRegistroRequisitos:
    """
    Asigna los requisitos correspondientes al tipo de visa del solicitante.

    Args:
        solicitante: El solicitante con tipo de visa asignado.

    Returns:
        ResultadoRegistroRequisitos con el estado de la operación.

    Raises:
        ValidationError: Si el solicitante no tiene tipo de visa asignado.
    """
    if not solicitante.tipo_visa:
        raise ValidationError(
            "El solicitante debe tener un tipo de visa asignado."
        )

    nombres_requisitos = obtener_requisitos_por_visa(solicitante.tipo_visa)
    requisitos_creados = []

    for nombre in nombres_requisitos:
        requisito, _ = Requisito.objects.get_or_create(
            solicitante=solicitante,
            nombre=nombre,
            defaults={
                "estado": ESTADO_DOCUMENTO_FALTANTE,
                "carga_habilitada": True,
            }
        )
        requisitos_creados.append(requisito)

    return ResultadoRegistroRequisitos(
        exitoso=True,
        mensaje=f"Se asignaron {len(requisitos_creados)} requisitos al solicitante.",
        requisitos=requisitos_creados
    )


def verificar_requisitos_pendientes(solicitante: Solicitante) -> bool:
    """
    Verifica si todos los requisitos del solicitante están pendientes por subir.

    Args:
        solicitante: El solicitante a verificar.

    Returns:
        True si todos los requisitos están en estado faltante, False en caso contrario.
    """
    requisitos = solicitante.requisitos.all()
    if not requisitos.exists():
        return False

    return all(req.estado == ESTADO_DOCUMENTO_FALTANTE for req in requisitos)
