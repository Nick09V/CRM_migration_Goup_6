
from django.contrib import admin
from .models import (
    Solicitante,
    Agente,
    Cita,
    Requisito,
    Documento,
    Carpeta,
    CatalogoRequisito,
    TipoVisa,
)


@admin.register(Solicitante)
class SolicitanteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cedula', 'email', 'tipo_visa', 'creado_en')
    search_fields = ('nombre', 'cedula', 'email')
    list_filter = ('tipo_visa',)


@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'creado_en')
    search_fields = ('nombre',)
    list_filter = ('activo',)


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ('solicitante', 'agente', 'inicio', 'estado')
    search_fields = ('solicitante__nombre', 'agente__nombre')
    list_filter = ('estado',)


@admin.register(Requisito)
class RequisitoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'solicitante', 'estado', 'carga_habilitada')
    search_fields = ('nombre', 'solicitante__nombre')
    list_filter = ('estado', 'carga_habilitada')


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('requisito', 'nombre_archivo', 'version', 'estado', 'creado_en')
    search_fields = ('requisito__nombre', 'nombre_archivo')
    list_filter = ('estado',)


@admin.register(Carpeta)
class CarpetaAdmin(admin.ModelAdmin):
    list_display = ('solicitante', 'estado', 'creado_en')
    search_fields = ('solicitante__nombre',)
    list_filter = ('estado',)


@admin.register(CatalogoRequisito)
class CatalogoRequisitoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activo', 'creado_en')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('activo',)
    ordering = ('nombre',)


@admin.register(TipoVisa)
class TipoVisaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activo', 'creado_en')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activo',)
    ordering = ('nombre',)

