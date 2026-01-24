# Created by nickv at 21/1/2026
# language: es

@citas
Característica: Reprogramación de citas migratorias
  Como solicitante
  Quiero reprogramar una cita
  Para cambiar el horario asignado


  Escenario: Reprogramación a un nuevo horario disponible
  Dado que el solicitante tiene una cita pendiente
    Y existen horarios disponibles
  Cuando selecciona un nuevo horario
  Entonces el sistema actualiza la fecha y hora de la cita
    Y el horario del agente anterior queda disponible para otro agendamiento




