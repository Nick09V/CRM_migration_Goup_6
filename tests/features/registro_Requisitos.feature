# Created by nickv at 21/1/2026
# language: es


@documentos
Característica: Registro de requisitos migratorios
  Como agente de migración
  Quiero asignar los requisitos del solicitante
  Para monitorear su proceso migratorio


  Esquema del escenario: Registro de requisitos migratorios según tipo de visa
    Dado que se tiene una cita pendiente
    Y que el agente ha registrado que el cliente necesita la visa <tipo_visa>
    Y se tienen los siguientes requisitos cargados
      | requisitos_cargado  |
      | ci                  |
      | carta aceptación    |
      | solvencia económica |
      | oferta laboral      |
      | experiencia         |
      | antecedentes        |
      | sustento económico  |
      | seguro médico       |

    Entonces el agente asigna los siguientes requisitos al cliente "<requisitos>"
    Y los documentos quedan como pendientes por subir
    Y la cita se marca como exitosa

    Ejemplos:
      | tipo_visa   | requisitos                                    |
      | estudiantil | ci, carta aceptación, solvencia económica     |
      | trabajo     | ci, oferta laboral, experiencia, antecedentes |
      | residencial | ci, sustento económico, seguro médico         |