# Created by nickv at 21/1/2026
# language: es


@citas
Característica: Agendamiento de citas migratorias
  Como solicitante
  Quiero agendar una cita
  Para recibir asesoría migratoria


  Escenario: Agendamiento exitoso de cita
  Dado que el solicitante no tiene una cita activa
    Y existen agentes disponibles
  Cuando el solicitante selecciona un horario disponible
  Entonces el sistema registra la cita
  Y asigna automáticamente un agente disponible
  Y la cita queda en estado "pendiente"


  Escenario: Asignación automática según carga de trabajo
    Dado que existen varios agentes disponibles
      Y cada agente tiene distinta cantidad de citas pendientes
    Cuando el solicitante agenda una cita
    Entonces el sistema asigna el agente con menor cantidad de citas pendientes


  Escenario: Intento de agendar con cita existente
    Dado que el solicitante ya tiene una cita pendiente
    Cuando intenta agendar una nueva cita
    Entonces el sistema rechaza el agendamiento
      Y muestra un mensaje indicando que ya posee una cita activa
