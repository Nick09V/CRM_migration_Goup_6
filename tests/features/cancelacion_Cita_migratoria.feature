# Created by nickv at 21/1/2026
# language: es

@citas
Característica: Cancelación de citas migratorias
  Como solicitante
  Quiero cancelar una cita
  Para liberar el horario asignado

  Antecedentes:
    Dado que el solicitante tiene una cita pendiente


  Escenario: Cancelación exitosa de cita
    Cuando solicita cancelar la cita
    Entonces el sistema elimina la cita
    Y el solicitante queda sin cita asignada
    Y el horario del agente queda disponible para otro agendamiento



  Escenario: Cancelación fuera del tiempo permitido
    Dado que faltan dos días para la cita
    Cuando intenta cancelar la cita
    Entonces el sistema rechaza la cancelación
    Y notifica al solicitante la restricción
