from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from datetime import datetime, timedelta
import uuid

User = get_user_model()

# Import para obtener las choices de roles
from accounts.models import User as UserModel


class MetricaTerceros(models.Model):
    """
    Métricas precalculadas para el dashboard de terceros
    """
    fecha = models.DateField(
        verbose_name=_('Fecha de la métrica')
    )
    
    total_terceros = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total de terceros')
    )
    
    terceros_pendientes = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Terceros pendientes de aprobación')
    )
    
    terceros_aprobados = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Terceros aprobados')
    )
    
    terceros_rechazados = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Terceros rechazados')
    )
    
    terceros_en_revision = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Terceros en revisión')
    )
    
    # Métricas por tipo de persona
    personas_naturales = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Personas naturales')
    )
    
    personas_juridicas = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Personas jurídicas')
    )
    
    # Métricas de validaciones
    validaciones_pendientes = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Validaciones pendientes')
    )
    
    validaciones_con_alerta = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Validaciones con alerta')
    )
    
    # Métricas de documentos
    documentos_pendientes = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Documentos pendientes de validación')
    )
    
    documentos_rechazados = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Documentos rechazados')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    class Meta:
        verbose_name = _('Métrica de Terceros')
        verbose_name_plural = _('Métricas de Terceros')
        unique_together = ['fecha']
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['fecha']),
        ]
    
    def __str__(self):
        return f"Métricas del {self.fecha}"
    
    @classmethod
    def calcular_metricas_del_dia(cls, fecha=None):
        """
        Calcula las métricas del día especificado
        """
        if fecha is None:
            fecha = datetime.now().date()
        
        from terceros.models import Tercero
        from documents.models import DocumentoTercero
        from validations.models import ValidacionTercero
        
        # Terceros hasta la fecha
        terceros_query = Tercero.objects.filter(created_at__date__lte=fecha)
        
        metrics = {
            'fecha': fecha,
            'total_terceros': terceros_query.count(),
            'terceros_pendientes': terceros_query.filter(
                estado_aprobacion=Tercero.EstadoAprobacion.PENDIENTE
            ).count(),
            'terceros_aprobados': terceros_query.filter(
                estado_aprobacion=Tercero.EstadoAprobacion.APROBADO
            ).count(),
            'terceros_rechazados': terceros_query.filter(
                estado_aprobacion=Tercero.EstadoAprobacion.RECHAZADO
            ).count(),
            'terceros_en_revision': terceros_query.filter(
                estado_aprobacion=Tercero.EstadoAprobacion.EN_REVISION
            ).count(),
            'personas_naturales': terceros_query.filter(
                tipo_persona=Tercero.TipoPersona.NATURAL
            ).count(),
            'personas_juridicas': terceros_query.filter(
                tipo_persona=Tercero.TipoPersona.JURIDICA
            ).count(),
        }
        
        # Validaciones hasta la fecha
        validaciones_query = ValidacionTercero.objects.filter(fecha_validacion__date__lte=fecha)
        metrics.update({
            'validaciones_pendientes': validaciones_query.filter(
                estado=ValidacionTercero.EstadoValidacion.PENDIENTE
            ).count(),
            'validaciones_con_alerta': validaciones_query.filter(
                estado=ValidacionTercero.EstadoValidacion.ALERTA
            ).count(),
        })
        
        # Documentos hasta la fecha
        documentos_query = DocumentoTercero.objects.filter(fecha_subida__date__lte=fecha)
        metrics.update({
            'documentos_pendientes': documentos_query.filter(
                estado_validacion=DocumentoTercero.EstadoValidacion.PENDIENTE
            ).count(),
            'documentos_rechazados': documentos_query.filter(
                estado_validacion=DocumentoTercero.EstadoValidacion.RECHAZADO
            ).count(),
        })
        
        # Crear o actualizar la métrica
        metrica, created = cls.objects.update_or_create(
            fecha=fecha,
            defaults=metrics
        )
        
        return metrica


