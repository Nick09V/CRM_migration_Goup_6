from behave import given, step
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError as DjValidationError
from datetime import timedelta, time

from django.contrib.auth.models import User
from migration.models import Agente, Cita, Solicitante, HORA_INICIO_ATENCION
from migration.services.scheduling import (
    agendar_cita,
    SolicitudAgendamiento,
    cancelar_cita,
    reprogramar_cita,
    calcular_dias_restantes,
    DIAS_MINIMOS_CANCELACION,
    DIAS_MINIMOS_REPROGRAMACION, validar_tiempo_reprogramacion, validar_tiempo_cancelacion,
)
from faker import Faker

faker = Faker("es_ES")


def obtener_proximo_dia_laboral():
    fecha = dj_timezone.localtime(dj_timezone.now()).date() + timedelta(days=1)

    # Si cae domingo, avanzar al lunes
    while fecha.weekday() == 6:  # 6 = domingo
        fecha += timedelta(days=1)

    return fecha


def obtener_dia_laboral_con_anticipacion(dias_anticipacion: int):
    fecha = dj_timezone.localtime(dj_timezone.now()).date() + timedelta(days=dias_anticipacion)

    # Si cae domingo, avanzar al lunes
    # while fecha.weekday() == 6:  # 6 = domingo
    #     fecha += timedelta(days=1)

    return fecha


def crear_horario_valido(hora=9):
    fecha_laboral = obtener_proximo_dia_laboral()
    horario_naive = dj_timezone.datetime.combine(fecha_laboral, time(hora, 0))
    return dj_timezone.make_aware(horario_naive)


def crear_horario_con_anticipacion(dias_anticipacion: int, hora: int = 9):
    fecha_laboral = obtener_dia_laboral_con_anticipacion(dias_anticipacion)
    horario_naive = dj_timezone.datetime.combine(fecha_laboral, time(hora, 0))
    return dj_timezone.make_aware(horario_naive)


def crear_solicitante():
    return Solicitante.objects.create(
        nombre=faker.name(),
        telefono=faker.phone_number(),
        email=faker.email()
    )


def obtener_o_crear_agentes():
    # Crear usuario y agente A
    user_a, _ = User.objects.get_or_create(
        username="agente_a",
        defaults={"password": "test_password_a"}
    )
    Agente.objects.get_or_create(
        nombre="Agente A",
        defaults={"usuario": user_a, "activo": True}
    )

    # Crear usuario y agente B
    user_b, _ = User.objects.get_or_create(
        username="agente_b",
        defaults={"password": "test_password_b"}
    )
    Agente.objects.get_or_create(
        nombre="Agente B",
        defaults={"usuario": user_b, "activo": True}
    )

    return Agente.objects.filter(activo=True)


def obtener_o_crear_agente():
    agente, _ = Agente.objects.get_or_create(
        nombre="Agente Reprogramaciones",
        defaults={"activo": True}
    )
    return agente


def crear_cita_pendiente(dias_anticipacion: int, hora: int = 9):
    solicitante = crear_solicitante()
    agente = obtener_o_crear_agente()
    horario = crear_horario_con_anticipacion(dias_anticipacion, hora)

    cita = Cita(
        solicitante=solicitante,
        agente=agente,
        inicio=horario,
        estado=Cita.ESTADO_PENDIENTE,
    )
    cita.save()
    return cita


# ==================== Agendamiento: Escenario 1 - Agendamiento exitoso ====================

@step("que el solicitante no tiene una cita")
def paso_solicitante_sin_cita(context):
    """Prepara un solicitante sin citas pendientes."""
    context.solicitante = crear_solicitante()

    # Verificar que no tenga citas pendientes
    tiene_pendiente = context.solicitante.tiene_cita_pendiente()
    assert not tiene_pendiente, "El solicitante no debería tener citas pendientes"


@step("que existen agentes disponibles")
def paso_existen_agente(context):
    # Asegurar que existan agentes
    agentes = obtener_o_crear_agentes()
    assert agentes.count() >= 1, "Debe existir al menos un agente activo"


@step("el solicitante selecciona un horario a las {hora:d}:00")
def paso_seleccionar_horario_especifico(context, hora):
    """El solicitante selecciona un horario específico para la cita."""
    context.hora_seleccionada = hora
    #print(f"esta es la hora que se pasa: {context.hora_seleccionada}")

    try:
        context.inicio = crear_horario_valido(hora=hora)
        solicitud = SolicitudAgendamiento(
            solicitante=context.solicitante,
            inicio=context.inicio
        )
        context.cita = agendar_cita(solicitud)
        context.error = None
    except DjValidationError as error:
        context.error = error
        context.cita = None


