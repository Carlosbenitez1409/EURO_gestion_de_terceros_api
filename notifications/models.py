from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class Notificacion(models.Model):
    """
    Modelo para manejar notificaciones de usuarios
    """
    TIPOS_NOTIFICACION = [
        ('tercero_asignado', 'Tercero Asignado'),
        ('tercero_aprobado', 'Tercero Aprobado'),
        ('tercero_rechazado', 'Tercero Rechazado'),
        ('documento_subido', 'Documento Subido'),
        ('revision_requerida', 'Revisión Requerida'),
        ('estado_cambiado', 'Estado Cambiado'),
        ('alerta_cumplimiento', 'Alerta de Cumplimiento'),
        ('sistema', 'Notificación del Sistema'),
        ('recordatorio', 'Recordatorio'),
        ('usuario_creado', 'Usuario Creado'),
        ('rol_cambiado', 'Rol Cambiado'),
    ]
    
    NIVELES_PRIORIDAD = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        verbose_name='Usuario'
    )
    titulo = models.CharField(
        max_length=255,
        verbose_name='Título'
    )
    mensaje = models.TextField(
        verbose_name='Mensaje'
    )
    tipo = models.CharField(
        max_length=50,
        choices=TIPOS_NOTIFICACION,
        verbose_name='Tipo de Notificación'
    )
    prioridad = models.CharField(
        max_length=20,
        choices=NIVELES_PRIORIDAD,
        default='media',
        verbose_name='Prioridad'
    )
    leida = models.BooleanField(
        default=False,
        verbose_name='Leída'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_leida = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Lectura'
    )
    
    # Referencias opcionales para contexto
    tercero_relacionado = models.ForeignKey(
        'terceros.Tercero',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificaciones',
        verbose_name='Tercero Relacionado'
    )
    usuario_relacionado = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificaciones_generadas',
        verbose_name='Usuario que Generó la Notificación'
    )
    
    # Datos adicionales en JSON
    datos_extra = models.JSONField(
        blank=True,
        null=True,
        verbose_name='Datos Adicionales',
        help_text='Información adicional en formato JSON'
    )
    
    # URL para acción (opcional)
    url_accion = models.URLField(
        blank=True,
        null=True,
        verbose_name='URL de Acción',
        help_text='URL para redirigir cuando se haga clic en la notificación'
    )
    
    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['usuario', 'leida']),
            models.Index(fields=['tipo', 'fecha_creacion']),
            models.Index(fields=['prioridad', 'fecha_creacion']),
            models.Index(fields=['tercero_relacionado']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.usuario.get_full_name()}"
    
    def marcar_como_leida(self):
        """Marcar la notificación como leída"""
        if not self.leida:
            self.leida = True
            self.fecha_leida = timezone.now()
            self.save(update_fields=['leida', 'fecha_leida'])
    
    @property
    def tiempo_transcurrido(self):
        """Calcula el tiempo transcurrido desde la creación"""
        from django.utils.timesince import timesince
        return timesince(self.fecha_creacion)
    
    @classmethod
    def crear_notificacion(cls, usuario, titulo, mensaje, tipo='sistema', prioridad='media', 
                          tercero_relacionado=None, usuario_relacionado=None, 
                          datos_extra=None, url_accion=None):
        """
        Método de clase para crear notificaciones fácilmente
        """
        return cls.objects.create(
            usuario=usuario,
            titulo=titulo,
            mensaje=mensaje,
            tipo=tipo,
            prioridad=prioridad,
            tercero_relacionado=tercero_relacionado,
            usuario_relacionado=usuario_relacionado,
            datos_extra=datos_extra,
            url_accion=url_accion
        )


class PreferenciasNotificacion(models.Model):
    """
    Modelo para preferencias de notificación de cada usuario
    """
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferencias_notificacion',
        verbose_name='Usuario'
    )
    
    # Preferencias por tipo de notificación
    tercero_asignado = models.BooleanField(default=True, verbose_name='Tercero Asignado')
    tercero_aprobado = models.BooleanField(default=True, verbose_name='Tercero Aprobado')
    tercero_rechazado = models.BooleanField(default=True, verbose_name='Tercero Rechazado')
    documento_subido = models.BooleanField(default=True, verbose_name='Documento Subido')
    revision_requerida = models.BooleanField(default=True, verbose_name='Revisión Requerida')
    estado_cambiado = models.BooleanField(default=True, verbose_name='Estado Cambiado')
    alerta_cumplimiento = models.BooleanField(default=True, verbose_name='Alerta de Cumplimiento')
    sistema = models.BooleanField(default=True, verbose_name='Notificaciones del Sistema')
    recordatorio = models.BooleanField(default=True, verbose_name='Recordatorios')
    usuario_creado = models.BooleanField(default=False, verbose_name='Usuario Creado')
    rol_cambiado = models.BooleanField(default=True, verbose_name='Rol Cambiado')
    
    # Preferencias de entrega
    notificaciones_email = models.BooleanField(
        default=True, 
        verbose_name='Recibir por Email'
    )
    notificaciones_push = models.BooleanField(
        default=True, 
        verbose_name='Notificaciones Push'
    )
    notificaciones_en_app = models.BooleanField(
        default=True, 
        verbose_name='Notificaciones en la App'
    )
    
    # Configuración de horarios
    horario_inicio = models.TimeField(
        default='08:00',
        verbose_name='Horario de Inicio',
        help_text='Hora de inicio para recibir notificaciones'
    )
    horario_fin = models.TimeField(
        default='18:00',
        verbose_name='Horario de Fin',
        help_text='Hora límite para recibir notificaciones'
    )
    
    # Configuración de frecuencia
    resumen_diario = models.BooleanField(
        default=False,
        verbose_name='Resumen Diario',
        help_text='Recibir resumen diario de actividades'
    )
    resumen_semanal = models.BooleanField(
        default=False,
        verbose_name='Resumen Semanal',
        help_text='Recibir resumen semanal de actividades'
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = "Preferencias de Notificación"
        verbose_name_plural = "Preferencias de Notificación"
    
    def __str__(self):
        return f"Preferencias de {self.usuario.get_full_name()}"
    
    def acepta_notificacion(self, tipo_notificacion):
        """
        Verifica si el usuario acepta un tipo específico de notificación
        """
        return getattr(self, tipo_notificacion, True)
    
    @classmethod
    def get_or_create_for_user(cls, usuario):
        """
        Obtiene o crea las preferencias para un usuario
        """
        preferencias, created = cls.objects.get_or_create(
            usuario=usuario,
            defaults={
                'tercero_asignado': True,
                'tercero_aprobado': True,
                'tercero_rechazado': True,
                'documento_subido': True,
                'revision_requerida': True,
                'estado_cambiado': True,
                'alerta_cumplimiento': True,
                'sistema': True,
                'recordatorio': True,
                'usuario_creado': usuario.role in ['administrador', 'gestion_humana'],
                'rol_cambiado': True,
            }
        )
        return preferencias, created
