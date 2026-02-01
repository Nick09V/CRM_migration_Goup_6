# Created by nickv at 27/1/2026
# language: es
Característica: Gestión del estado de carpetas migratorias
  Como agente de migración
  Quiero administrar el estado de las carpetas según el avance y resultado del proceso
  Para controlar el resultado final de los trámites migratorios


  Escenario: Carpeta aprobada cuando todos los documentos están validados
    Dado que todos los documentos del solicitante están en estado aprobado
    Cuando el sistema verifica la carpeta del solicitante
    Entonces la carpeta queda en estado aprobada


  Escenario: Carpeta cerrada por visa aprobada
    Dado que la carpeta del solicitante está en estado aprobada
    Y el consulado aprueba la visa
    Cuando el agente registra el resultado de la visa
    Entonces la carpeta queda en estado cerrada aceptada


  Escenario: Carpeta cerrada por visa rechazada
    Dado que la carpeta del solicitante está en estado aprobada
    Y el consulado rechaza la visa
    Cuando el agente registra el motivo del rechazo
    Entonces la carpeta queda en estado cerrada rechazada
    Y se registra la observación del rechazo