@step("el sistema agenda la cita con un agente disponible en dicho horario")
def paso_agendar_cita(context):
    """El sistema asigna la cita a un agente disponible."""
    assert context.error is None, f"No debería haber error al agendar: {context.error}"
    assert context.cita is not None, "La cita debe haberse creado"

    # Verificar que se asignó un agente
    assert context.cita.agente is not None, "La cita debe tener un agente asignado"

    # Verificar que el agente no tenga otra cita en el mismo horario
    citas_mismo_horario = Cita.objects.filter(
        agente=context.cita.agente,
        inicio=context.inicio,
        estado=Cita.ESTADO_PENDIENTE
    ).exclude(pk=context.cita.pk)

    assert not citas_mismo_horario.exists(), (
        "El agente no debe tener otra cita en el mismo horario"
    )


@step("la cita queda pendiente para su resolución")
def paso_verificar_cita_pendiente(context):
    """Verifica que la cita esté correctamente agendada."""
    cita = context.cita

    # Verificar estado pendiente usando metodo encapsulado
    assert cita.esta_pendiente(), "La cita debe estar pendiente"

# ==================== Agendamiento: Escenario 2 - Intento con cita existente ====================

@step("que el solicitante ya tiene una cita pendiente")
def paso_solicitante_con_cita_pendiente(context):
    """Prepara un solicitante que ya tiene una cita pendiente."""
    context.solicitante = crear_solicitante()
    agentes = obtener_o_crear_agentes()
    agente = agentes.first()

    # Crear una cita pendiente para el solicitante
    inicio_cita_existente = crear_horario_valido(hora=10)
    context.cita_existente = Cita(
        solicitante=context.solicitante,
        agente=agente,
        inicio=inicio_cita_existente,
        estado=Cita.ESTADO_PENDIENTE
    )
    context.cita_existente.save()

    # Verificar que la cita pendiente existe
    assert context.solicitante.tiene_cita_pendiente(), (
        "El solicitante debe tener una cita pendiente"
    )


@step("intenta agendar una nueva cita")
def paso_intentar_nueva_cita(context):
    """El solicitante intenta agendar una segunda cita."""
    context.error = None

    try:
        # Intentar agendar en un horario diferente
        nuevo_inicio = crear_horario_valido(hora=11)
        solicitud = SolicitudAgendamiento(
            solicitante=context.solicitante,
            inicio=nuevo_inicio
        )
        agendar_cita(solicitud)
    except DjValidationError as error:
        context.error = error


@step("el sistema rechaza el agendamiento")
def paso_verificar_rechazo(context):
    """Verifica que el sistema rechazó la solicitud."""
    assert context.error is not None, (
        "El sistema debería haber rechazado el agendamiento"
    )


@step("se le notifica que debe cancelar una cita antes de agendar una nueva")
def paso_verificar_mensaje_error(context):
    """Verifica que se muestre el mensaje de error apropiado."""
    mensaje_error = str(context.error)

    palabras_clave = ["ya tiene una cita pendiente", "cancelar"]
    contiene_mensaje = any(
        palabra.lower() in mensaje_error.lower()
        for palabra in palabras_clave
    )

    assert contiene_mensaje, (
        f"El mensaje debe indicar que ya tiene cita pendiente. "
        f"Mensaje recibido: {mensaje_error}"
    )


@step("se le notifica que las citas solo se permiten entre las 08:00 y 12:00")
def paso_notifica_horario_invalido(context):
    """Verifica que se notifique que el horario está fuera del permitido."""
    assert context.error is not None, "Debe haber un error de validación"




# ==================== Reprogramación: Escenario 1 - Reprogramación exitosa ====================

@step("que el solicitante tiene una cita pendiente")
def paso_solicitante_tiene_cita_pendiente(context):
    """Prepara un solicitante con una cita pendiente con suficiente anticipación."""
    # Crear cita con 5 días de anticipación (más de los 3 requeridos)
    context.cita = crear_cita_pendiente(dias_anticipacion=6)
    context.solicitante = context.cita.solicitante
    context.agente_original = context.cita.agente
    context.horario_original = context.cita.inicio


@step("faltan más de dos días para la cita")
def paso_faltan_mas_de_dos_dias(context):
    """Verifica que faltan más de 2 días para la cita."""
    dias_restantes = calcular_dias_restantes(context.cita)
    context.error = None
    try:
        validar_tiempo_reprogramacion(context.cita)

    except DjValidationError as error:
        context.error = error

    assert context.error is None, (
        f"La cita debe tener más de 2 días de anticipación. "
        f"Días restantes: {dias_restantes}"
    )


