from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Notificacion, PreferenciasNotificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    """
    Administración para notificaciones
    """
    list_display = [
        'titulo', 'usuario', 'tipo', 'prioridad', 'leida', 
        'fecha_creacion', 'tercero_relacionado'
    ]
    list_filter = [
        'tipo', 'prioridad', 'leida', 'fecha_creacion'
    ]
    search_fields = [
        'titulo', 'mensaje', 'usuario__username', 'usuario__email'
    ]
    readonly_fields = ['fecha_creacion', 'fecha_leida', 'id']
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('usuario', 'titulo', 'mensaje', 'tipo', 'prioridad')
        }),
        (_('Estado'), {
            'fields': ('leida', 'fecha_creacion', 'fecha_leida')
        }),
        (_('Referencias'), {
            'fields': ('tercero_relacionado', 'usuario_relacionado')
        }),
        (_('Datos Adicionales'), {
            'fields': ('datos_extra', 'url_accion'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimizar consultas con select_related"""
        return super().get_queryset(request).select_related(
            'usuario', 'tercero_relacionado', 'usuario_relacionado'
        )
    
    def has_add_permission(self, request):
        """Solo administradores pueden crear notificaciones manualmente"""
        if hasattr(request.user, 'role'):
            return request.user.role == 'administrador'
        return super().has_add_permission(request)
    
    def has_change_permission(self, request, obj=None):
        """Solo el usuario propietario o administradores pueden modificar"""
        if obj and hasattr(request.user, 'role'):
            return (
                request.user.role == 'administrador' or 
                obj.usuario == request.user
            )
        return super().has_change_permission(request, obj)


@admin.register(PreferenciasNotificacion)
class PreferenciasNotificacionAdmin(admin.ModelAdmin):
    """
    Administración para preferencias de notificación
    """
    list_display = [
        'usuario', 'notificaciones_email', 'notificaciones_push', 
        'notificaciones_en_app', 'fecha_actualizacion'
    ]
    list_filter = [
        'notificaciones_email', 'notificaciones_push', 'notificaciones_en_app',
        'resumen_diario', 'resumen_semanal'
    ]
    search_fields = ['usuario__username', 'usuario__email']
    readonly_fields = ['fecha_actualizacion']
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('usuario',)
        }),
        (_('Tipos de Notificación'), {
            'fields': (
                'tercero_asignado', 'tercero_aprobado', 'tercero_rechazado',
                'documento_subido', 'revision_requerida', 'estado_cambiado',
                'alerta_cumplimiento', 'sistema', 'recordatorio', 
                'usuario_creado', 'rol_cambiado'
            )
        }),
        (_('Canales de Entrega'), {
            'fields': ('notificaciones_email', 'notificaciones_push', 'notificaciones_en_app')
        }),
        (_('Configuración de Horarios'), {
            'fields': ('horario_inicio', 'horario_fin')
        }),
        (_('Resúmenes'), {
            'fields': ('resumen_diario', 'resumen_semanal')
        }),
        (_('Información del Sistema'), {
            'fields': ('fecha_actualizacion',),
            'classes': ('collapse',)
        }),
    )
    
    def has_change_permission(self, request, obj=None):
        """Solo el usuario propietario o administradores pueden modificar"""
        if obj and hasattr(request.user, 'role'):
            return (
                request.user.role == 'administrador' or 
                obj.usuario == request.user
            )
        return super().has_change_permission(request, obj)
