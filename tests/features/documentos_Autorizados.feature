# language: es
@documentos
Característica: repositorio de documentos autoorganizado
  Como agente de migración
  Quiero que los documentos de los solicitantes se suban en un repositorio digital
  Para facilitar el seguimiento de los documentos

  Antecedentes:
    Dado que el repositorio de documentos está disponible y vacío
    Y los estados de revisión permitidos son: pendiente, revisado, faltante
    Y los tipos de visa soportados son: estudiantil, trabajo, residencial, turista


  Escenario: Carga de un documento no revisado previamente
    Dado que un solicitante requiere una visa del tipo "trabajo"
    Cuando el solicitante sube un documento
    Entonces el documento se guarda en el repositorio como versión 1
    Y el documento quedá pendiente para su revisión
    Y se bloquea la carga del documento


  Escenario: Carga de un documento rechazado
    Dado que un solicitante requiere una visa del tipo "trabajo"
    Y previamente subió el "documento"
    Cuando el solicitante sube otro "documento"
    Entonces el documento se guarda en el repositorio como versión "n"
    Y el documento quedá pendiente para su revisión
    Y se bloquea la carga del documento


  Esquema del escenario: Carga de todos los documentos
    Dado que un solicitante requiere una visa del tipo <tipo_visa>
    Y tiene registrado que debe subir los siguientes documentos: <documentos>
    Cuando el solicitante sube un documento
    Entonces los documentos se guardan en una carpeta
    Y la carpeta tiene de nombre <cedula_solicitante>
    Y los documentos deberán ser revisados por el agente

    Ejemplos:
      | cedula_solicitante | tipo_visa   | documentos                                                          |
      | 1720274910         | estudiantil | ci, carta aceptación, solvencia económica, certificado idioma       |
      | 1710307503         | trabajo     | ci, oferta laboral, experiencia, antecedentes, pruebas calificación |
      | 3710306563         | residencial | ci, sustento económico, seguro médico, acreditación arraigo         |

