from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import logging

from .models import Notificacion, PreferenciasNotificacion
from .utils import NotificationService

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender='terceros.Tercero')
def tercero_cambio_estado(sender, instance, created, **kwargs):
    """
    Crear notificaciones cuando cambie el estado de un tercero
    """
    if created:
        # Tercero recién creado
        if instance.asignado_a:
            NotificationService.crear_notificacion_tercero_asignado(
                instance, instance.asignado_a
            )
    else:
        # Tercero actualizado - verificar cambios de estado
        if hasattr(instance, '_state_changed'):
            # Solo si realmente cambió el estado
            NotificationService.crear_notificacion_cambio_estado(instance)


@receiver(post_save, sender='terceros.DocumentoTercero')
def documento_subido(sender, instance, created, **kwargs):
    """
    Crear notificación cuando se suba un documento
    """
    if created:
        NotificationService.crear_notificacion_documento_subido(instance)


@receiver(post_save, sender=User)
def usuario_creado_o_modificado(sender, instance, created, **kwargs):
    """
    Crear notificaciones cuando se cree o modifique un usuario
    """
    if created:
        # Usuario recién creado
        NotificationService.crear_notificacion_usuario_creado(instance)
        
        # Crear preferencias por defecto
        PreferenciasNotificacion.get_or_create_for_user(instance)
    else:
        # Usuario modificado - verificar cambio de rol
        if hasattr(instance, '_role_changed'):
            NotificationService.crear_notificacion_rol_cambiado(instance)


@receiver(post_save, sender='terceros.RevisionCumplimiento')
def revision_cumplimiento_realizada(sender, instance, created, **kwargs):
    """
    Crear notificación cuando se realice una revisión de cumplimiento
    """
    if created:
        NotificationService.crear_notificacion_revision_cumplimiento(instance)
