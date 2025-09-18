# euro_terceros/email_service.py
"""
Servicio centralizado para el envío de correos de terceros
Implementa la funcionalidad completa según documentación
"""

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .config import DESTINATARIOS_PREDETERMINADOS, EMAIL_CONFIG, EMAIL_TEMPLATES
import logging
import os

logger = logging.getLogger(__name__)

class TerceroEmailService:
    """Servicio centralizado para envío de correos de terceros aprobados"""
    
    def __init__(self):
        self.from_email = EMAIL_CONFIG.get('DEFAULT_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)
    
    def enviar_email_aprobacion(self, tercero, destinatarios_adicionales=None, 
                               incluir_cert_bancaria=False, incluir_info_comercial=True, 
                               incluir_info_adicional=True):
        """
        Envía email de aprobación de tercero con datos estructurados
        
        Args:
            tercero: Instancia del modelo Tercero
            destinatarios_adicionales: Lista de emails adicionales
            incluir_cert_bancaria: Incluir certificación bancaria
            incluir_info_comercial: Incluir información comercial
            incluir_info_adicional: Incluir información adicional
            
        Returns:
            dict: Resultado del envío con éxito/error
        """
        try:
            # Validar estado del tercero
            if tercero.estado_aprobacion not in ['aprobado', 'aprobado_final']:
                return {
                    'success': False,
                    'error': f'Tercero debe estar aprobado. Estado actual: {tercero.estado_aprobacion}'
                }
            
            # Generar datos estructurados usando el método del modelo
            datos_contexto = tercero.generar_datos_para_correo(
                incluir_cert_bancaria=incluir_cert_bancaria,
                incluir_info_comercial=incluir_info_comercial,
                incluir_info_adicional=incluir_info_adicional
            )
            
            # Combinar destinatarios
            destinatarios_finales = list(DESTINATARIOS_PREDETERMINADOS)
            if destinatarios_adicionales:
                destinatarios_finales.extend(destinatarios_adicionales)
            
            # Eliminar duplicados manteniendo orden
            destinatarios_finales = list(dict.fromkeys(destinatarios_finales))
            
            # Renderizar plantillas
            template_config = EMAIL_TEMPLATES['tercero_aprobado']
            html_content = render_to_string(template_config['html'], datos_contexto)
            text_content = render_to_string(template_config['text'], datos_contexto)
            
            # Crear asunto
            subject = template_config['subject'].format(
                nombre_completo=datos_contexto['informacion_personal']['nombre_completo']
            )
            subject += " - EUROTERCEROS"
            
            # Crear email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=destinatarios_finales
            )
            email.attach_alternative(html_content, "text/html")
            
            # Adjuntar documentos si están disponibles
            if 'documentos' in datos_contexto:
                self._adjuntar_documentos(email, datos_contexto['documentos'])
            
            # Enviar email
            resultado = email.send()
            
            if resultado == 1:
                logger.info(f'Email de aprobación enviado exitosamente para tercero {tercero.id}')
                return {
                    'success': True,
                    'message': 'Correo enviado exitosamente',
                    'destinatarios': destinatarios_finales,
                    'tercero_id': str(tercero.id),
                    'tercero_nombre': datos_contexto['informacion_personal']['nombre_completo'],
                    'asunto': subject
                }
            else:
                logger.error(f'Error enviando email para tercero {tercero.id}: resultado={resultado}')
                return {
                    'success': False,
                    'error': 'Error en el envío del correo'
                }
                
        except Exception as e:
            logger.error(f'Error enviando email para tercero {tercero.id}: {str(e)}')
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}'
            }
    
    def _adjuntar_documentos(self, email, documentos):
        """Adjunta documentos PDF al email"""
        for tipo_doc, doc_info in documentos.items():
            try:
                # Construir ruta del archivo
                file_path = doc_info['url'].replace('/media/', '', 1)
                full_path = os.path.join(settings.MEDIA_ROOT, file_path)
                
                # Verificar que el archivo existe
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        contenido = f.read()
                    
                    # Adjuntar archivo
                    email.attach(doc_info['nombre'], contenido, 'application/pdf')
                    logger.info(f'Documento adjuntado: {doc_info["nombre"]}')
                else:
                    logger.warning(f'Archivo no encontrado: {full_path}')
                    
            except Exception as e:
                logger.error(f'Error adjuntando documento {tipo_doc}: {str(e)}')
    
    def generar_preview(self, tercero, incluir_cert_bancaria=False, 
                       incluir_info_comercial=True, incluir_info_adicional=True):
        """
        Genera preview del email sin enviarlo
        
        Returns:
            dict: HTML content y datos del preview
        """
        try:
            # Generar datos estructurados
            datos_contexto = tercero.generar_datos_para_correo(
                incluir_cert_bancaria=incluir_cert_bancaria,
                incluir_info_comercial=incluir_info_comercial,
                incluir_info_adicional=incluir_info_adicional
            )
            
            # Renderizar solo HTML
            template_config = EMAIL_TEMPLATES['tercero_aprobado']
            html_content = render_to_string(template_config['html'], datos_contexto)
            
            return {
                'success': True,
                'html_content': html_content,
                'datos': datos_contexto,
                'tercero_nombre': datos_contexto['informacion_personal']['nombre_completo']
            }
            
        except Exception as e:
            logger.error(f'Error generando preview para tercero {tercero.id}: {str(e)}')
            return {
                'success': False,
                'error': f'Error generando preview: {str(e)}'
            }
