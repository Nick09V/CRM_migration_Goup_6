"""
Servicio de administración del sistema.
Gestiona la lógica de negocio para funcionalidades exclusivas del administrador.
"""
from __future__ import annotations
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from migration.models import (
    Agente,
    CatalogoRequisito,
    TipoVisa,
)


@dataclass
class ResultadoOperacion:
    """Representa el resultado de una operación administrativa."""
    exitoso: bool
    mensaje: str
    objeto: object = None


# ==================== Gestión de Agentes ====================

def activar_agente(agente: Agente) -> ResultadoOperacion:
    """
    Activa un agente en el sistema.

    Args:
        agente: El agente a activar.

    Returns:
        ResultadoOperacion con el estado de la operación.
    """
    if agente.activo:
        return ResultadoOperacion(
            exitoso=False,
            mensaje=f"El agente '{agente.nombre}' ya está activo.",
            objeto=agente
        )

    agente.activo = True
    agente.save(update_fields=["activo"])

    # Activar también el usuario asociado si existe
    if agente.usuario:
        agente.usuario.is_active = True
        agente.usuario.save(update_fields=["is_active"])

    return ResultadoOperacion(
        exitoso=True,
        mensaje=f"El agente '{agente.nombre}' ha sido activado exitosamente.",
        objeto=agente
    )


def desactivar_agente(agente: Agente) -> ResultadoOperacion:
    """
    Desactiva un agente en el sistema.
    El agente no podrá iniciar sesión ni ser asignado a nuevas carpetas.

    Args:
        agente: El agente a desactivar.

    Returns:
        ResultadoOperacion con el estado de la operación.
    """
    if not agente.activo:
        return ResultadoOperacion(
            exitoso=False,
            mensaje=f"El agente '{agente.nombre}' ya está inactivo.",
            objeto=agente
        )

    agente.activo = False
    agente.save(update_fields=["activo"])

    # Desactivar también el usuario asociado si existe
    if agente.usuario:
        agente.usuario.is_active = False
        agente.usuario.save(update_fields=["is_active"])

    return ResultadoOperacion(
        exitoso=True,
        mensaje=f"El agente '{agente.nombre}' ha sido desactivado. No podrá iniciar sesión.",
        objeto=agente
    )


def cambiar_estado_agente(agente: Agente) -> ResultadoOperacion:
    """
    Cambia el estado de un agente (activo <-> inactivo).

    Args:
        agente: El agente cuyo estado se cambiará.

    Returns:
        ResultadoOperacion con el estado de la operación.
    """
    if agente.activo:
        return desactivar_agente(agente)
    else:
        return activar_agente(agente)


def obtener_agentes_activos():
    """Obtiene todos los agentes activos del sistema."""
    return Agente.objects.filter(activo=True)


def obtener_todos_agentes():
    """Obtiene todos los agentes del sistema."""
    return Agente.objects.all()


# ==================== Gestión de Tipos de Visa ====================

def crear_tipo_visa(
    codigo: str,
    nombre: str,
    descripcion: str = ""
) -> ResultadoOperacion:
    """
    Crea un nuevo tipo de visa en el sistema.

    Args:
        codigo: Identificador único del tipo de visa.
        nombre: Nombre descriptivo del tipo de visa.
        descripcion: Descripción opcional del tipo de visa.

    Returns:
        ResultadoOperacion con el estado de la operación.

    Raises:
        ValidationError: Si el código o nombre ya existen.
    """
    # Normalizar el código a minúsculas sin espacios
    codigo = codigo.lower().strip().replace(" ", "_")
    nombre = nombre.strip()

    if not codigo:
        raise ValidationError("El código del tipo de visa es obligatorio.")

    if not nombre:
        raise ValidationError("El nombre del tipo de visa es obligatorio.")

    # Verificar duplicados
    if TipoVisa.objects.filter(codigo=codigo).exists():
        raise ValidationError(f"Ya existe un tipo de visa con el código '{codigo}'.")

    if TipoVisa.objects.filter(nombre__iexact=nombre).exists():
        raise ValidationError(f"Ya existe un tipo de visa con el nombre '{nombre}'.")

    tipo_visa = TipoVisa.objects.create(
        codigo=codigo,
        nombre=nombre,
        descripcion=descripcion,
        activo=True
    )

    return ResultadoOperacion(
        exitoso=True,
        mensaje=f"Tipo de visa '{nombre}' creado exitosamente.",
        objeto=tipo_visa
    )


def obtener_tipos_visa_activos():
    """Obtiene todos los tipos de visa activos."""
    return TipoVisa.obtener_tipos_activos()


def obtener_tipos_visa_choices():
    """
    Obtiene los tipos de visa activos como una lista de tuplas (codigo, nombre)
    para usar en formularios como choices.
    """
    return list(TipoVisa.objects.filter(activo=True).values_list('codigo', 'nombre'))


def obtener_todos_tipos_visa():
    """Obtiene todos los tipos de visa."""
    return TipoVisa.objects.all()


def inicializar_tipos_visa():
    """Inicializa los tipos de visa por defecto si no existen."""
    TipoVisa.inicializar_tipos_default()


# ==================== Gestión de Catálogo de Requisitos ====================

def crear_requisito_catalogo(
    nombre: str,
    descripcion: str = ""
) -> ResultadoOperacion:
    """
    Crea un nuevo requisito en el catálogo del sistema.

    Args:
        nombre: Nombre del requisito.
        descripcion: Descripción opcional del requisito.

    Returns:
        ResultadoOperacion con el estado de la operación.

    Raises:
        ValidationError: Si el nombre ya existe.
    """
    nombre = nombre.strip().lower()

    if not nombre:
        raise ValidationError("El nombre del requisito es obligatorio.")

    # Verificar duplicados
    if CatalogoRequisito.objects.filter(nombre__iexact=nombre).exists():
        raise ValidationError(f"Ya existe un requisito con el nombre '{nombre}'.")

    requisito = CatalogoRequisito.objects.create(
        nombre=nombre,
        descripcion=descripcion,
        activo=True
    )

    return ResultadoOperacion(
        exitoso=True,
        mensaje=f"Requisito '{nombre}' agregado al catálogo exitosamente.",
        objeto=requisito
    )


def obtener_catalogo_requisitos_activos():
    """Obtiene todos los requisitos activos del catálogo."""
    return CatalogoRequisito.obtener_requisitos_activos()


def obtener_requisitos_choices():
    """
    Obtiene los requisitos activos como una lista de tuplas (id, nombre)
    para usar en formularios como choices.
    """
    return [(req.id, req.nombre.title()) for req in CatalogoRequisito.objects.filter(activo=True)]


def obtener_todos_requisitos_catalogo():
    """Obtiene todos los requisitos del catálogo."""
    return CatalogoRequisito.objects.all()


def inicializar_catalogo_requisitos():
    """Inicializa el catálogo de requisitos con valores por defecto."""
    CatalogoRequisito.inicializar_catalogo()


# ==================== Inicialización del Sistema ====================

def inicializar_sistema():
    """
    Inicializa los datos base del sistema.
    Crea tipos de visa y requisitos por defecto si no existen.
    """
    with transaction.atomic():
        inicializar_tipos_visa()
        inicializar_catalogo_requisitos()
