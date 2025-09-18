from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    Tercero, DocumentoTercero, RepresentanteLegal, ComposicionAccionaria, 
    InformacionFinanciera, InformacionPEP, RevisionCumplimiento, 
    HistorialEstado, ActividadAdministrativa, HistorialTercero
)

class DocumentoTerceroInline(admin.TabularInline):
    """
    Formulario en línea para agregar documentos asociados al Tercero.
    """
    model = DocumentoTercero
    extra = 1  # Número de formularios vacíos que se mostrarán por defecto.
    fields = ('tipo_documento', 'archivo')  # Asegúrate de que 'tipo_documento' esté incluido
    #readonly_fields = ('tipo_documento',)  # Esto es solo para que no se edite, si lo quieres editable elimina esta línea


class InformacionPEPInline(admin.TabularInline):
    """
    Formulario en línea para información PEP - CRÍTICO para SARLAFT
    """
    model = InformacionPEP
    extra = 0
    fields = ('nombre', 'tipo', 'numero_identificacion', 'patrimonio_fiducia', 'relaciones_comerciales')
    verbose_name = "Información PEP"
    verbose_name_plural = "Información Personas Expuestas Políticamente"


@admin.register(Tercero)
class TerceroAdmin(admin.ModelAdmin):
    """
    Administración para el modelo Tercero
    """
    list_display = [
        'numero_documento', 
        'get_nombre_completo', 
        'tipo_persona', 
        'email',
        'responsableIVA',  # Agregar campos del formulario
        'granContribuyente',
        'estado_aprobacion', 
        'created_at'
    ]
    list_filter = ['tipo_persona', 'estado_aprobacion', 'responsableIVA', 'granContribuyente', 'created_at']
    search_fields = ['numero_documento', 'nombres', 'apellidos', 'razon_social', 'email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('tipo_documento', 'numero_documento', 'tipo_persona')
        }),
        (_('Información Personal/Empresarial'), {
            'fields': ('nombres', 'apellidos', 'razon_social')
        }),
        (_('Información de Contacto'), {
            'fields': ('email', 'telefono', 'direccion', 'ciudad', 'departamento')
        }),
        (_('Información Tributaria Frontend'), {
            'fields': ('responsableIVA', 'correoFacturacion', 'granContribuyente', 
                      'numeroResolucionGC', 'fechaResolucionGC', 'exentoRenta', 'condicionesExentoRenta'),
            'classes': ('collapse',)
        }),
        (_('Información Financiera Frontend'), {
            'fields': ('ingresoMensual', 'costosGastos', 'otrosIngresos', 'totalIngresos', 'detalleOtrosIngresos'),
            'classes': ('collapse',)
        }),
        (_('Información Comercial Frontend'), {
            'fields': ('operacionesMonedaExtranjera', 'tiposOperacionesMonedaExtranjera', 'manejoAltoEfectivo', 'autorizacionTratamientoDatos'),
            'classes': ('collapse',)
        }),
        (_('SARLAFT/PEP Frontend - CRÍTICO'), {
            'fields': ('personaExpuestaPolitica', 'detallesPEP', 'origenFondos', 'fuentesFondos', 'tiposRecursos',
                      'constituyePatrimoniosAutonomos', 'declaracionTransparencia'),
            'classes': ('collapse',),
            'description': 'Campos críticos para cumplimiento SARLAFT/PEP Colombia'
        }),
        (_('Representantes y Accionistas Frontend'), {
            'fields': ('representantes', 'accionistas_frontend'),
            'classes': ('collapse',)
        }),
        (_('Estado y Aprobación'), {
            'fields': ('estado_aprobacion', 'aprobado_por', 'fecha_aprobacion', 'observaciones')
        }),
        (_('Estado del Registro'), {
            'fields': ('activo', 'creado_por')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DocumentoTerceroInline, InformacionPEPInline]  # Agregar documentos e información PEP
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # editing an existing object
            readonly.extend(['numero_documento'])
        return readonly
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.creado_por:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
    
    def get_nombre_completo(self, obj):
        if obj.tipo_persona == 'natural':
            return f"{obj.nombres} {obj.apellidos}"
        return obj.razon_social
    get_nombre_completo.short_description = 'Nombre Completo'


@admin.register(DocumentoTercero)
class DocumentoTerceroAdmin(admin.ModelAdmin):
    list_display = ['tercero', 'tipo_documento', 'nombre_original', 'fecha_subida', 'es_vigente']
    list_filter = ['tipo_documento', 'es_vigente', 'fecha_subida']
    search_fields = ['tercero__numero_documento', 'nombre_original']

@admin.register(RepresentanteLegal)
class RepresentanteLegalAdmin(admin.ModelAdmin):
    list_display = ['tercero', 'nombre_completo', 'numero_identificacion', 'telefono']
    search_fields = ['nombre_completo', 'numero_identificacion']

@admin.register(ComposicionAccionaria)
class ComposicionAccionariaAdmin(admin.ModelAdmin):
    list_display = ['tercero', 'nombre_razon_social', 'numero_identificacion', 'porcentaje_participacion']
    search_fields = ['nombre_razon_social', 'numero_identificacion']

@admin.register(InformacionFinanciera)
class InformacionFinancieraAdmin(admin.ModelAdmin):
    list_display = ['tercero', 'total_ingresos', 'activos', 'pasivos', 'patrimonio']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InformacionPEP)
