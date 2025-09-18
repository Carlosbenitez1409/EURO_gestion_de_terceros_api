"""
Servicio de correos para EUROSPEED
Maneja el envío de notificaciones por email
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

class EuroSpeedEmailService:
    """Servicio centralizado para envío de correos"""
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@euroterceros.com')
    
    def enviar_notificacion_asignacion(self, tercero, usuario_asignado, tipo_asignacion):
        """
        Envía notificación cuando se asigna un tercero a un usuario
        """
        subject = f'EUROSPEED - Nuevo tercero asignado: {tercero.numero_documento}'
        
        message = f"""
        Hola {usuario_asignado.first_name},
        
        Se te ha asignado un nuevo tercero para revisión:
        
        📋 Información del Tercero:
        - Documento: {tercero.numero_documento}
        - Nombre: {tercero.get_nombre_completo()}
        - Email: {tercero.email}
        - Estado: {tercero.get_estado_aprobacion_display()}
        - Tipo de asignación: {tipo_asignacion}
        
        Por favor, ingresa al sistema para revisar y procesar este tercero.
        
        Saludos,
        Sistema EUROSPEED
        """
        
        try:
            result = send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[usuario_asignado.email],
                fail_silently=False
            )
            
            logger.info(f"Correo de asignación enviado a {usuario_asignado.email} para tercero {tercero.numero_documento}")
            return result
            
        except Exception as e:
            logger.error(f"Error enviando correo de asignación: {str(e)}")
            return False
    
    def enviar_notificacion_cambio_estado(self, tercero, usuario, estado_anterior, estado_nuevo):
        """
        Envía notificación cuando cambia el estado de un tercero
        """
        subject = f'EUROSPEED - Cambio de estado: {tercero.numero_documento}'
        
        message = f"""
        Notificación de cambio de estado en EUROSPEED
        
        📋 Tercero: {tercero.numero_documento} - {tercero.get_nombre_completo()}
        
        📊 Cambio de Estado:
        - Estado anterior: {estado_anterior}
        - Estado nuevo: {estado_nuevo}
        - Procesado por: {usuario.get_full_name() or usuario.username}
        - Fecha: {tercero.updated_at}
        
        Para más detalles, ingresa al sistema EUROSPEED.
        
        Saludos,
        Sistema EUROSPEED
        """
        
        # Enviar a usuario actual y otros relevantes
        recipients = [usuario.email]
        
        # Agregar otros usuarios según el estado
        if estado_nuevo == 'aprobado_comercial' and tercero.asignado_a_procesos:
            recipients.append(tercero.asignado_a_procesos.email)
        elif estado_nuevo == 'aprobado_procesos' and tercero.asignado_cumplimiento:
            recipients.append(tercero.asignado_cumplimiento.email)
        
        try:
            result = send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=recipients,
                fail_silently=False
            )
            
            logger.info(f"Correo de cambio de estado enviado para tercero {tercero.numero_documento}")
            return result
            
        except Exception as e:
            logger.error(f"Error enviando correo de cambio de estado: {str(e)}")
            return False
    
    def enviar_correo_prueba(self, destinatario):
        """
        Envía un correo de prueba para verificar configuración
        """
        subject = 'EUROSPEED - Correo de Prueba'
        
        message = f"""
        ¡Hola!
        
        Este es un correo de prueba del sistema EUROSPEED.
        
        ✅ El sistema de correos está funcionando correctamente.
        
        📧 Configuración actual:
        - Backend: {settings.EMAIL_BACKEND}
        - Desde: {self.from_email}
        - Destinatario: {destinatario}
        
        🎯 Sistema de Gestión de Terceros EUROSPEED
        Desarrollado para facilitar el proceso de aprobación y gestión.
        
        Saludos,
        Equipo EUROSPEED
        """
        
        try:
            result = send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[destinatario],
                fail_silently=False
            )
            
            logger.info(f"Correo de prueba enviado a {destinatario}")
            return result
            
        except Exception as e:
            logger.error(f"Error enviando correo de prueba: {str(e)}")
            return False

# Instancia global del servicio
email_service = EuroSpeedEmailService()

# Funciones de conveniencia
def enviar_notificacion_asignacion(tercero, usuario, tipo):
    return email_service.enviar_notificacion_asignacion(tercero, usuario, tipo)

def enviar_notificacion_cambio_estado(tercero, usuario, estado_ant, estado_nuevo):
    return email_service.enviar_notificacion_cambio_estado(tercero, usuario, estado_ant, estado_nuevo)

def enviar_correo_prueba(destinatario):
    return email_service.enviar_correo_prueba(destinatario)