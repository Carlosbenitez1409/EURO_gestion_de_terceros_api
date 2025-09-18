from django.db import models
from django.conf import settings
from terceros.models import Tercero
import uuid
import os


def stradata_documento_upload_path(instance, filename):
    """
    Generar path para documentos de Stradata
    """
    return f"documentos_terceros/{instance.tercero.numero_documento}/stradata/{filename}"


class StrataDataDocumento(models.Model):
    """
    Modelo para documentos de consultas Stradata
    (Compatible con migración existente)
    """
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nombre = models.CharField(
        max_length=255,
        help_text='Nombre original del archivo'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        help_text='Descripción del documento'
    )
    archivo = models.FileField(
        upload_to=stradata_documento_upload_path,
        help_text='Archivo del documento Stradata'
    )
    tipo_consulta = models.CharField(
        max_length=100,
        default='Búsqueda Unificada',
        help_text='Tipo de consulta Stradata'
    )
    tamaño_archivo = models.BigIntegerField(
        help_text='Tamaño del archivo en bytes'
    )
    tipo_mime = models.CharField(
        max_length=100,
        help_text='Tipo MIME del archivo'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    tercero = models.ForeignKey(
        'terceros.Tercero', 
        on_delete=models.CASCADE, 
        related_name='documentos_stradata'
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_stradata_subidos'
    )

    class Meta:
        verbose_name = 'Documento Stradata'
        verbose_name_plural = 'Documentos Stradata'
        ordering = ['-fecha_subida']

    def __str__(self):
        return f"Stradata {self.tercero.numero_documento} - {self.tipo_consulta}"

    def save(self, *args, **kwargs):
        """Override save para llenar campos automáticamente"""
        if self.archivo:
            self.nombre = os.path.basename(self.archivo.name)
            self.tamaño_archivo = self.archivo.size
            # Determinar tipo MIME básico
            if self.nombre.lower().endswith('.pdf'):
                self.tipo_mime = 'application/pdf'
            else:
                self.tipo_mime = 'application/octet-stream'
        super().save(*args, **kwargs)

    @property
    def nombre_archivo(self):
        """Obtener solo el nombre del archivo"""
        return self.nombre or os.path.basename(self.archivo.name)

    @property
    def url_descarga(self):
        """URL para descargar el archivo"""
        return self.archivo.url if self.archivo else None


# Alias para compatibilidad con código existente
StratadaDocumento = StrataDataDocumento