class InformacionPEPAdmin(admin.ModelAdmin):
    """
    Administración CRÍTICA para información PEP - SARLAFT
    """
    list_display = ['tercero', 'nombre', 'tipo', 'numero_identificacion', 'patrimonio_fiducia', 'relaciones_comerciales']
    list_filter = ['tipo', 'patrimonio_fiducia', 'relaciones_comerciales', 'created_at']
    search_fields = ['nombre', 'numero_identificacion', 'tercero__numero_documento']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Información Personal PEP'), {
            'fields': ('tercero', 'nombre', 'tipo', 'numero_identificacion')
        }),
        (_('Información Financiera/Comercial'), {
            'fields': ('patrimonio_fiducia', 'relaciones_comerciales')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RevisionCumplimiento)
class RevisionCumplimientoAdmin(admin.ModelAdmin):
    """
    Administración para revisiones de cumplimiento SARLAFT
    """
    list_display = ['tercero', 'usuario', 'nivel_riesgo', 'aprobado', 'requiere_monitoreo', 'fecha_revision']
    list_filter = ['nivel_riesgo', 'aprobado', 'requiere_monitoreo', 'fecha_revision']
    search_fields = ['tercero__numero_documento', 'usuario__username', 'observaciones']
    readonly_fields = ['fecha_revision']
    
    fieldsets = (
        (_('Información de la Revisión'), {
            'fields': ('tercero', 'usuario', 'nivel_riesgo', 'aprobado', 'requiere_monitoreo')
        }),
        (_('Observaciones'), {
            'fields': ('observaciones',)
        }),
        (_('Fechas'), {
            'fields': ('fecha_revision',),
            'classes': ('collapse',)
        }),
    )
    
    def has_change_permission(self, request, obj=None):
        # Solo oficiales de cumplimiento y administradores pueden editar
        if hasattr(request.user, 'role'):
            return request.user.role in ['oficial_cumplimiento', 'administrador']
        return super().has_change_permission(request, obj)


@admin.register(HistorialEstado)
class HistorialEstadoAdmin(admin.ModelAdmin):
    """
    Administración para historial de cambios de estado
    """
    list_display = ['tercero', 'estado_anterior', 'estado_nuevo', 'usuario', 'fecha_cambio']
    list_filter = ['estado_anterior', 'estado_nuevo', 'fecha_cambio']
    search_fields = ['tercero__numero_documento', 'usuario__username', 'observaciones']
    readonly_fields = ['fecha_cambio']
    
    def has_add_permission(self, request):
        # No permitir crear manualmente, solo se crean automáticamente
        return False
    
    def has_change_permission(self, request, obj=None):
        # Solo lectura para mantener integridad del historial
        return False


@admin.register(ActividadAdministrativa)
class ActividadAdministrativaAdmin(admin.ModelAdmin):
    """
    Administración para actividades administrativas del sistema
    """
    list_display = ['tipo_actividad', 'usuario_administrador', 'usuario_afectado', 'tercero_afectado', 'fecha_actividad']
    list_filter = ['tipo_actividad', 'fecha_actividad']
    search_fields = ['usuario_administrador__username', 'usuario_afectado__username', 'descripcion']
    readonly_fields = ['fecha_actividad']
    
    fieldsets = (
        (_('Información de la Actividad'), {
            'fields': ('tipo_actividad', 'usuario_administrador', 'descripcion')
        }),
        (_('Entidades Afectadas'), {
            'fields': ('usuario_afectado', 'tercero_afectado')
        }),
        (_('Datos Adicionales'), {
            'fields': ('datos_adicionales',),
            'classes': ('collapse',)
        }),
        (_('Fechas'), {
            'fields': ('fecha_actividad',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Solo administradores pueden crear actividades administrativas
        if hasattr(request.user, 'role'):
            return request.user.role == 'administrador'
        return False
    
    def has_change_permission(self, request, obj=None):
        # Solo administradores pueden editar
        if hasattr(request.user, 'role'):
            return request.user.role == 'administrador'
        return super().has_change_permission(request, obj)


@admin.register(HistorialTercero)
class HistorialTerceroAdmin(admin.ModelAdmin):
    """
    Administración para el modelo HistorialTercero - Vista de solo lectura para auditoría
    """
    list_display = [
        'tercero_numero_documento',
        'tercero_nombre', 
        'accion',
        'usuario_accion',
        'usuario_asignado_nuevo',
        'fecha_accion'
    ]
    
    list_filter = [
        'accion', 
        'fecha_accion',
        'usuario__role',
        'usuario_asignado_nuevo__role'
    ]
    
    search_fields = [
        'tercero__numero_documento',
        'tercero__nombres',
        'tercero__apellidos', 
        'tercero__razon_social',
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
        'observaciones'
    ]
    
    readonly_fields = [
        'tercero', 'accion', 'usuario', 'usuario_asignado_anterior',
        'usuario_asignado_nuevo', 'estado_anterior', 'estado_nuevo',
        'observaciones', 'fecha_accion'
    ]
    
    ordering = ['-fecha_accion']
    
    date_hierarchy = 'fecha_accion'
    
    fieldsets = (
        ('Información del Tercero', {
            'fields': ('tercero',)
        }),
        ('Acción Realizada', {
            'fields': ('accion', 'fecha_accion', 'usuario')
        }),
        ('Estados', {
            'fields': ('estado_anterior', 'estado_nuevo')
        }),
        ('Asignaciones', {
            'fields': ('usuario_asignado_anterior', 'usuario_asignado_nuevo')
        }),
        ('Detalles', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )
    
    def tercero_numero_documento(self, obj):
        return obj.tercero.numero_documento
    tercero_numero_documento.short_description = 'Número Documento'
    tercero_numero_documento.admin_order_field = 'tercero__numero_documento'
    
    def tercero_nombre(self, obj):
        return str(obj.tercero)
    tercero_nombre.short_description = 'Tercero'
    tercero_nombre.admin_order_field = 'tercero__nombres'
    
    def usuario_accion(self, obj):
        return f"{obj.usuario.get_full_name()} ({obj.usuario.username})"
    usuario_accion.short_description = 'Usuario que realizó la acción'
    usuario_accion.admin_order_field = 'usuario__username'
    
    def has_add_permission(self, request):
        # El historial se crea automáticamente, no permitir creación manual
        return False
    
    def has_change_permission(self, request, obj=None):
        # El historial es de solo lectura para auditoría
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Solo administradores pueden eliminar historial (para casos excepcionales)
        if hasattr(request.user, 'role'):
            return request.user.role == 'administrador'
        return False
