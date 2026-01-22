# -*- coding: utf-8 -*-
# Steps skeletons for behave-django. Rellena las implementaciones según tu lógica.

from behave import given, when, then

# -----------------------------
# Dominio: Citas (@citas)
# -----------------------------

@given('que el solicitante no tiene una cita activa')
def step_impl(context):
    pass

@given('existen agentes disponibles')
def step_impl(context):
    pass

@when('el solicitante selecciona un horario disponible')
@when('el solicitante agenda una cita')
def step_impl(context):
    pass

@then('el sistema registra la cita')
def step_impl(context):
    pass

@then('asigna automáticamente un agente disponible')
def step_impl(context):
    pass

@then('la cita queda en estado "pendiente"')
def step_impl(context):
    pass

@given('que existen varios agentes disponibles')
def step_impl(context):
    pass

@given('cada agente tiene distinta cantidad de citas pendientes')
def step_impl(context):
    pass

@then('el sistema asigna el agente con menor cantidad de citas pendientes')
def step_impl(context):
    pass

@given('que el solicitante ya tiene una cita pendiente')
def step_impl(context):
    pass

@when('intenta agendar una nueva cita')
def step_impl(context):
    pass

@then('el sistema rechaza el agendamiento')
def step_impl(context):
    pass

@then('muestra un mensaje indicando que ya posee una cita activa')
def step_impl(context):
    pass

# Cancelación
@given('que el solicitante tiene una cita pendiente')
def step_impl(context):
    pass

@when('solicita cancelar la cita')
@when('intenta cancelar una cita')
@when('intenta cancelar la cita')
def step_impl(context):
    pass

@then('el sistema elimina la cita')
def step_impl(context):
    pass

@then('el solicitante queda sin cita asignada')
def step_impl(context):
    pass

@then('el agente decrementa su cantidad de citas pendientes')
def step_impl(context):
    pass

@given('que el solicitante no tiene ninguna cita activa')
def step_impl(context):
    pass

@then('el sistema rechaza la acción')
def step_impl(context):
    pass

@then('muestra un mensaje indicando que no existe una cita que cancelar')
def step_impl(context):
    pass

@given('que el solicitante tiene una cita próxima')
def step_impl(context):
    pass

@given('el tiempo mínimo para cancelar ya expiró')
def step_impl(context):
    pass

@then('el sistema rechaza la cancelación')
def step_impl(context):
    pass

@then('notifica al solicitante la restricción')
def step_impl(context):
    pass

# Reprogramación
@given('existen horarios disponibles')
def step_impl(context):
    pass

@when('selecciona un nuevo horario')
@when('selecciona el nuevo horario')
@when('selecciona un horario ocupado')
def step_impl(context):
    pass

@then('el sistema actualiza la fecha y hora de la cita')
def step_impl(context):
    pass

@then('mantiene el agente asignado')
def step_impl(context):
    pass

@then('el sistema rechaza la reprogramación')
def step_impl(context):
    pass

@then('muestra un mensaje indicando que el horario no está disponible')
def step_impl(context):
    pass

@given('el nuevo horario no está disponible para el agente actual')
def step_impl(context):
    pass

@then('el sistema reasigna la cita a otro agente disponible')
def step_impl(context):
    pass

# -----------------------------
# Dominio: Documentos (@documentos)
# -----------------------------

@given('que el repositorio de documentos está disponible y vacío')
def step_impl(context):
    pass

@given('los estados de revisión permitidos son: pendiente, revisado, faltante')
def step_impl(context):
    pass

@given('los tipos de visa soportados son: estudiantil, trabajo, residencial')
def step_impl(context):
    pass

@given('que un solicitante requiere una visa del tipo {tipo_visa}')
def step_impl(context, tipo_visa):
    pass

@given('tiene registrado que debe subir los siguientes documentos: {documentos}')
def step_impl(context, documentos):
    pass

@when('el solicitante sube sus documentos al repositorio')
def step_impl(context):
    pass

@then('los documentos se guardan en una carpeta')
def step_impl(context):
    pass

@then('la carpeta tiene de nombre {cedula_solicitante}')
def step_impl(context, cedula_solicitante):
    pass

@then('esa carpeta se clasifica dentro de la carpeta {tipo_visa}')
def step_impl(context, tipo_visa):
    pass

@then('la carpeta se marca como expediente abierto para revisión')
def step_impl(context):
    pass

@then('todos los documentos se marcan como pendientes por revisar')
def step_impl(context):
    pass

@when('el solicitante solo sube los documentos: {documentos_subidos}')
def step_impl(context, documentos_subidos):
    pass

@then('la carpeta se marca como expediente no completado')
def step_impl(context):
    pass

@then('los documentos {documentos_subidos} se marcan como pendientes por revisar')
def step_impl(context, documentos_subidos):
    pass

@then('el resto de documentos se mantienen como faltantes por subir')
def step_impl(context):
    pass

@given('ha subido los documentos {documentos_subidos}')
def step_impl(context, documentos_subidos):
    pass

@when('el solicitante sube los documentos faltantes')
def step_impl(context):
    pass

@then('los documentos se guardan en la carpeta con ruta {tipo_visa}/{cedula_solicitante}')
def step_impl(context, tipo_visa, cedula_solicitante):
    pass

@then('los documentos faltantes se marcan como pendientes por revisar')
def step_impl(context):
    pass

