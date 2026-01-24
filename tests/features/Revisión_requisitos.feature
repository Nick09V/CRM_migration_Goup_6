# Created by nickv at 24/1/2026
# language: es
Característica: Validación de documentos
  Como agente de migración
  Quiero revisar los documentos de un solicitante
  Para confirmar su validez y gestionar correcciones


  Escenario: Aprobación de un documento final
    Dado que existe un documento cargado por el solicitante
    Cuando el agente revisa y aprueba el documento
    Entonces el documento queda marcado como "revisado" sin observaciones
    Y el solicitante es notificado de la aprobación
    Y la carpeta queda marcado como "aprobado"


  Escenario: Aprobación de un documento
    Dado que existe un documento cargado por el solicitante
    Cuando el agente revisa y aprueba el documento
    Entonces el documento queda marcado como "revisado" sin observaciones
    Y el solicitante es notificado de la aprobación

  Escenario: Rechazo de un documento
    Dado que hay un documento cargado por el solicitante
    Cuando el agente rechaza el documento
    Y escribe las razones del rechazo
    Entonces el sistema notifica al solicitante las razones del rechazo
    Y se habilita la carga del documento
