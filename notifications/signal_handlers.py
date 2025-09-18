from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from terceros.models import Tercero, DocumentoTercero, RevisionCumplimiento
from notifications.utils import NotificationService
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tercero)
def notificar_cambio_tercero(sender, instance, created, **kwargs):
    """
    Notificar cuando se cree o actualice un tercero
    """
    try:
        if created:
            # Tercero recién creado
            if instance.asignado_a:
                NotificationService.crear_notificacion_tercero_asignado(
                    instance, instance.asignado_a
                )
                logger.info(f"Notificación de tercero asignado creada para {instance.asignado_a.username}")
        else:
            # Tercero actualizado
            # Verificar si cambió el estado
            old_instance = getattr(instance, '_old_instance', None)
            if old_instance and old_instance.estado_aprobacion != instance.estado_aprobacion:
                NotificationService.crear_notificacion_cambio_estado(instance)
                logger.info(f"Notificación de cambio de estado creada para tercero {instance.id}")
            
            # Verificar si cambió la asignación de comercial
            if old_instance and old_instance.asignado_a != instance.asignado_a and instance.asignado_a:
                NotificationService.crear_notificacion_tercero_asignado(
                    instance, instance.asignado_a
                )
                logger.info(f"Notificación de reasignación creada para {instance.asignado_a.username}")
    
    except Exception as e:
        logger.error(f"Error en notificar_cambio_tercero: {e}")


@receiver(post_save, sender=DocumentoTercero)
def notificar_documento_subido(sender, instance, created, **kwargs):
    """
    Notificar cuando se suba un documento
    """
    if created:
        try:
            NotificationService.crear_notificacion_documento_subido(instance)
            logger.info(f"Notificación de documento subido creada para tercero {instance.tercero.id}")
        except Exception as e:
            logger.error(f"Error en notificar_documento_subido: {e}")


@receiver(post_save, sender=User)
def notificar_usuario_cambios(sender, instance, created, **kwargs):
    """
    Notificar cuando se cree o modifique un usuario
    """
    try:
        if created:
            # Usuario recién creado
            NotificationService.crear_notificacion_usuario_creado(instance)
            logger.info(f"Notificación de usuario creado enviada para {instance.username}")
        else:
            # Usuario modificado - verificar cambio de rol
            old_instance = getattr(instance, '_old_instance', None)
            if old_instance and old_instance.role != instance.role:
                NotificationService.crear_notificacion_rol_cambiado(instance)
                logger.info(f"Notificación de cambio de rol enviada para {instance.username}")
    
    except Exception as e:
        logger.error(f"Error en notificar_usuario_cambios: {e}")


@receiver(post_save, sender=RevisionCumplimiento)
def notificar_revision_cumplimiento(sender, instance, created, **kwargs):
    """
    Notificar cuando se realice una revisión de cumplimiento
    """
    if created:
        try:
            NotificationService.crear_notificacion_revision_cumplimiento(instance)
            logger.info(f"Notificación de revisión de cumplimiento creada para tercero {instance.tercero.id}")
        except Exception as e:
            logger.error(f"Error en notificar_revision_cumplimiento: {e}")


# Función para agregar instancia anterior a los modelos para detectar cambios
def add_old_instance(sender, **kwargs):
    """
    Agregar instancia anterior para detectar cambios
    """
    try:
        instance = kwargs.get('instance')
        if instance and instance.pk:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_instance = old_instance
    except sender.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error en add_old_instance: {e}")


# Conectar las señales pre_save para capturar el estado anterior
from django.db.models.signals import pre_save

pre_save.connect(add_old_instance, sender=Tercero)
pre_save.connect(add_old_instance, sender=User)
