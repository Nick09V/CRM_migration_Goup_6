# Created by nickv at 21/1/2026
# language: es

@ready
@citas
Característica: Gestión de citas migratorias
  Como solicitante
  Quiero gestionar mis citas migratorias
  Para agendar, reprogramar o cancelar según mis necesidades


  # ==================== Agendamiento de citas ====================

  Escenario: Agendamiento exitoso de cita
    Dado que el solicitante no tiene una cita
    Cuando el solicitante selecciona un horario
    Entonces el sistema agenda la cita con un agente disponible en dicho horario
    Y la cita queda pendiente para su resolución


  Escenario: Intento de agendar con cita existente
    Dado que el solicitante ya tiene una cita pendiente
    Cuando intenta agendar una nueva cita
    Entonces el sistema rechaza el agendamiento
    Y se le notifica que debe cancelar una cita antes de agendar una nueva


  # ==================== Reprogramación de citas ====================

  Escenario: Reprogramación a un nuevo horario dentro del tiempo disponible
    Dado que el solicitante tiene una cita pendiente
    Y faltan más de dos días para la cita
    Cuando el solicitante selecciona un nuevo horario disponible
    Entonces el sistema actualiza la fecha y hora de la cita
    Y el horario del agente anterior queda disponible para otro agendamiento


  Escenario: Reprogramación fuera del tiempo permitido
    Dado que faltan dos días para la cita
    Cuando el solicitante intenta reprogramar la cita
    Entonces el sistema rechaza la reprogramación
    Y se notifica que no se pudo hacer el reagendamiento


  # ==================== Cancelación de citas ====================

  Escenario: Cancelación exitosa de cita
    Dado que el solicitante tiene una cita pendiente
    Cuando solicita cancelar la cita
    Entonces el sistema elimina la cita
    Y el solicitante queda sin cita asignada
    Y el horario del agente queda disponible para otro agendamiento


  Escenario: Cancelación fuera del tiempo permitido
    Dado que el solicitante tiene una cita pendiente
    Y que faltan dos días para la cita
    Cuando intenta cancelar la cita
    Entonces el sistema rechaza la cancelación
    Y notifica al solicitante la restricción
