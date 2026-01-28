"""Configuración del admin de Django para los modelos del proyecto."""

from django.contrib import admin
from .models import Solicitante, Agente, Cita, Requisito, Documento, Carpeta

@admin.register(Solicitante)
class SolicitanteAdmin(admin.ModelAdmin):
    """Admin para gestionar Solicitantes."""
    
    # 1. Agregamos Cédula y Tipo de Visa a la tabla
    list_display = ('nombre', 'cedula', 'tipo_visa', 'email', 'telefono', 'tiene_cita_pendiente')
    search_fields = ('nombre', 'cedula', 'email')
    list_filter = ('tipo_visa', 'creado_en',) 
    readonly_fields = ('creado_en',)
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('usuario', 'nombre', 'cedula', 'email', 'telefono')
        }),
        ('Información del Sistema', {
            'fields': ('creado_en',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    """Admin para gestionar Agentes."""
    list_display = ('nombre', 'usuario', 'activo')
    search_fields = ('nombre', 'usuario__username')
    list_filter = ('activo',)
    
    fieldsets = (
        ('Información del Agente', {
            'fields': ('usuario', 'nombre', 'activo')
        }),
    )

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    """Admin para gestionar Citas."""
    list_display = ('__str__', 'estado', 'inicio', 'fin')
    search_fields = ('solicitante__nombre', 'agente__nombre')
    list_filter = ('estado', 'inicio')
    readonly_fields = ('fin', 'creada_en')
    
    fieldsets = (
        ('Información de la Cita', {
            # Nota: Ya no va 'tipo_tramite' ni 'detalle' aquí porque eso cambió en el modelo nuevo
            'fields': ('solicitante', 'agente', 'estado')
        }),
        ('Horarios', {
            'fields': ('inicio', 'fin')
        }),
        ('Información del Sistema', {
            'fields': ('creada_en',),
            'classes': ('collapse',)
        }),
    )

# --- NUEVOS REGISTROS PARA VER SI LA LÓGICA FUNCIONA ---

@admin.register(Requisito)
class RequisitoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'solicitante', 'estado', 'carga_habilitada')
    list_filter = ('estado', 'carga_habilitada')
    search_fields = ('solicitante__nombre', 'nombre')

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('requisito', 'version', 'estado', 'creado_en')
    list_filter = ('estado',)

@admin.register(Carpeta)
class CarpetaAdmin(admin.ModelAdmin):
    list_display = ('solicitante', 'estado', 'creado_en')