import os
import sys
import django

# Agregar el directorio raíz del proyecto al path
ruta_proyecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ruta_proyecto)

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')
django.setup()


def before_scenario(context, scenario):
    from migration.models import Cita, Solicitante, Agente, Requisito, Documento, Carpeta

    # Limpiar datos de pruebas anteriores (orden importa por las FK)
    Documento.objects.all().delete()
    Carpeta.objects.all().delete()
    Requisito.objects.all().delete()
    Cita.objects.all().delete()
    Solicitante.objects.all().delete()
    Agente.objects.all().delete()


def after_scenario(context, scenario):
    from migration.services.documentos import limpiar_carpeta_documentos

    # Limpiar carpeta de documentos después de cada escenario
    if "documentos" in [tag for tag in scenario.tags]:
        limpiar_carpeta_documentos()


def after_feature(context, feature):
    from migration.services.documentos import limpiar_carpeta_documentos

    # Limpiar carpeta de documentos al finalizar features de documentos
    if "documentos" in [tag for tag in feature.tags]:
        limpiar_carpeta_documentos()
