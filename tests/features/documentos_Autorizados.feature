# language: es
@documentos
Característica: repositorio de documentos autoorganizado
  Como agente de migración
  Quiero que los documentos de los solicitantes se suban en un repositorio digital
  Para facilitar el seguimiento de los documentos

  Antecedentes:
    Dado los estados de revisión permitidos son: pendiente, revisado, faltante
    Y los tipos de visa soportados son: estudiantil, trabajo, residencial, turista


  Escenario: Carga inicial de un documento
    Dado que un solicitante de visa de "trabajo" no ha subido su "Pasaporte"
    Cuando sube el archivo "pasaporte_v1.pdf"
    Entonces el archivo se guarda como "Versión 1"
    Y el estado del documento cambia a "Pendiente"
    Y el sistema impide subir una nueva versión hasta que esta sea revisada


  Esquema del escenario: Carga de un documento previamente rechazado
    Dado que la versión del documento es: <version_previa>
    Y dicho documento ha sido rechazado
    Cuando el solicitante sube un documento
    Entonces el documento se guarda como versión <version_esperada>
    Y el estado queda "pendiente"

    Ejemplos:
      | version_previa | version_esperada |
      | 2              | 3                |
      | 1              | 2                |
      | 5              | 6                |