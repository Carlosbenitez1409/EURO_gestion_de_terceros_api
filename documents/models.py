from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
import uuid
import os

User = get_user_model()


def upload_documento_tercero(instance, filename):
    """Función para generar la ruta de upload de documentos"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"documentos/terceros/{instance.tercero.numero_documento}/{filename}"


class TipoDocumento(models.Model):
    """
    Catálogo de tipos de documentos requeridos
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Nombre del Documento')
    )
    
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Descripción')
    )
    
    es_obligatorio = models.BooleanField(
        default=True,
        verbose_name=_('Es Obligatorio')
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name=_('Activo')
    )
    
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Orden de presentación')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    class Meta:
        verbose_name = _('Tipo de Documento')
        verbose_name_plural = _('Tipos de Documentos')
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return self.nombre


class DocumentoTercero(models.Model):
    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        verbose_name='Tipo de Documento'
    )
    
    class EstadoValidacion(models.TextChoices):
        PENDIENTE = 'pendiente', _('Pendiente')
        APROBADO = 'aprobado', _('Aprobado')
        RECHAZADO = 'rechazado', _('Rechazado')
        REQUIERE_AJUSTES = 'requiere_ajustes', _('Requiere Ajustes')
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tercero = models.ForeignKey(
        'terceros.Tercero',
        on_delete=models.CASCADE,
        related_name='documentos_documents',
        verbose_name=_('Tercero')
    )
    
    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        verbose_name=_('Tipo de Documento')
    )
    
    archivo = models.FileField(
        upload_to=upload_documento_tercero,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
            )
        ],
        verbose_name=_('Archivo')
    )
    
    nombre_original = models.CharField(
        max_length=255,
        verbose_name=_('Nombre Original del Archivo')
    )
    
    tamano_archivo = models.PositiveIntegerField(
        verbose_name=_('Tamaño del Archivo (bytes)')
    )
    
    estado_validacion = models.CharField(
        max_length=20,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.PENDIENTE,
        verbose_name=_('Estado de Validación')
    )
    
    # Relaciones de auditoría
    subido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='documentos_subidos',
        verbose_name=_('Subido por')
    )
    
    validado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_validados',
        verbose_name=_('Validado por')
    )
    
    # Timestamps
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de subida')
    )
    
    fecha_validacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Fecha de validación')
    )
    
    # Observaciones
    observaciones_validacion = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Observaciones de Validación')
    )
    
    class Meta:
        verbose_name = _('Documento de Tercero')
        verbose_name_plural = _('Documentos de Terceros')
        ordering = ['-fecha_subida']
        unique_together = ['tercero', 'tipo_documento']
        indexes = [
            models.Index(fields=['estado_validacion']),
            models.Index(fields=['fecha_subida']),
        ]
    
    def __str__(self):
        return f"{self.tercero} - {self.tipo_documento.nombre}"
    
    def save(self, *args, **kwargs):
        if self.archivo:
            self.nombre_original = self.archivo.name 
    
    @property
    def extension_archivo(self):
        """Retorna la extensión del archivo"""
        return os.path.splitext(self.nombre_original)[1].lower()
    
    @property
    def tamano_legible(self):
        """Retorna el tamaño del archivo en formato legible"""
        size = self.tamano_archivo
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class HistorialDocumento(models.Model):
    """
    Historial de cambios en los documentos
    """
    documento = models.ForeignKey(
        DocumentoTercero,
        on_delete=models.CASCADE,
        related_name='historial'
    )
    
    estado_anterior = models.CharField(
        max_length=20,
        choices=DocumentoTercero.EstadoValidacion.choices,
        null=True,
        blank=True,
        verbose_name=_('Estado Anterior')
    )
    
    estado_nuevo = models.CharField(
        max_length=20,
        choices=DocumentoTercero.EstadoValidacion.choices,
        verbose_name=_('Estado Nuevo')
    )
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Usuario')
    )
    
    comentarios = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Comentarios')
    )
    
    fecha_cambio = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha del cambio')
    )
    
    class Meta:
        verbose_name = _('Historial de Documento')
        verbose_name_plural = _('Historiales de Documentos')
        ordering = ['-fecha_cambio']
    
    def __str__(self):
        return f"{self.documento} - {self.estado_anterior} → {self.estado_nuevo}"

class Documento(models.Model):
    tercero = models.ForeignKey(
        'terceros.Tercero',
        on_delete=models.CASCADE,
        related_name='documentos_tercero_documentos',  # Un nombre diferente aquí
        verbose_name=_('Tercero')
    )
