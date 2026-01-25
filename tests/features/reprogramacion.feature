# Created by nickv at 21/1/2026
# language: es
@ready
@citas
Característica: Reprogramación de citas migratorias
  Como solicitante
  Quiero reprogramar una cita
  Para cambiar el horario asignado


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




