# Created by nickv at 24/1/2026
# language: es
Característica: Validación y control de documentos migratorios
  Para reducir rechazos y reprocesos en trámites migratorios
  Como agencia migratoria
  Quiero validar los documentos de los solicitantes y gestionar observaciones

  Antecedentes:
    Dado que existe un documento pendiente por revisar


  Escenario: Aprobación de un documento
    Cuando el agente marca como aprobado el documento
    Entonces el documento queda marcado como "revisado" sin observaciones
    Y el solicitante es notificado de la aprobación


  Escenario: Rechazo de un documento
    Cuando el agente rechaza el documento
    Y escribe las razones del rechazo
    Entonces el sistema notifica al solicitante las razones del rechazo
    Y se habilita la carga del documento
