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
    Y mantiene el agente asignado


  Escenario: Reprogramación a horario no disponible
  Dado que el solicitante tiene una cita pendiente
  Cuando selecciona un horario ocupado
  Entonces el sistema rechaza la reprogramación
    Y muestra un mensaje indicando que el horario no está disponible


  Escenario: Reprogramación con cambio de agente
  Dado que el solicitante tiene una cita pendiente
  Y el nuevo horario no está disponible para el agente actual
  Cuando selecciona el nuevo horario
  Entonces el sistema reasigna la cita a otro agente disponible
