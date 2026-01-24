# CRM_migration_Goup_6

Proyecto Django con BDD (behave-django). Inicio con SQLite y servicios de dominio; futura migración a PostgreSQL/Docker sin romper código.

## Arranque rápido
- Instalar dependencias:
```
pip install -r requirements
```
- Migrar DB:
```
python manage.py migrate
```
- Ejecutar BDD:
```
python manage.py behave
```

## Estructura
- `migration/models.py`: Solicitante, Agente, Cita, SolicitudVisa, Documento.
- `migration/services/`: lógica de negocio
  - `citas.py`: agendar, cancelar, reprogramar.
  - `documentos.py`: carga_inicial, carga_parcial, cargar_faltantes.
- `tests/features/`: escenarios BDD.
- `tests/steps/steps.py`: pasos que invocan servicios.

## División de equipo
1. BDD y contratos
2. Modelos y migraciones
3. Servicios: Citas
4. Servicios: Documentos/Requisitos
5. Configuración y CI

## Postgres/Docker (futuro)
- `.env` con `DATABASE_URL` para conmutar motor.
- Docker Compose para Postgres y web.