@step("el solicitante selecciona un nuevo horario a las {hora:d}:00 con {dias:d} días de anticipación")
def paso_solicitante_selecciona_horario_nuevo(context, hora, dias):
    """El solicitante selecciona un nuevo horario para reprogramar."""
    context.hora_nueva_seleccionada = hora
    # Seleccionar un nuevo horario con la hora especificada (6 días de anticipación)
    context.nuevo_horario = crear_horario_con_anticipacion(dias_anticipacion=dias, hora=hora)

    try:
        context.resultado = reprogramar_cita(context.cita, context.nuevo_horario)
        context.error = None
    except DjValidationError as e:
        context.resultado = None
        context.error = e


@step("el sistema actualiza la fecha y hora de la cita")
def paso_sistema_actualiza_cita(context):
    """Verifica que la cita fue actualizada correctamente."""
    assert context.error is None, f"Error inesperado: {context.error}"
    assert context.resultado is not None, "No se obtuvo resultado de reprogramación"
    assert context.resultado.exitoso is True, "La reprogramación debió ser exitosa"

    # Refrescar la cita desde la base de datos
    cita_actualizada = Cita.objects.get(pk=context.cita.pk)

    assert cita_actualizada.inicio == context.nuevo_horario, (
        f"El horario de la cita debió actualizarse. "
        f"Esperado: {context.nuevo_horario}, Actual: {cita_actualizada.inicio}"
    )


@step("el horario anterior queda disponible para otro agendamiento")
def paso_horario_agente_disponible(context):
    """Verifica que el horario anterior quedó liberado."""
    # Verificar que no existe ninguna cita pendiente en el horario original
    citas_en_horario_original = Cita.objects.filter(
        inicio=context.horario_original,
        estado=Cita.ESTADO_PENDIENTE
    ).count()

    assert citas_en_horario_original == 0, (
        f"El horario original debería estar disponible. "
        f"Se encontraron {citas_en_horario_original} citas en ese horario."
    )


# ==================== Reprogramación: Escenario 2 - Fuera del tiempo ====================

@step("que faltan dos días para la cita")
def paso_faltan_dos_dias_reprogramacion(context):
    """Prepara una cita que tiene exactamente 2 días de anticipación."""
    context.cita = crear_cita_pendiente(dias_anticipacion=5)
    context.solicitante = context.cita.solicitante
    context.agente_original = context.cita.agente
    context.horario_original = context.cita.inicio

    dias_restantes = calcular_dias_restantes(context.cita)


    puede_reprogramar = validar_tiempo_reprogramacion(context.cita)

    assert puede_reprogramar, (
        f"La cita debe tener exactamente 2 días de anticipación. "
        f"Días restantes: {dias_restantes}"
    )


@step("el solicitante intenta reprogramar la cita")
def paso_solicitante_intenta_reprogramar(context):
    """Intenta reprogramar la cita cuando no hay suficiente anticipación."""
    nuevo_horario = crear_horario_con_anticipacion(dias_anticipacion=7, hora=10)

    try:
        context.resultado = reprogramar_cita(context.cita, nuevo_horario)
        context.error = None
    except DjValidationError as e:
        context.resultado = None
        context.error = e


@step("el sistema rechaza la reprogramación")
def paso_sistema_rechaza_reprogramacion(context):
    """Verifica que el sistema rechazó la reprogramación."""
    assert context.error is not None, (
        "El sistema debió rechazar la reprogramación con un error de validación"
    )
    assert context.resultado is None, "No debió haber resultado exitoso"

    # Verificar que la cita original no fue modificada
    cita_sin_cambios = Cita.objects.get(pk=context.cita.pk)
    assert cita_sin_cambios.inicio == context.horario_original, (
        "La cita no debió ser modificada al rechazar la reprogramación"
    )


@step("se notifica que el horario no está dentro del horario de atención")
def paso_notifica_horario_reprogramacion_invalido(context):
    """Verifica que se notifique que el horario de reprogramación está fuera del permitido."""
    assert context.error is not None, "Debe haber un error de validación"

    mensaje_error = str(context.error)
    palabras_clave = ["08", "12", "citas", "solo"]
    contiene_mensaje = any(
        palabra.lower() in mensaje_error.lower()
        for palabra in palabras_clave
    )

    assert contiene_mensaje, (
        f"El mensaje debe indicar el horario de atención permitido. "
        f"Mensaje recibido: {mensaje_error}"
    )


