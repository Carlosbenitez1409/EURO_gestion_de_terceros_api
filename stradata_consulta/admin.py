from django.contrib import admin
from .models import StrataDataDocumento


@admin.register(StrataDataDocumento)
class StrataDataDocumentoAdmin(admin.ModelAdmin):
    """
    Admin para documentos de Stradata
    """
    list_display = ['nombre', 'tercero', 'tipo_consulta', 'fecha_subida', 'subido_por', 'activo']
    list_filter = ['tipo_consulta', 'fecha_subida', 'activo']
    search_fields = ['nombre', 'tercero__numero_documento', 'tercero__nombre_completo']
    readonly_fields = ['uuid', 'nombre', 'tamaño_archivo', 'tipo_mime', 'fecha_subida', 'fecha_actualizacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'tercero', 'archivo', 'uuid')
        }),
        ('Detalles del Archivo', {
            'fields': ('tipo_consulta', 'descripcion', 'tamaño_archivo', 'tipo_mime')
        }),
        ('Metadatos', {
            'fields': ('fecha_subida', 'fecha_actualizacion', 'subido_por', 'activo')
        }),
    )
