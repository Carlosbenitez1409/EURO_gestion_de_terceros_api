from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import uuid

User = get_user_model()


class ListaRestrictiva(models.Model):
    """
    Modelo para las diferentes listas restrictivas
    """
    class TipoLista(models.TextChoices):
        OFAC = 'ofac', _('OFAC (Office of Foreign Assets Control)')
        ONU = 'onu', _('Lista de Sanciones de la ONU')
        UE = 'ue', _('Lista de Sanciones de la Unión Europea')
        CLINTON = 'clinton', _('Lista Clinton')
        INTERPOL = 'interpol', _('Lista de Interpol')
        POLICÍA_NACIONAL = 'policia_nacional', _('Policía Nacional')
        CONTRALORIA = 'contraloria', _('Contraloría General')
        PROCURADURIA = 'procuraduria', _('Procuraduría General')
        OTRAS = 'otras', _('Otras listas')
    
    nombre = models.CharField(
        max_length=200,
        verbose_name=_('Nombre de la Lista')
    )
    
    tipo_lista = models.CharField(
        max_length=20,
        choices=TipoLista.choices,
        verbose_name=_('Tipo de Lista')
    )
    
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Descripción')
    )
    
    url_fuente = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('URL de la fuente')
    )
    
    activa = models.BooleanField(
        default=True,
        verbose_name=_('Lista Activa')
    )
    
    fecha_ultima_actualizacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Fecha de última actualización')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    class Meta:
        verbose_name = _('Lista Restrictiva')
        verbose_name_plural = _('Listas Restrictivas')
        ordering = ['tipo_lista', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_lista_display()})"  # type: ignore


class ValidacionTercero(models.Model):
    """
    Validación de terceros contra listas restrictivas
    """
    class EstadoValidacion(models.TextChoices):
        PENDIENTE = 'pendiente', _('Pendiente')
        EN_PROCESO = 'en_proceso', _('En Proceso')
        APROBADO = 'aprobado', _('Aprobado - Sin coincidencias')
        ALERTA = 'alerta', _('Alerta - Posibles coincidencias')
        RECHAZADO = 'rechazado', _('Rechazado - Coincidencia confirmada')
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tercero = models.ForeignKey(
        'terceros.Tercero',
        on_delete=models.CASCADE,
        related_name='validaciones',
        verbose_name=_('Tercero')
    )
    
    estado = models.CharField(
        max_length=15,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.PENDIENTE,
        verbose_name=_('Estado de Validación')
    )
    
    fecha_validacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de Validación')
    )
    
    validado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_('Validado por')
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Observaciones')
    )
    
    # Campos de resultado
    total_listas_consultadas = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total de listas consultadas')
    )
    
    total_coincidencias = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total de coincidencias encontradas')
    )
    
    class Meta:
        verbose_name = _('Validación de Tercero')
        verbose_name_plural = _('Validaciones de Terceros')
        ordering = ['-fecha_validacion']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_validacion']),
        ]
    
    def __str__(self):
        return f"{self.tercero} - {self.get_estado_display()}"  # type: ignore


class CoincidenciaLista(models.Model):
    """
    Coincidencias encontradas en las listas restrictivas
    """
    class NivelCoincidencia(models.TextChoices):
        EXACTA = 'exacta', _('Coincidencia Exacta')
        ALTA = 'alta', _('Coincidencia Alta')
        MEDIA = 'media', _('Coincidencia Media')
        BAJA = 'baja', _('Coincidencia Baja')
    
    validacion = models.ForeignKey(
        ValidacionTercero,
        on_delete=models.CASCADE,
        related_name='coincidencias',
        verbose_name=_('Validación')
    )
    
    lista_restrictiva = models.ForeignKey(
        ListaRestrictiva,
        on_delete=models.PROTECT,
        verbose_name=_('Lista Restrictiva')
    )
    
    nombre_encontrado = models.CharField(
        max_length=255,
        verbose_name=_('Nombre encontrado en la lista')
    )
    
    documento_encontrado = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Documento encontrado')
    )
    
    nivel_coincidencia = models.CharField(
        max_length=10,
        choices=NivelCoincidencia.choices,
        verbose_name=_('Nivel de Coincidencia')
    )
    
    porcentaje_similitud = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Porcentaje de Similitud')
    )
    
    detalles_adicionales = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Detalles adicionales de la coincidencia')
    )
    
    revisado = models.BooleanField(
        default=False,
        verbose_name=_('Revisado por usuario')
    )
    
    es_falso_positivo = models.BooleanField(
        default=False,
        verbose_name=_('Marcado como falso positivo')
    )
    
    observaciones_revision = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Observaciones de la revisión')
    )
    
    revisado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Revisado por')
    )
    
    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Fecha de revisión')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de detección')
    )
    
    class Meta:
        verbose_name = _('Coincidencia en Lista')
        verbose_name_plural = _('Coincidencias en Listas')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['nivel_coincidencia']),
            models.Index(fields=['revisado']),
        ]
    
    def __str__(self):
        return f"{self.validacion.tercero} - {self.lista_restrictiva.nombre} ({self.nivel_coincidencia})"


class ConfiguracionValidacion(models.Model):
    """
    Configuración para las validaciones automáticas
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Nombre de la configuración')
    )
    
    listas_activas = models.ManyToManyField(
        ListaRestrictiva,
        verbose_name=_('Listas activas para validación')
    )
    
    umbral_similitud = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('80.00'),
        verbose_name=_('Umbral de similitud (%)')
    )
    
    validacion_automatica = models.BooleanField(
        default=True,
        verbose_name=_('Validación automática activada')
    )
    
    notificar_coincidencias = models.BooleanField(
        default=True,
        verbose_name=_('Notificar coincidencias por email')
    )
    
    activa = models.BooleanField(
        default=True,
        verbose_name=_('Configuración activa')
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
        verbose_name = _('Configuración de Validación')
        verbose_name_plural = _('Configuraciones de Validación')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.nombre
