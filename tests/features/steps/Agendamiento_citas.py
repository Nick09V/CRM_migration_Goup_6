from behave import *
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from migration.models import Agente, Cita
from migration.services.scheduling import agendar_cita, SolicitudAgendamiento
from faker import Faker

use_step_matcher("re")
faker = Faker("es_ES")


@step("que el solicitante no tiene una cita")
def step_impl(context):
    # Genera un nombre de cliente si no existe
    context.cliente = getattr(context, "cliente", None) or faker.name()
    Cita.objects.filter(cliente=context.cliente, estado=Cita.ESTADO_PENDIENTE).delete()
    # Verifica que efectivamente no existan pendientes
    assert not Cita.objects.filter(cliente=context.cliente, estado=Cita.ESTADO_PENDIENTE).exists()


@step("el solicitante selecciona un horario")
def step_impl(context):
    # Selecciona hoy a las 9:00 con zona activa
    now = dj_timezone.now()
    naive = dj_timezone.datetime(year=now.year, month=now.month, day=now.day, hour=9, minute=0)
    inicio = dj_timezone.make_aware(naive)
    context.inicio = inicio

    Agente.objects.get_or_create(nombre="Agente A", defaults={"activo": True})
    Agente.objects.get_or_create(nombre="Agente B", defaults={"activo": True})
    # Verifica que hay agentes activos disponibles
    assert Agente.objects.filter(activo=True).count() >= 2


@step("el sistema agenda la cita con un agente disponible en dicho horario")
def step_impl(context):
    req = SolicitudAgendamiento(cliente=context.cliente, inicio=context.inicio)
    context.cita = agendar_cita(req)
    # Verifica que la cita tenga agente y que el agente no tenga otra cita en el mismo inicio
    assert context.cita.agente is not None
    assert not Cita.objects.filter(agente=context.cita.agente, inicio=context.inicio).exclude(pk=context.cita.pk).exists()


@step("la cita queda pendiente para su resolución")
def step_impl(context):
    cita = context.cita
    assert cita.estado == Cita.ESTADO_PENDIENTE
    assert cita.fin == cita.inicio + dj_timezone.timedelta(hours=1)
    # La hora de inicio debe estar en [8, 12)
    hora_local = dj_timezone.localtime(cita.inicio).hour
    assert 8 <= hora_local < 12


# Pasos adicionales del segundo escenario
@step("que el solicitante ya tiene una cita pendiente")
def step_impl(context):
    context.cliente = faker.name()
    Agente.objects.get_or_create(nombre="Agente A", defaults={"activo": True})
    Agente.objects.get_or_create(nombre="Agente B", defaults={"activo": True})
    now = dj_timezone.now()
    naive = dj_timezone.datetime(year=now.year, month=now.month, day=now.day, hour=10)
    inicio = dj_timezone.make_aware(naive)
    context.inicio = inicio
    agente = Agente.objects.filter(activo=True).first()
    Cita.objects.update_or_create(
        cliente=context.cliente,
        estado=Cita.ESTADO_PENDIENTE,
        defaults={
            "agente": agente,
            "inicio": inicio,
            "fin": inicio + dj_timezone.timedelta(hours=1),
        },
    )
    # Verificar que existe la cita pendiente inicial
    assert Cita.objects.filter(cliente=context.cliente, estado=Cita.ESTADO_PENDIENTE, inicio=inicio).exists()


@step("intenta agendar una nueva cita")
def step_impl(context):
    context.error = None
    try:
        now = dj_timezone.now()
        naive = dj_timezone.datetime(year=now.year, month=now.month, day=now.day, hour=11)
        nuevo_inicio = dj_timezone.make_aware(naive)
        req = SolicitudAgendamiento(cliente=context.cliente, inicio=nuevo_inicio)
        agendar_cita(req)
    except DjValidationError as e:
        context.error = e


@step("el sistema rechaza el agendamiento")
def step_impl(context):
    assert context.error is not None


@step("se le notifica que debe cancelar una cita antes de agendar una nueva")
def step_impl(context):
    assert any("ya tiene una cita pendiente" in msg for msg in context.error.messages)


# Paso adicional para validar asignación a distinto agente en mismo horario
@step("si dos clientes agendan en el mismo horario se asignan a agentes distintos")
def step_impl(context):
    # Primer cliente
    cliente1 = faker.name()
    Cita.objects.filter(cliente=cliente1).delete()
    req1 = SolicitudAgendamiento(cliente=cliente1, inicio=context.inicio)
    cita1 = agendar_cita(req1)
    # Segundo cliente en mismo horario
    cliente2 = faker.name()
    Cita.objects.filter(cliente=cliente2).delete()
    req2 = SolicitudAgendamiento(cliente=cliente2, inicio=context.inicio)
    cita2 = agendar_cita(req2)
    # Validar agentes distintos
    assert cita1.agente != cita2.agente
    # Y que no exista doble asignación para un mismo agente en ese inicio
    for agente in Agente.objects.filter(activo=True):
        assert Cita.objects.filter(agente=agente, inicio=context.inicio).count() <= 1
