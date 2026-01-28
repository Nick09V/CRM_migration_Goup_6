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
    Cita,
    TipoVisa,
    RequisitoVisa,
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
        Lista de códigos de requisitos para el tipo de visa.

    Raises:
        ValidationError: Si el tipo de visa no es válido.
    """
    # Verificar que el tipo de visa existe y está activo
    if not TipoVisa.existe(tipo_visa):
        raise ValidationError(f"Tipo de visa '{tipo_visa}' no válido.")

    # Obtener requisitos desde la BD
    requisitos = RequisitoVisa.obtener_requisitos_por_visa(tipo_visa)
    if not requisitos:
        raise ValidationError(f"No hay requisitos configurados para la visa '{tipo_visa}'.")

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
    # Validar que el tipo de visa exista en la BD
    if not TipoVisa.existe(tipo_visa):
        raise ValidationError(f"Tipo de visa '{tipo_visa}' no válido.")

    solicitante.tipo_visa = tipo_visa
    solicitante.save()
    return solicitante


def obtener_cita_pendiente(solicitante: Solicitante) -> Cita:
    """
    Obtiene la cita pendiente del solicitante.

    Args:
        solicitante: El solicitante a consultar.

    Returns:
        La cita pendiente del solicitante.

    Raises:
        ValidationError: Si el solicitante no tiene cita pendiente.
    """
    cita = solicitante.citas.filter(estado=Cita.ESTADO_PENDIENTE).first()
    if not cita:
        raise ValidationError(
            "El solicitante no tiene una cita pendiente. "
            "Debe agendar una cita antes de asignar requisitos."
        )
    return cita


def validar_cita_para_asignacion(cita: Cita) -> None:
    """
    Valida que la cita cumpla las condiciones para asignar requisitos.

    Reglas de negocio:
    - La cita debe estar en estado pendiente.
    - La fecha de la cita debe ser hoy.

    Args:
        cita: La cita a validar.

    Raises:
        ValidationError: Si la cita no cumple las condiciones.
    """
    if cita.estado != Cita.ESTADO_PENDIENTE:
        raise ValidationError(
            f"No se pueden asignar requisitos. La cita está en estado '{cita.estado}'. "
            "Solo se pueden asignar requisitos a citas pendientes."
        )

    if not cita.es_fecha_cita_hoy():
        raise ValidationError(
            "No se pueden asignar requisitos. La fecha de la cita no coincide con la fecha actual. "
            "Solo se pueden asignar requisitos el día programado de la cita."
        )


def filtrar_requisitos_disponibles(
    requisitos_solicitados: list[str],
    requisitos_cargados: list[str]
) -> list[str]:
    """
    Filtra los requisitos solicitados contra la lista global de requisitos cargados.

    Args:
        requisitos_solicitados: Lista de requisitos que se desean asignar.
        requisitos_cargados: Lista global de requisitos disponibles en el sistema.

    Returns:
        Lista de requisitos que están disponibles para asignar.

    Raises:
        ValidationError: Si algún requisito solicitado no está en los cargados.
    """
    requisitos_no_disponibles = [
        req for req in requisitos_solicitados
        if req not in requisitos_cargados
    ]

    if requisitos_no_disponibles:
        raise ValidationError(
            f"Los siguientes requisitos no están disponibles en el sistema: "
            f"{', '.join(requisitos_no_disponibles)}"
        )

    return requisitos_solicitados


def asignar_requisitos(
    solicitante: Solicitante,
    requisitos_a_asignar: list[str] | None = None,
    requisitos_cargados: list[str] | None = None,
    validar_fecha: bool = True
) -> ResultadoRegistroRequisitos:
    """
    Asigna los requisitos correspondientes al solicitante.

    Si no se especifican requisitos_a_asignar, se usan los del tipo de visa.
    Valida que exista una cita pendiente y que sea el día de la cita.

    Args:
        solicitante: El solicitante con tipo de visa asignado.
        requisitos_a_asignar: Lista de requisitos específicos a asignar (opcional).
        requisitos_cargados: Lista global de requisitos disponibles (opcional).
        validar_fecha: Si se debe validar que la cita sea hoy (default: True).

    Returns:
        ResultadoRegistroRequisitos con el estado de la operación.

    Raises:
        ValidationError: Si el solicitante no cumple las condiciones.
    """
    if not solicitante.tipo_visa:
        raise ValidationError(
            "El solicitante debe tener un tipo de visa asignado."
        )

    # Obtener y validar la cita pendiente
    cita = obtener_cita_pendiente(solicitante)

    if validar_fecha:
        validar_cita_para_asignacion(cita)

    # Determinar qué requisitos asignar
    if requisitos_a_asignar is None:
        nombres_requisitos = obtener_requisitos_por_visa(solicitante.tipo_visa)
    else:
        # Filtrar contra requisitos cargados si se proporcionan
        if requisitos_cargados:
            nombres_requisitos = filtrar_requisitos_disponibles(
                requisitos_a_asignar,
                requisitos_cargados
            )
        else:
            nombres_requisitos = requisitos_a_asignar

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


def marcar_cita_exitosa(solicitante: Solicitante) -> Cita:
    """
    Marca la cita pendiente del solicitante como exitosa.

    Args:
        solicitante: El solicitante cuya cita se marcará como exitosa.

    Returns:
        La cita actualizada.

    Raises:
        ValidationError: Si no hay cita pendiente.
    """
    cita = obtener_cita_pendiente(solicitante)
    cita.marcar_como_exitosa()
    return cita


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