@step("se notifica que no se pudo hacer el reagendamiento")
def paso_notifica_error_reprogramacion(context):
    """Verifica que se notifica correctamente el error de reprogramación."""
    assert context.error is not None, "Debió haber un error de validación"

    mensaje_error = str(context.error.message)
    assert "reprogramar" in mensaje_error.lower(), (
        f"El mensaje de error debe mencionar la reprogramación. "
        f"Mensaje recibido: {mensaje_error}"
    )
    assert str(DIAS_MINIMOS_REPROGRAMACION) in mensaje_error, (
        f"El mensaje debe mencionar los días mínimos de anticipación. "
        f"Mensaje recibido: {mensaje_error}"
    )


# ==================== Cancelación: Escenario 1 - Cancelación exitosa ====================

@step("solicita cancelar la cita")
def paso_solicita_cancelar_cita(context):
    """El solicitante solicita cancelar su cita."""
    context.error = None
    context.resultado = None

    # Guardar referencias antes de cancelar para verificaciones posteriores
    context.agente = getattr(context, 'agente_original', context.cita.agente)
    context.inicio_cita = getattr(context, 'horario_original', context.cita.inicio)

    try:
        context.resultado = cancelar_cita(context.cita)
    except DjValidationError as error:
        context.error = error


@step("el sistema elimina la cita")
def paso_sistema_elimina_cita(context):
    """Verifica que el sistema eliminó la cita."""
    assert context.error is None, (
        f"No debería haber error al cancelar: {context.error}"
    )
    assert context.resultado is not None, "Debe existir un resultado de cancelación"
    assert context.resultado.exitoso, "La cancelación debe ser exitosa"


@step("el solicitante queda sin cita asignada")
def paso_solicitante_sin_cita_asignada(context):
    """Verifica que el solicitante ya no tiene citas pendientes."""
    # Refrescar el solicitante desde la base de datos
    context.solicitante.refresh_from_db()

    tiene_cita = context.solicitante.tiene_cita_pendiente()
    assert not tiene_cita, "El solicitante no debe tener citas pendientes"


@step("el horario del agente queda disponible para otro agendamiento")
def paso_horario_disponible(context):
    """Verifica que el horario del agente quedó libre."""
    # Verificar que no existe cita pendiente para el agente en ese horario
    cita_existente = Cita.objects.filter(
        agente=context.agente,
        inicio=context.inicio_cita,
        estado=Cita.ESTADO_PENDIENTE
    ).exists()

    assert not cita_existente, (
        "El horario del agente debe estar disponible para otro agendamiento"
    )


# ==================== Cancelación: Escenario 2 - Fuera del tiempo ====================

@step("que faltan dos días para el inicio de la cita")
def paso_faltan_dos_dias_cancelacion(context):
    puede_cancelar = validar_tiempo_cancelacion(context.cita)
    dias_restantes = calcular_dias_restantes(context.cita)

    assert not puede_cancelar, (
        f"La cita debe tener menos de {DIAS_MINIMOS_CANCELACION} días de anticipación "
        f"para que la cancelación sea rechazada. Días restantes: {dias_restantes}"
    )


@step("intenta cancelar la cita")
def paso_intenta_cancelar(context):
    """El solicitante intenta cancelar su cita."""
    context.error = None
    context.resultado = None

    try:
        context.resultado = cancelar_cita(context.cita)
    except DjValidationError as e:
        context.error = e


@step("el sistema rechaza la cancelación")
def paso_sistema_rechaza_cancelacion(context):
    """Verifica que el sistema rechazó la cancelación."""
    assert context.error is not None, (
        "El sistema debería haber rechazado la cancelación"
    )

    # Verificar que la cita sigue existiendo
    cita_existe = Cita.objects.filter(pk=context.cita.pk).exists()
    assert cita_existe, "La cita debe seguir existiendo después del rechazo"


@step("que el solicitante posee una cita pendiente")
def step_impl(context):
    """Prepara un solicitante con una cita pendiente que tiene pocos días de anticipación."""
    # Crear cita con 3 días de anticipación (menos de DIAS_MINIMOS_CANCELACION=4)
    context.cita = crear_cita_pendiente(dias_anticipacion=5)
    context.solicitante = context.cita.solicitante
    context.agente_original = context.cita.agente
    context.horario_original = context.cita.inicio

    # Verificar que la cita pendiente existe
    assert context.solicitante.tiene_cita_pendiente(), (
        "El solicitante debe tener una cita pendiente"
    )