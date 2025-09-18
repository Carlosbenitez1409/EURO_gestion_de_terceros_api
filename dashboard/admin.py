from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import MetricaTerceros, AlertaDashboard, ConfiguracionDashboard


@admin.register(MetricaTerceros)
class MetricaTercerosAdmin(admin.ModelAdmin):
    """
    Administración para métricas de terceros
    """
    list_display = (
        'fecha', 'total_terceros', 'terceros_pendientes', 
        'terceros_aprobados', 'terceros_rechazados', 'created_at'
    )
    list_filter = ('fecha', 'created_at')
    search_fields = ('fecha',)
    ordering = ('-fecha',)
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('fecha',)
        }),
        (_('Métricas de Terceros'), {
            'fields': (
                'total_terceros', 'terceros_pendientes', 
                'terceros_aprobados', 'terceros_rechazados', 
                'terceros_en_revision'
            )
        }),
        (_('Métricas por Tipo'), {
            'fields': ('personas_naturales', 'personas_juridicas')
        }),
        (_('Métricas de Validaciones'), {
            'fields': ('validaciones_pendientes', 'validaciones_con_alerta')
        }),
        (_('Métricas de Documentos'), {
            'fields': ('documentos_pendientes', 'documentos_rechazados')
        }),
        (_('Fechas'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)
    
    actions = ['calcular_metricas_seleccionadas']
    
    def calcular_metricas_seleccionadas(self, request, queryset):
        """Acción para recalcular métricas seleccionadas"""
        for metrica in queryset:
            MetricaTerceros.calcular_metricas_del_dia(metrica.fecha)
        
        self.message_user(
            request, 
            f"Se recalcularon {queryset.count()} métricas."
        )
    
    calcular_metricas_seleccionadas.short_description = _("Recalcular métricas seleccionadas")


@admin.register(AlertaDashboard)
class AlertaDashboardAdmin(admin.ModelAdmin):
    """
    Administración para alertas del dashboard
    """
    list_display = (
        'titulo', 'tipo', 'categoria', 'activa', 
        'mostrar_a_rol', 'fecha_expiracion', 'created_at'
    )
    list_filter = (
        'tipo', 'categoria', 'activa', 'mostrar_a_rol', 
        'fecha_expiracion', 'created_at'
    )
    search_fields = ('titulo', 'mensaje')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Información de la Alerta'), {
            'fields': ('titulo', 'mensaje', 'tipo', 'categoria')
        }),
        (_('Visibilidad'), {
            'fields': (
                'mostrar_a_rol', 'mostrar_a_usuario', 
                'activa', 'fecha_expiracion'
            )
        }),
        (_('Acción'), {
            'fields': ('url_accion', 'texto_accion'),
            'classes': ('collapse',)
        }),
        (_('Auditoría'), {
            'fields': ('creada_por', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)
    
    def save_model(self, request, obj, form, change):
        if not change:  # creating new object
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(ConfiguracionDashboard)
class ConfiguracionDashboardAdmin(admin.ModelAdmin):
    """
    Administración para configuración del dashboard
    """
    list_display = (
        'usuario', 'periodo_metricas', 'auto_refresh', 
        'max_terceros_recientes', 'updated_at'
    )
    list_filter = (
        'periodo_metricas', 'auto_refresh', 
        'mostrar_metricas_generales', 'created_at'
    )
    search_fields = ('usuario__email', 'usuario__first_name', 'usuario__last_name')
    ordering = ('-updated_at',)
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('usuario',)
        }),
        (_('Widgets Habilitados'), {
            'fields': (
                'mostrar_metricas_generales', 'mostrar_grafico_terceros', 
                'mostrar_alertas_validacion', 'mostrar_documentos_pendientes', 
                'mostrar_ultimos_terceros'
            )
        }),
        (_('Configuración de Datos'), {
            'fields': (
                'periodo_metricas', 'max_terceros_recientes', 'max_alertas'
            )
        }),
        (_('Actualización Automática'), {
            'fields': ('auto_refresh', 'refresh_interval')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
