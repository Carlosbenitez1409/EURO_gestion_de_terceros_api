# usuarios_consultas/models.py
"""
Modelos para el Sistema de Usuarios GH (Consultas de Personal)
Implementación según API_SPECIFICATION_USUARIOS_GH.md
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.utils import timezone

User = get_user_model()


class EstadoSolicitud(models.TextChoices):
    """Estados posibles de una solicitud según flujo de negocio"""
    CREADA = 'creada', 'Creada'
    ASIGNADA_ADMINISTRADOR = 'asignada_administrador', 'Asignada a Administrador'
    EN_REVISION_ADMINISTRADOR = 'en_revision_administrador', 'En revisión por Administrador'
    ASIGNADA_PROCESOS = 'asignada_procesos', 'Asignada a Procesos'
    EN_REVISION_PROCESOS = 'en_revision_procesos', 'En revisión por Procesos'
    DEVUELTA_GH = 'devuelta_gh', 'Devuelta a GH'
    FINALIZADA = 'finalizada', 'Finalizada'


class TipoDocumento(models.TextChoices):
    """Tipos de documento de identidad"""
    CC = 'CC', 'Cédula de Ciudadanía'
    CE = 'CE', 'Cédula de Extranjería'
    PP = 'PP', 'Pasaporte'
    TI = 'TI', 'Tarjeta de Identidad'


class Riesgo(models.TextChoices):
    """Niveles de riesgo asignados a personas"""
    ALTO = 'ALTO', 'Alto'
    MEDIO = 'MEDIO', 'Medio'
    BAJO = 'BAJO', 'Bajo'
    SIN_ANTECEDENTES = 'SIN_ANTECEDENTES', 'Sin Antecedentes'


class Solicitud(models.Model):
    """
    Solicitud de consulta de personal
    Una solicitud puede contener de 1 a 10 personas para consultar
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID'
    )
    
    estado = models.CharField(
        max_length=50,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.CREADA,
        verbose_name='Estado',
        help_text='Estado actual de la solicitud'
    )
    
    creada_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='solicitudes_creadas',
        verbose_name='Creada por',
        help_text='Usuario que creó la solicitud'
    )
    
    asignada_a = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='solicitudes_asignadas',
        null=True,
        blank=True,
        verbose_name='Asignada a',
        help_text='Usuario asignado actualmente'
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    
    fecha_ultima_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de última actualización'
    )
    
    observaciones_generales = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones generales',
        help_text='Observaciones opcionales sobre la solicitud'
    )
    
    class Meta:
        verbose_name = 'Solicitud'
        verbose_name_plural = 'Solicitudes'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado'], name='idx_solicitud_estado'),
            models.Index(fields=['creada_por'], name='idx_solicitud_creada_por'),
            models.Index(fields=['asignada_a'], name='idx_solicitud_asignada_a'),
            models.Index(fields=['fecha_creacion'], name='idx_solicitud_fecha_creacion'),
        ]
    
    def __str__(self):
        return f"Solicitud {self.id} - {self.get_estado_display()}"
    
    def puede_ser_editada_por(self, usuario):
        """Determina si un usuario puede editar esta solicitud"""
        # Solo el creador (GH) puede editar si está en estado devuelta
        if self.estado == EstadoSolicitud.DEVUELTA_GH:
            return self.creada_por == usuario
        
        # Admin y Procesos pueden editar si está asignada a ellos
        if self.estado in [EstadoSolicitud.EN_REVISION_ADMINISTRADOR, EstadoSolicitud.EN_REVISION_PROCESOS]:
            return self.asignada_a == usuario
        
        return False
    
    def puede_tomar_revision(self, usuario):
        """Determina si un usuario puede tomar esta solicitud para revisión"""
        if not hasattr(usuario, 'role'):
            return False
            
        role = usuario.role
        
        # Admin puede tomar si está asignada a administrador
        if (role == 'administrador' and 
            self.estado == EstadoSolicitud.ASIGNADA_ADMINISTRADOR):
            return True
        
        # Procesos puede tomar si está asignada a procesos
        if (role == 'procesos' and 
            self.estado == EstadoSolicitud.ASIGNADA_PROCESOS):
            return True
        
        return False
    
    @property
    def total_personas(self):
        """Retorna el número total de personas en la solicitud"""
        return self.personas.count()