class AlertaDashboard(models.Model):
    """
    Alertas para mostrar en el dashboard
    """
    class TipoAlerta(models.TextChoices):
        INFO = 'info', _('Información')
        WARNING = 'warning', _('Advertencia')
        DANGER = 'danger', _('Peligro')
        SUCCESS = 'success', _('Éxito')
    
    class CategoriaAlerta(models.TextChoices):
        TERCEROS = 'terceros', _('Terceros')
        DOCUMENTOS = 'documentos', _('Documentos')
        VALIDACIONES = 'validaciones', _('Validaciones')
        SISTEMA = 'sistema', _('Sistema')
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    titulo = models.CharField(
        max_length=200,
        verbose_name=_('Título de la alerta')
    )
    
    mensaje = models.TextField(
        verbose_name=_('Mensaje de la alerta')
    )
    
    tipo = models.CharField(
        max_length=10,
        choices=TipoAlerta.choices,
        default=TipoAlerta.INFO,
        verbose_name=_('Tipo de alerta')
    )
    
    categoria = models.CharField(
        max_length=15,
        choices=CategoriaAlerta.choices,
        verbose_name=_('Categoría')
    )
    
    # Campos para determinar a quién mostrar la alerta
    mostrar_a_rol = models.CharField(
        max_length=20,
        choices=UserModel.RoleChoices.choices,
        null=True,
        blank=True,
        verbose_name=_('Mostrar solo a rol específico')
    )
    
    mostrar_a_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Mostrar solo a usuario específico')
    )
    
    # Campos de estado
    activa = models.BooleanField(
        default=True,
        verbose_name=_('Alerta activa')
    )
    
    fecha_expiracion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Fecha de expiración')
    )
    
    # Campos de auditoría
    creada_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='alertas_creadas',
        verbose_name=_('Creada por')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    # Campo para enlaces opcionales
    url_accion = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('URL de acción')
    )
    
    texto_accion = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Texto del botón de acción')
    )
    
    class Meta:
        verbose_name = _('Alerta del Dashboard')
        verbose_name_plural = _('Alertas del Dashboard')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['activa', 'categoria']),
            models.Index(fields=['mostrar_a_rol']),
            models.Index(fields=['fecha_expiracion']),
        ]
    
    def __str__(self):
        return self.titulo
    
    @property
    def esta_vigente(self):
        """Determina si la alerta está vigente"""
        if not self.activa:
            return False
        if self.fecha_expiracion and datetime.now() > self.fecha_expiracion:
            return False
        return True
    
    def es_visible_para_usuario(self, usuario):
        """Determina si la alerta es visible para un usuario específico"""
        if not self.esta_vigente:
            return False
        
        # Si está dirigida a un usuario específico
        if self.mostrar_a_usuario:
            return self.mostrar_a_usuario == usuario
        
        # Si está dirigida a un rol específico
        if self.mostrar_a_rol:
            return usuario.role == self.mostrar_a_rol
        
        # Si no hay restricciones, es visible para todos
        return True


class ConfiguracionDashboard(models.Model):
    """
    Configuración personalizada del dashboard por usuario
    """
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='configuracion_dashboard',
        verbose_name=_('Usuario')
    )
    
    # Widgets habilitados
    mostrar_metricas_generales = models.BooleanField(
        default=True,
        verbose_name=_('Mostrar métricas generales')
    )
    
    mostrar_grafico_terceros = models.BooleanField(
        default=True,
        verbose_name=_('Mostrar gráfico de terceros')
    )
    
    mostrar_alertas_validacion = models.BooleanField(
        default=True,
        verbose_name=_('Mostrar alertas de validación')
    )
    
    mostrar_documentos_pendientes = models.BooleanField(
        default=True,
        verbose_name=_('Mostrar documentos pendientes')
    )
    
    mostrar_ultimos_terceros = models.BooleanField(
        default=True,
        verbose_name=_('Mostrar últimos terceros')
    )
    
    # Configuración de período de datos
    periodo_metricas = models.CharField(
        max_length=10,
        choices=[
            ('7d', _('Últimos 7 días')),
            ('30d', _('Últimos 30 días')),
            ('90d', _('Últimos 90 días')),
            ('1y', _('Último año')),
        ],
        default='30d',
        verbose_name=_('Período para métricas')
    )
    
    # Número de elementos a mostrar
    max_terceros_recientes = models.PositiveIntegerField(
        default=10,
        verbose_name=_('Máximo terceros recientes a mostrar')
    )
    
    max_alertas = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Máximo alertas a mostrar')
    )
    
    # Configuración de actualización
    auto_refresh = models.BooleanField(
        default=True,
        verbose_name=_('Actualización automática')
    )
    
    refresh_interval = models.PositiveIntegerField(
        default=300,  # 5 minutos
        verbose_name=_('Intervalo de actualización (segundos)')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Fecha de actualización')
    )
    
    class Meta:
        verbose_name = _('Configuración del Dashboard')
        verbose_name_plural = _('Configuraciones del Dashboard')
    
    def __str__(self):
        return f"Configuración de {self.usuario.get_full_name()}"
