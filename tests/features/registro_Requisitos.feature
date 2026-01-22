# Created by nickv at 21/1/2026
# language: es


@documentos
Característica: Registro de requisitos migratorios
  Como agente de migración
  Quiero registrar los requisitos del solicitante
  Para iniciar su proceso migratorio


  Escenario: Registro exitoso de requisitos migratorios
    Dado que el solicitante tiene una cita pendiente
    Cuando el agente registra el tipo de visa
      Y registra la lista de requisitos
    Entonces el sistema guarda los requisitos
      Y la cita queda marcada como completada


  Escenario: Registro incompleto de requisitos
    Dado que el solicitante tiene una cita pendiente
    Cuando el agente no registra todos los requisitos obligatorios
    Entonces el sistema rechaza el registro
      Y muestra los requisitos faltantes


  Escenario: Registro sin cita asociada
    Dado que el solicitante no tiene una cita pendiente
    Cuando el agente intenta registrar requisitos
    Entonces el sistema rechaza la acción
      Y notifica que no existe una cita válida
