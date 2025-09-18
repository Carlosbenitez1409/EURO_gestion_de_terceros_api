from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    ListaRestrictiva, ValidacionTercero, CoincidenciaLista, 
    ConfiguracionValidacion
)


@admin.register(ListaRestrictiva)
class ListaRestrictivaAdmin(admin.ModelAdmin):
    """
    Administración para listas restrictivas
    """
    list_display = (
        'nombre', 'tipo_lista', 'activa', 
        'fecha_ultima_actualizacion', 'created_at'
    )
    list_filter = ('tipo_lista', 'activa', 'created_at')
    search_fields = ('nombre', 'descripcion')
    ordering = ('tipo_lista', 'nombre')
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('nombre', 'tipo_lista', 'descripcion')
        }),
        (_('Configuración'), {
            'fields': ('url_fuente', 'activa', 'fecha_ultima_actualizacion')
        }),
        (_('Fechas'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)


@admin.register(ValidacionTercero)
class ValidacionTerceroAdmin(admin.ModelAdmin):
    """
    Administración para validaciones de terceros
    """
    list_display = (
        'tercero', 'estado', 'total_listas_consultadas', 
        'total_coincidencias', 'validado_por', 'fecha_validacion'
    )
    list_filter = ('estado', 'fecha_validacion')
    search_fields = (
        'tercero__numero_documento', 'tercero__nombres', 
        'validado_por__email'
    )
    ordering = ('-fecha_validacion',)
    
    fieldsets = (
        (_('Información de Validación'), {
            'fields': ('tercero', 'estado', 'validado_por')
        }),
        (_('Resultados'), {
            'fields': (
                'total_listas_consultadas', 'total_coincidencias', 
                'observaciones'
            )
        }),
        (_('Fechas'), {
            'fields': ('fecha_validacion',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('fecha_validacion',)


@admin.register(CoincidenciaLista)
class CoincidenciaListaAdmin(admin.ModelAdmin):
    """
    Administración para coincidencias en listas
    """
    list_display = (
        'validacion', 'lista_restrictiva', 'nombre_encontrado', 
        'nivel_coincidencia', 'revisado', 'created_at'
    )
    list_filter = (
        'nivel_coincidencia', 'revisado', 'es_falso_positivo', 
        'lista_restrictiva__tipo_lista', 'created_at'
    )
    search_fields = (
        'validacion__tercero__numero_documento', 
        'nombre_encontrado', 'documento_encontrado'
    )
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Información de la Coincidencia'), {
            'fields': (
                'validacion', 'lista_restrictiva', 'nombre_encontrado', 
                'documento_encontrado'
            )
        }),
        (_('Análisis de Coincidencia'), {
            'fields': (
                'nivel_coincidencia', 'porcentaje_similitud', 
                'detalles_adicionales'
            )
        }),
        (_('Revisión'), {
            'fields': (
                'revisado', 'es_falso_positivo', 'observaciones_revision', 
                'revisado_por', 'fecha_revision'
            )
        }),
        (_('Fechas'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)


@admin.register(ConfiguracionValidacion)
class ConfiguracionValidacionAdmin(admin.ModelAdmin):
    """
    Administración para configuración de validaciones
    """
    list_display = (
        'nombre', 'umbral_similitud', 'validacion_automatica', 
        'notificar_coincidencias', 'activa', 'created_at'
    )
    list_filter = (
        'validacion_automatica', 'notificar_coincidencias', 
        'activa', 'created_at'
    )
    search_fields = ('nombre',)
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('nombre', 'listas_activas')
        }),
        (_('Configuración de Validación'), {
            'fields': (
                'umbral_similitud', 'validacion_automatica', 
                'notificar_coincidencias'
            )
        }),
        (_('Estado'), {
            'fields': ('activa',)
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    filter_horizontal = ('listas_activas',)
