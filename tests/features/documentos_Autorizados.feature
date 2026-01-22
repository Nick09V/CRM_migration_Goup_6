# language: es
@documentos
Característica: repositorio de documentos autoorganizado
  Como agente de migración
  Quiero que los documentos de los solicitantes se suban en un repositorio digital
  Para que se organicen de forma automática y correcta

  Antecedentes:
    Dado que el repositorio de documentos está disponible y vacío
    Y los estados de revisión permitidos son: pendiente, revisado, faltante
    Y los tipos de visa soportados son: estudiantil, trabajo, residencial

  Esquema del escenario: Organización automática de la carga inicial y total de documentos
    Dado que un solicitante requiere una visa del tipo <tipo_visa>
    Y tiene registrado que debe subir los siguientes documentos: <documentos>
    Cuando el solicitante sube sus documentos al repositorio
    Entonces los documentos se guardan en una carpeta
    Y la carpeta tiene de nombre <cedula_solicitante>
    Y esa carpeta se clasifica dentro de la carpeta <tipo_visa>
    Y la carpeta se marca como expediente abierto para revisión
    Y todos los documentos se marcan como pendientes por revisar
    Ejemplos:
      | cedula_solicitante | tipo_visa   | documentos                                                          |
      | 1720274910         | estudiantil | ci, carta aceptación, solvencia económica, certificado idioma       |
      | 1710307503         | trabajo     | ci, oferta laboral, experiencia, antecedentes, pruebas calificación |
      | 3710306563         | residencial | ci, sustento económico, seguro médico, acreditación arraigo         |


  Esquema del escenario: Organización automática de la carga inicial y parcial de documentos
    Dado que un solicitante requiere una visa del tipo <tipo_visa>
    Y tiene registrado que debe subir los siguientes documentos: <documentos>
    Cuando el solicitante solo sube los documentos: <documentos_subidos>
    Entonces los documentos se guardan en una carpeta
    Y la carpeta tiene de nombre <cedula_solicitante>
    Y esa carpeta se clasifica dentro de la carpeta <tipo_visa>
    Y la carpeta se marca como expediente no completado
    Y los documentos <documentos_subidos> se marcan como pendientes por revisar
    Y el resto de documentos se mantienen como faltantes por subir
    Ejemplos:
      | cedula_solicitante | tipo_visa   | documentos                                                          | documentos_subidos                |
      | 1720274910         | estudiantil | ci, carta aceptación, solvencia económica, certificado idioma       | ci, solvencia económica           |
      | 1710307503         | trabajo     | ci, oferta laboral, experiencia, antecedentes, pruebas calificación | oferta laboral, experiencia       |
      | 3710306563         | residencial | ci, sustento económico, seguro médico, acreditación arraigo         | sustento económico, seguro médico |


  Esquema del escenario: Organización automática de la carga de documentos faltantes
    Dado que un solicitante requiere una visa del tipo <tipo_visa>
    Y tiene registrado que debe subir los siguientes documentos: <documentos>
    Y ha subido los documentos <documentos_subidos>
    Cuando el solicitante sube los documentos faltantes
    Entonces los documentos se guardan en la carpeta con ruta <tipo_visa>/<cedula_solicitante>
    Y los documentos faltantes se marcan como pendientes por revisar
    Y la carpeta se marca como expediente abierto para revisión
    Ejemplos:
      | cedula_solicitante | tipo_visa   | documentos                                                          | documentos_subidos                |
      | 1720274910         | estudiantil | ci, carta aceptación, solvencia económica, certificado idioma       | ci, solvencia económica           |
      | 1710307503         | trabajo     | ci, oferta laboral, experiencia, antecedentes, pruebas calificación | oferta laboral, experiencia       |
      | 3710306563         | residencial | ci, sustento económico, seguro médico, acreditación arraigo         | sustento económico, seguro médico |
