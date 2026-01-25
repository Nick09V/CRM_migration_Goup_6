# -*- coding: utf-8 -*-
"""
Steps para la caracteristica de Registro de requisitos migratorios.
Implementa los pasos BDD para los escenarios de registro de requisitos.
"""
from behave import given, then

from migration.models import (
    Solicitante,
    ESTADO_DOCUMENTO_FALTANTE,
)
from migration.services.requisitos import (
    registrar_tipo_visa,
    asignar_requisitos,
    verificar_requisitos_pendientes,
)
from faker import Faker


faker = Faker("es_ES")


# ==================== Funciones auxiliares ====================


def crear_solicitante() -> Solicitante:
    """
    Crea un nuevo solicitante con datos aleatorios.

    Returns:
        Instancia de Solicitante guardada en la base de datos.
    """
    return Solicitante.objects.create(
        nombre=faker.name(),
        cedula=faker.unique.numerify(text="##########"),
        telefono=faker.phone_number(),
        email=faker.email()
    )


# ==================== Escenario: Registro de requisitos migratorios ====================


@given("que el agente ha reigstrado que el cliente necesita la visa {tipo_visa}")
def paso_agente_registra_tipo_visa(context, tipo_visa: str):
    """El agente registra el tipo de visa que necesita el cliente."""
    context.solicitante = crear_solicitante()
    context.tipo_visa = tipo_visa.strip()

    # Registrar el tipo de visa para el solicitante
    registrar_tipo_visa(context.solicitante, context.tipo_visa)

    # Verificar que el tipo de visa fue asignado
    context.solicitante.refresh_from_db()
    assert context.solicitante.tipo_visa == context.tipo_visa, (
        f"El tipo de visa debe ser '{context.tipo_visa}', "
        f"pero es '{context.solicitante.tipo_visa}'"
    )


@then('se asignan los siguientes requisitos al cliente "{requisitos}"')
def paso_asignar_requisitos(context, requisitos: str):
    """Se asignan los requisitos correspondientes al tipo de visa."""
    # Asignar los requisitos al solicitante
    resultado = asignar_requisitos(context.solicitante)

    assert resultado.exitoso, f"Error al asignar requisitos: {resultado.mensaje}"
    assert resultado.requisitos is not None, "No se crearon requisitos"

    # Parsear los requisitos esperados
    requisitos_esperados = [r.strip() for r in requisitos.split(",")]

    # Obtener los requisitos asignados
    requisitos_asignados = [r.nombre for r in resultado.requisitos]

    # Verificar que se asignaron los requisitos correctos
    assert len(requisitos_asignados) == len(requisitos_esperados), (
        f"Se esperaban {len(requisitos_esperados)} requisitos, "
        f"pero se asignaron {len(requisitos_asignados)}"
    )

    for req_esperado in requisitos_esperados:
        assert req_esperado in requisitos_asignados, (
            f"El requisito '{req_esperado}' no fue asignado. "
            f"Requisitos asignados: {requisitos_asignados}"
        )

    context.requisitos = resultado.requisitos


@then("los documentos quedan como pendientes por subir")
def paso_documentos_pendientes(context):
    """Los documentos quedan como pendientes por subir (estado faltante)."""
    # Verificar que todos los requisitos estan pendientes
    todos_pendientes = verificar_requisitos_pendientes(context.solicitante)
    assert todos_pendientes, "Todos los requisitos deben estar pendientes por subir"

    # Verificar estado individual de cada requisito
    for requisito in context.requisitos:
        requisito.refresh_from_db()
        assert requisito.estado == ESTADO_DOCUMENTO_FALTANTE, (
            f"El requisito '{requisito.nombre}' debe estar en estado "
            f"'{ESTADO_DOCUMENTO_FALTANTE}', pero esta en '{requisito.estado}'"
        )
        assert requisito.carga_habilitada, (
            f"La carga del requisito '{requisito.nombre}' debe estar habilitada"
        )
