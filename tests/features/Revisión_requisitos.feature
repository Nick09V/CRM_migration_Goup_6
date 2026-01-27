# Created by nickv at 24/1/2026
# language: es
Característica: Validación de documentos
  Como agente de migración
  Quiero revisar los documentos de un solicitante
  Para confirmar su validez y gestionar correcciones

  Antecedentes:
    Dado que existe un documento pendiente por revisar


  Escenario: Aprobación de un documento
    Cuando el agente marca como apruebado el documento
    Entonces el documento queda marcado como "revisado" sin observaciones
    Y el solicitante es notificado de la aprobación


  Escenario: Aprobación de un documento final
    Dado que existe un unico documento por aprobar
    Cuando el agente aprueba el documento
    Entonces el documento queda marcado como revisado sin observaciones
    Y se notifica al solicitante sobre la aprobación
    Y la carpeta queda marcado como aprobada


  Escenario: Rechazo de un documento
    Cuando el agente rechaza el documento
    Y escribe las razones del rechazo
    Entonces el sistema notifica al solicitante las razones del rechazo
    Y se habilita la carga del documento
