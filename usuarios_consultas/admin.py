# usuarios_consultas/admin.py
"""
Configuración del admin para el Sistema de Usuarios GH
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from .models import Solicitud, Persona, HistorialCambio, EstadoSolicitud


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    """Administración de solicitudes"""
    
    list_display = [
        'estado_badge', 'creada_por', 'asignada_a', 
        'total_personas', 'fecha_creacion', 'fecha_ultima_actualizacion'
    ]
    list_filter = ['estado', 'fecha_creacion', 'creada_por__role', 'asignada_a__role']
    search_fields = [
        'id', 'creada_por__username', 'creada_por__first_name', 'creada_por__last_name',
        'asignada_a__username', 'asignada_a__first_name', 'asignada_a__last_name',
        'observaciones_generales'
    ]
    date_hierarchy = 'fecha_creacion'
    ordering = ['-fecha_creacion']
    
    readonly_fields = ['id', 'fecha_creacion', 'fecha_ultima_actualizacion', 'total_personas']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('id', 'estado', 'creada_por', 'asignada_a')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_ultima_actualizacion')
        }),
        ('Detalles', {
            'fields': ('observaciones_generales', 'total_personas')
        }),
    )
    
    def estado_badge(self, obj):
        """Mostrar estado con colores"""
        colors = {
            EstadoSolicitud.CREADA: 'blue',
            EstadoSolicitud.ASIGNADA_ADMINISTRADOR: 'orange',
            EstadoSolicitud.EN_REVISION: 'purple',
            EstadoSolicitud.DEVUELTA_GH: 'red',
            EstadoSolicitud.ASIGNADA_PROCESOS: 'orange',
            EstadoSolicitud.COMPLETADA: 'green',
            EstadoSolicitud.FINALIZADA: 'darkgreen',
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creada_por', 'asignada_a').prefetch_related('personas')


class PersonaInline(admin.TabularInline):
    """Inline para personas dentro de solicitud"""
    model = Persona
    extra = 0
    fields = ['orden', 'nombres_apellidos', 'tipo_documento', 'numero_documento', 'riesgo']
    readonly_fields = ['fecha_creacion']


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    """Administración de personas"""
    
    list_display = [
        'nombres_apellidos', 'tipo_documento', 'numero_documento', 
        'solicitud_link', 'riesgo_badge', 'fecha_creacion'
    ]
    list_filter = ['tipo_documento', 'riesgo', 'solicitud__estado', 'fecha_creacion']
    search_fields = [
        'nombres_apellidos', 'numero_documento', 'solicitud__id',
        'solicitud__creada_por__username'
    ]
    date_hierarchy = 'fecha_creacion'
    ordering = ['-fecha_creacion']
    
    readonly_fields = ['id', 'fecha_creacion', 'fecha_actualizacion']
    
    fieldsets = (
        ('Información personal', {
            'fields': ('nombres_apellidos', 'tipo_documento', 'numero_documento', 'orden')
        }),
        ('Solicitud', {
            'fields': ('solicitud',)
        }),
        ('Resultados', {
            'fields': ('antecedentes', 'riesgo', 'observaciones')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion')
        }),
    )
    
    def solicitud_link(self, obj):
        """Link a la solicitud"""
        url = reverse('admin:usuarios_consultas_solicitud_change', args=[obj.solicitud.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.solicitud.id)[:8])
    solicitud_link.short_description = 'Solicitud'
    
    def riesgo_badge(self, obj):
        """Mostrar riesgo con colores"""
        if not obj.riesgo:
            return format_html('<span style="color: gray;">Sin asignar</span>')
        
        colors = {
            'ALTO': 'red',
            'MEDIO': 'orange',
            'BAJO': 'green',
        }
        color = colors.get(obj.riesgo, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_riesgo_display()
        )
    riesgo_badge.short_description = 'Riesgo'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('solicitud', 'solicitud__creada_por')


@admin.register(HistorialCambio)
class HistorialCambioAdmin(admin.ModelAdmin):
    """Administración del historial de cambios"""
    
    list_display = [
        'accion', 'usuario', 'solicitud_link', 'cambio_estado', 'fecha_cambio'
    ]
    list_filter = ['accion', 'fecha_cambio', 'usuario__role', 'estado_anterior', 'estado_nuevo']
    search_fields = [
        'accion', 'descripcion', 'usuario__username', 'solicitud__id'
    ]
    date_hierarchy = 'fecha_cambio'
    ordering = ['-fecha_cambio']
    
    readonly_fields = [
        'id', 'solicitud', 'fecha_cambio', 'usuario', 'accion', 
        'descripcion', 'estado_anterior', 'estado_nuevo'
    ]
    
    fieldsets = (
        ('Información básica', {
            'fields': ('solicitud', 'usuario', 'fecha_cambio')
        }),
        ('Cambio realizado', {
            'fields': ('accion', 'descripcion')
        }),
        ('Estados', {
            'fields': ('estado_anterior', 'estado_nuevo')
        }),
    )
    
    def solicitud_link(self, obj):
        """Link a la solicitud"""
        url = reverse('admin:usuarios_consultas_solicitud_change', args=[obj.solicitud.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.solicitud.id)[:8])
    solicitud_link.short_description = 'Solicitud'
    
    def cambio_estado(self, obj):
        """Mostrar cambio de estado si aplica"""
        if obj.estado_anterior and obj.estado_nuevo:
            return f"{obj.estado_anterior} → {obj.estado_nuevo}"
        return "N/A"
    cambio_estado.short_description = 'Cambio de Estado'
    
    def has_add_permission(self, request):
        """No permitir agregar historial manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir editar historial"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar historial"""
        return False
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('solicitud', 'usuario')


# Configurar el inline de personas en solicitudes
SolicitudAdmin.inlines = [PersonaInline]

# Configurar el admin site
admin.site.site_header = "EURO Sistema de Gestión de Terceros"
admin.site.site_title = "EURO Admin"
admin.site.index_title = "Panel de Administración"
