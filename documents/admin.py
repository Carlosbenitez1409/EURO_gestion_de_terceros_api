from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import TipoDocumento, DocumentoTercero


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    """
    Administración para tipos de documentos
    """
    list_display = ('nombre', 'es_obligatorio', 'activo', 'orden', 'created_at')
    list_filter = ('es_obligatorio', 'activo', 'created_at')
    search_fields = ('nombre', 'descripcion')
    ordering = ('orden', 'nombre')
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('nombre', 'descripcion')
        }),
        (_('Configuración'), {
            'fields': ('es_obligatorio', 'activo', 'orden')
        }),
        (_('Fechas'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)


# @admin.register(DocumentoTercero)
# class DocumentoTerceroAdmin(admin.ModelAdmin):
#     """
#     Administración para documentos de terceros
#     """
#     list_display = (
#         'tercero', 'tipo_documento', 'nombre_original', 
#         'estado_validacion', 'subido_por', 'fecha_subida'
#     )
#     list_filter = (
#         'estado_validacion', 'tipo_documento', 
#         'fecha_subida', 'fecha_validacion'
#     )
#     search_fields = (
#         'tercero__numero_documento', 'tercero__nombres', 
#         'tipo_documento__nombre', 'nombre_original'
#     )
#     ordering = ('-fecha_subida',)
    
#     fieldsets = (
#         (_('Información del Documento'), {
#             'fields': ('tercero', 'tipo_documento', 'archivo')
#         }),
#         (_('Información del Archivo'), {
#             'fields': ('nombre_original', 'tamano_archivo'),
#             'classes': ('collapse',)
#         }),
#         (_('Estado de Validación'), {
#             'fields': (
#                 'estado_validacion', 'validado_por', 
#                 'fecha_validacion', 'observaciones_validacion'
#             )
#         }),
#         (_('Auditoría'), {
#             'fields': ('subido_por', 'fecha_subida'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = (
#         'nombre_original', 'tamano_archivo', 
#         'fecha_subida', 'subido_por'
#     )
    
#     def save_model(self, request, obj, form, change):
#         if not change:  # creating new object
#             obj.subido_por = request.user
#         super().save_model(request, obj, form, change)