class Persona(models.Model):
    """
    Persona incluida en una solicitud de consulta
    Contiene información personal y resultados de consulta
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID'
    )
    
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name='personas',
        verbose_name='Solicitud'
    )
    
    orden = models.PositiveIntegerField(
        verbose_name='Orden',
        help_text='Orden de la persona dentro de la solicitud'
    )
    
    nombres_apellidos = models.CharField(
        max_length=255,
        verbose_name='Nombres y apellidos',
        help_text='Nombres y apellidos completos'
    )
    
    tipo_documento = models.CharField(
        max_length=10,
        choices=TipoDocumento.choices,
        verbose_name='Tipo de documento'
    )
    
    numero_documento = models.CharField(
        max_length=50,
        verbose_name='Número de documento',
        help_text='Número del documento de identidad'
    )
    
    antecedentes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Antecedentes',
        help_text='Información de antecedentes (rellenado por Admin/Procesos)'
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones',
        help_text='Observaciones adicionales sobre la persona'
    )
    
    riesgo = models.CharField(
        max_length=20,
        choices=Riesgo.choices,
        blank=True,
        null=True,
        verbose_name='Nivel de riesgo',
        help_text='Nivel de riesgo asignado por Admin/Procesos'
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de actualización'
    )
    
    class Meta:
        verbose_name = 'Persona'
        verbose_name_plural = 'Personas'
        ordering = ['solicitud', 'orden']
        unique_together = [
            ('solicitud', 'orden'),  # No duplicar orden en misma solicitud
        ]
        indexes = [
            models.Index(fields=['solicitud'], name='idx_persona_solicitud'),
            models.Index(fields=['tipo_documento', 'numero_documento'], name='idx_persona_documento'),
        ]
    
    def __str__(self):
        return f"{self.nombres_apellidos} ({self.tipo_documento} {self.numero_documento})"
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # Validar que no haya duplicados de documento en la misma solicitud
        if self.solicitud_id:
            duplicados = Persona.objects.filter(
                solicitud=self.solicitud,
                tipo_documento=self.tipo_documento,
                numero_documento=self.numero_documento
            ).exclude(id=self.id)
            
            if duplicados.exists():
                raise ValidationError(
                    f'Ya existe una persona con {self.tipo_documento} {self.numero_documento} en esta solicitud'
                )


class HistorialCambio(models.Model):
    """
    Historial de cambios de una solicitud
    Registra todas las acciones realizadas sobre la solicitud
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID'
    )
    
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name='historial_cambios',
        verbose_name='Solicitud'
    )
    
    fecha_cambio = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha del cambio'
    )
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Usuario',
        help_text='Usuario que realizó el cambio'
    )
    
    accion = models.CharField(
        max_length=255,
        verbose_name='Acción',
        help_text='Descripción de la acción realizada'
    )
    
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción',
        help_text='Detalles adicionales del cambio'
    )
    
    estado_anterior = models.CharField(
        max_length=50,
        choices=EstadoSolicitud.choices,
        blank=True,
        null=True,
        verbose_name='Estado anterior'
    )
    
    estado_nuevo = models.CharField(
        max_length=50,
        choices=EstadoSolicitud.choices,
        blank=True,
        null=True,
        verbose_name='Estado nuevo'
    )
    
    class Meta:
        verbose_name = 'Historial de Cambio'
        verbose_name_plural = 'Historial de Cambios'
        ordering = ['-fecha_cambio']
        indexes = [
            models.Index(fields=['solicitud'], name='idx_historial_solicitud'),
            models.Index(fields=['fecha_cambio'], name='idx_historial_fecha'),
            models.Index(fields=['usuario'], name='idx_historial_usuario'),
        ]
    
    def __str__(self):
        return f"{self.accion} - {self.usuario.get_full_name() or self.usuario.username} - {self.fecha_cambio}"
    
    @classmethod
    def registrar_cambio(cls, solicitud, usuario, accion, descripcion=None, 
                        estado_anterior=None, estado_nuevo=None):
        """
        Método de conveniencia para registrar cambios
        """
        return cls.objects.create(
            solicitud=solicitud,
            usuario=usuario,
            accion=accion,
            descripcion=descripcion,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo
        )


# Señales para registrar automáticamente cambios en el historial
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=Solicitud)
def capturar_estado_anterior(sender, instance, **kwargs):
    """Captura el estado anterior antes de guardar"""
    if instance.pk:
        try:
            instancia_anterior = Solicitud.objects.get(pk=instance.pk)
            instance._estado_anterior = instancia_anterior.estado
        except Solicitud.DoesNotExist:
            instance._estado_anterior = None
    else:
        instance._estado_anterior = None


@receiver(post_save, sender=Solicitud)
def registrar_cambio_estado_automatico(sender, instance, created, **kwargs):
    """Registra automáticamente cambios de estado en el historial"""
    if created:
        # Registrar creación
        HistorialCambio.registrar_cambio(
            solicitud=instance,
            usuario=instance.creada_por,
            accion='Solicitud creada',
            descripcion=f'Nueva solicitud con {instance.total_personas} persona(s)',
            estado_nuevo=instance.estado
        )
    else:
        # Verificar si cambió el estado
        estado_anterior = getattr(instance, '_estado_anterior', None)
        if estado_anterior and estado_anterior != instance.estado:
            # Determinar usuario (podría ser más sofisticado)
            usuario = instance.asignada_a or instance.creada_por
            
            HistorialCambio.registrar_cambio(
                solicitud=instance,
                usuario=usuario,
                accion=f'Cambio de estado: {estado_anterior} → {instance.estado}',
                estado_anterior=estado_anterior,
                estado_nuevo=instance.estado
            )
