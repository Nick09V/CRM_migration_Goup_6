from __future__ import annotations
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from migration.models import (
    Solicitante,
    Requisito,
    Cita,
    CatalogoRequisito,
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
    requisitos = REQUISITOS_POR_VISA.get(tipo_visa)
    if requisitos is None:
        raise ValidationError(f"Tipo de visa '{tipo_visa}' no válido.")
    return requisitos


def registrar_tipo_visa(solicitante: Solicitante, tipo_visa: str) -> Solicitante:
    # Validar que el tipo de visa sea válido
    obtener_requisitos_por_visa(tipo_visa)

    solicitante.tipo_visa = tipo_visa
    solicitante.save()
    return solicitante


def obtener_cita_pendiente(solicitante: Solicitante) -> Cita:
    cita = solicitante.citas.filter(estado=Cita.ESTADO_PENDIENTE).first()
    if not cita:
        raise ValidationError(
            "El solicitante no tiene una cita pendiente. "
            "Debe agendar una cita antes de asignar requisitos."
        )
    return cita


def validar_cita_para_asignacion(cita: Cita) -> None:
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
    cita = obtener_cita_pendiente(solicitante)
    cita.marcar_como_exitosa()
    return cita


def verificar_requisitos_pendientes(solicitante: Solicitante) -> bool:
    requisitos = solicitante.requisitos.all()
    if not requisitos.exists():
        return False

    return all(req.estado == ESTADO_DOCUMENTO_FALTANTE for req in requisitos)


def obtener_catalogo_requisitos() -> list[CatalogoRequisito]:
    return list(CatalogoRequisito.obtener_requisitos_activos())


def asignar_requisitos_dinamico(
    solicitante: Solicitante,
    tipo_visa: str,
    requisitos_seleccionados: list[int],
    validar_fecha: bool = False
) -> ResultadoRegistroRequisitos:
    if not requisitos_seleccionados:
        raise ValidationError(
            "Debe seleccionar al menos un requisito para el solicitante."
        )

    # Registrar el tipo de visa
    solicitante.tipo_visa = tipo_visa
    solicitante.save()

    # Obtener los requisitos del catálogo
    catalogo_requisitos = CatalogoRequisito.objects.filter(
        id__in=requisitos_seleccionados,
        activo=True
    )

    if not catalogo_requisitos.exists():
        raise ValidationError(
            "Los requisitos seleccionados no son válidos o no están activos."
        )

    # Eliminar requisitos previos del solicitante (si se está reasignando)
    # Solo eliminar los que no tienen documentos asociados
    requisitos_sin_documentos = solicitante.requisitos.filter(documentos__isnull=True)
    requisitos_sin_documentos.delete()

    requisitos_creados = []

    for catalogo_req in catalogo_requisitos:
        requisito, created = Requisito.objects.get_or_create(
            solicitante=solicitante,
            nombre=catalogo_req.nombre,
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


def obtener_requisitos_sugeridos_por_visa(tipo_visa: str) -> list[str]:
    return REQUISITOS_POR_VISA.get(tipo_visa, [])

