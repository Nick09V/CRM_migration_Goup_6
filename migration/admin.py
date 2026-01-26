"""Configuración del admin de Django para los modelos del proyecto."""

from django.contrib import admin
from .models import Solicitante, Agente, Cita


@admin.register(Solicitante)
class SolicitanteAdmin(admin.ModelAdmin):
    """Admin para gestionar Solicitantes."""
    
    list_display = ('nombre', 'email', 'telefono', 'creado_en', 'tiene_cita_pendiente')
    search_fields = ('nombre', 'email', 'telefono')
    list_filter = ('creado_en',)
    readonly_fields = ('creado_en', 'usuario')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('usuario', 'nombre', 'email', 'telefono')
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
    readonly_fields = ('usuario',)
    
    fieldsets = (
        ('Información del Agente', {
            'fields': ('usuario', 'nombre', 'activo')
        }),
    )


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    """Admin para gestionar Citas."""
    
    list_display = ('__str__', 'estado', 'inicio', 'fin', 'creada_en')
    search_fields = ('solicitante__nombre', 'agente__nombre')
    list_filter = ('estado', 'inicio', 'creada_en')
    readonly_fields = ('fin', 'creada_en')
    
    fieldsets = (
        ('Información de la Cita', {
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
    
    # Filtros personalizados por estado
    def get_list_filter(self, request):
        """Agrega filtro dinámico según rol del usuario."""
        filters = list(super().get_list_filter(request))
        return filters
