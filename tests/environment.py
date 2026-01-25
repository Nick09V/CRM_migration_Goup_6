"""
Configuración del entorno para las pruebas BDD con Behave.
"""
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
    """
    Se ejecuta antes de cada escenario.
    Limpia la base de datos para garantizar pruebas aisladas.
    """
    from migration.models import Cita, Solicitante, Agente, Requisito, Documento, Carpeta

    # Limpiar datos de pruebas anteriores (orden importa por las FK)
    Documento.objects.all().delete()
    Carpeta.objects.all().delete()
    Requisito.objects.all().delete()
    Cita.objects.all().delete()
    Solicitante.objects.all().delete()
    Agente.objects.all().delete()


def after_scenario(context, scenario):
    """
    Se ejecuta después de cada escenario.
    """
    pass
