from behave import *

use_step_matcher("re")


@step("que el solicitante no tiene una cita")
def step_impl(context):
    """
    :type context: behave.runner.Context
    """
    raise NotImplementedError(u'STEP: Dado que el solicitante no tiene una cita')


@step("el solicitante selecciona un horario")
def step_impl(context):
    """
    :type context: behave.runner.Context
    """
    raise NotImplementedError(u'STEP: Cuando el solicitante selecciona un horario')


@step("el sistema agenda la cita con un agente disponible en dicho horario")
def step_impl(context):
    """
    :type context: behave.runner.Context
    """
    raise NotImplementedError(u'STEP: Entonces el sistema agenda la cita con un agente disponible en dicho horario')


@step("la cita queda pendiente para su resolución")
def step_impl(context):
    """
    :type context: behave.runner.Context
    """
    raise NotImplementedError(u'STEP: Y la cita queda pendiente para su resolución')