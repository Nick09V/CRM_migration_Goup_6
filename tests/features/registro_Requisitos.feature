# Created by nickv at 21/1/2026
# language: es


@documentos
Característica: Registro de requisitos migratorios
  Como agente de migración
  Quiero asignar los requisitos del solicitante
  Para monitorear su proceso migratorio


  Esquema del escenario: Registro de requisitos migratorios según tipo de visa
    Dado que el agente ha reigstrado que el cliente necesita la visa <tipo_visa>
    Entonces se asignan los siguientes requisitos al cliente "<requisitos>"
    Y los documentos quedan como pendientes por subir

    Ejemplos:
      | tipo_visa   | requisitos                                                          |
      | estudiantil | ci, carta aceptación, solvencia económica, certificado idioma       |
      | trabajo     | ci, oferta laboral, experiencia, antecedentes, pruebas calificación |
      | residencial | ci, sustento económico, seguro médico, acreditación arraigo         |
