# Created by nickv at 21/1/2026
# language: es

@citas
Característica: Cancelación de citas migratorias
  Como solicitante
  Quiero cancelar una cita
  Para liberar el horario asignado


  Escenario: Cancelación exitosa de cita
  Dado que el solicitante tiene una cita pendiente
  Cuando solicita cancelar la cita
  Entonces el sistema elimina la cita
  Y el solicitante queda sin cita asignada
  Y el agente decrementa su cantidad de citas pendientes

#Este no se si ponerle por que podríamos caer en lo obvio osea como quiere cancelar sin cita
  Escenario: Cancelación sin cita existente
  Dado que el solicitante no tiene ninguna cita activa
  Cuando intenta cancelar una cita
  Entonces el sistema rechaza la acción
  Y muestra un mensaje indicando que no existe una cita que cancelar


  Escenario: Cancelación fuera del tiempo permitido
    Dado que el solicitante tiene una cita próxima
      Y el tiempo mínimo para cancelar ya expiró
    Cuando intenta cancelar la cita
    Entonces el sistema rechaza la cancelación
      Y notifica al solicitante la restricción
