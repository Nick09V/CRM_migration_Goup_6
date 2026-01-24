# Created by nickv at 21/1/2026
# language: es


@citas
Característica: Agendamiento de citas migratorias
  Como solicitante
  Quiero agendar una cita
  Para recibir asesoría migratoria


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
