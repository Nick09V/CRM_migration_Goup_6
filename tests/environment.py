"""
Configuración del entorno para las pruebas BDD con Behave.

ENFOQUE SIMPLIFICADO:
- Los datos de tipos de visa y requisitos se crean en los steps según sea necesario
- No hay población masiva de datos en environment.py
- Cada test crea explícitamente los datos que necesita
- Los tests son autocontenidos y claros
"""
import os
import sys


def _setup_django():
    """Configura Django si no está configurado aún."""
    import django
    from django.conf import settings

    if not settings.configured:
        # Agregar el directorio raíz del proyecto al path
        ruta_proyecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if ruta_proyecto not in sys.path:
            sys.path.insert(0, ruta_proyecto)

        # Configurar Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')
        django.setup()


# Configurar Django al cargar el módulo
_setup_django()


def before_all(context):
    """
    Se ejecuta UNA VEZ antes de todas las features.

    Con el nuevo enfoque, NO poblamos datos aquí.
    Cada test creará los datos que necesita en sus propios steps.
    """
    print("\n" + "=" * 70)
    print("[environment.py] before_all - Inicializando entorno de pruebas")
    print("[environment.py] Los datos se crearán en cada step según sea necesario")
    print("=" * 70 + "\n")


def before_scenario(context, scenario):
    """
    Se ejecuta antes de cada escenario.

    ESTRATEGIA SIMPLIFICADA:
    1. Limpiar TODOS los datos (incluyendo tipos de visa y requisitos)
    2. Cada escenario creará los datos que necesita desde cero
    3. Los datos son explícitos en los steps, no "mágicos"
    """
    from migration.models import (
        Cita, Solicitante, Agente, Requisito, Documento, Carpeta,
        TipoVisa, TipoRequisito, RequisitoVisa
    )

    print(f"\n[environment.py] before_scenario: {scenario.name}")

    # Limpiar TODOS los datos (orden importa por FK)
    Documento.objects.all().delete()
    Carpeta.objects.all().delete()
    Requisito.objects.all().delete()
    Cita.objects.all().delete()
    Solicitante.objects.all().delete()
    Agente.objects.all().delete()

    # También limpiar datos de referencia - cada test creará los suyos
    RequisitoVisa.objects.all().delete()
    TipoRequisito.objects.all().delete()
    TipoVisa.objects.all().delete()

    print(f"[environment.py] Base de datos limpia - el test creará los datos que necesite\n")


def after_scenario(context, scenario):
    """
    Se ejecuta después de cada escenario.
    Limpia archivos físicos creados durante las pruebas.
    """
    from migration.services.documentos import limpiar_carpeta_documentos

    # Limpiar carpeta de documentos si el escenario tiene tag @documentos
    if "documentos" in [tag for tag in scenario.tags]:
        limpiar_carpeta_documentos()


def after_feature(context, feature):
    """
    Se ejecuta después de cada feature.
    Limpia archivos físicos para asegurar que no queden residuos.
    """
    from migration.services.documentos import limpiar_carpeta_documentos

    # Limpiar carpeta de documentos si la feature tiene tag @documentos
    if "documentos" in [tag for tag in feature.tags]:
        limpiar_carpeta_documentos()


def after_all(context):
    """
    Se ejecuta UNA VEZ después de todas las features.
    Limpieza final de todos los datos.
    """
    from migration.models import (
        Cita, Solicitante, Agente, Requisito, Documento, Carpeta,
        TipoVisa, TipoRequisito, RequisitoVisa
    )

    print("\n" + "=" * 70)
    print("[environment.py] after_all - Limpieza final")
    print("=" * 70)

    # Limpiar todos los datos al final
    Documento.objects.all().delete()
    Carpeta.objects.all().delete()
    Requisito.objects.all().delete()
    Cita.objects.all().delete()
    Solicitante.objects.all().delete()
    Agente.objects.all().delete()
    RequisitoVisa.objects.all().delete()
    TipoRequisito.objects.all().delete()
    TipoVisa.objects.all().delete()

    print("[environment.py] Limpieza completada")
    print("=" * 70 + "\n")