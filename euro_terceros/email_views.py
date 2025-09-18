"""
Sistema de correos para terceros aprobados
- Configuración segura usando variables de entorno  
- Solo envío manual (no automático)
- Incluye RUT y certificación bancaria
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.html import strip_tags
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging
import os
from terceros.models import Tercero

# Importar configuración actualizada
from .config import (
    DESTINATARIOS_PREDETERMINADOS,
    ESTADOS_CORREO_PERMITIDOS, 
    EMAIL_TEMPLATES,
    EMAIL_CONFIG
)

logger = logging.getLogger(__name__)

# Estados permitidos para envío (constante reutilizable)
ESTADOS_PERMITIDOS = ESTADOS_CORREO_PERMITIDOS

OPCIONES_CONFIGURACION = [
    'incluir_cert_bancaria',
    'incluir_info_comercial', 
    'incluir_info_adicional'
]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def configuracion_email(request):
    """
    Obtener configuración del sistema de correos
    """
    try:
        configuracion = {
            'estados_permitidos': ESTADOS_PERMITIDOS,
            'plantillas_disponibles': ['tercero_aprobado'],
            'destinatarios_predeterminados': DESTINATARIOS_PREDETERMINADOS,
            'opciones_configuracion': OPCIONES_CONFIGURACION
        }
        
        return Response(configuracion, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo configuración de correo: {str(e)}")
        return Response(
            {'error': 'Error interno del servidor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_correo_tercero(request, tercero_id):
    """
    Enviar correo de aprobación de tercero
    """
    try:
        from terceros.models import Tercero
        from euro_terceros.email_service import EuroSpeedEmailService
        
        # Obtener tercero
        try:
            tercero = Tercero.objects.get(id=tercero_id)
        except Tercero.DoesNotExist:
            return Response(
                {'error': 'Tercero no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validar estado del tercero
        if tercero.estado_aprobacion not in ESTADOS_PERMITIDOS:
            return Response(
                {
                    'error': f'El tercero debe estar en uno de estos estados: {ESTADOS_PERMITIDOS}',
                    'estado_actual': tercero.estado_aprobacion
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener datos del request
        data = request.data
        destinatarios_adicionales = data.get('destinatarios_adicionales', [])
        
        # Validar emails adicionales
        emails_validos = []
        for email in destinatarios_adicionales:
            try:
                validate_email(email)
                emails_validos.append(email.strip().lower())
            except ValidationError:
                return Response(
                    {'error': f'Email inválido: {email}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Opciones de contenido
        opciones = {
            'incluir_cert_bancaria': data.get('incluir_cert_bancaria', False),
            'incluir_info_comercial': data.get('incluir_info_comercial', True),
            'incluir_info_adicional': data.get('incluir_info_adicional', True)
        }
        
        # Combinar destinatarios (predeterminados + adicionales sin duplicados)
        todos_destinatarios = list(set(DESTINATARIOS_PREDETERMINADOS + emails_validos))
        
        # Enviar correo usando el servicio existente mejorado
        resultado = enviar_correo_aprobacion_tercero(
            tercero=tercero,
            destinatarios=todos_destinatarios,
            opciones=opciones,
            usuario=request.user
        )
        
        if resultado['success']:
            return Response({
                'success': True,
                'message': 'Correo enviado exitosamente',
                'destinatarios': todos_destinatarios,
                'tercero_id': str(tercero_id),
                'tercero_nombre': tercero.get_nombre_completo()
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': f'Error enviando correo: {resultado["error"]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Error en enviar_correo_tercero: {str(e)}")
        return Response(
            {'error': f'Error enviando correo: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def preview_correo_tercero(request, tercero_id):
    """
    Generar vista previa del correo sin enviarlo
    """
    try:
        from terceros.models import Tercero
        
        # Obtener tercero
        try:
            tercero = Tercero.objects.get(id=tercero_id)
        except Tercero.DoesNotExist:
            return Response(
                {'error': 'Tercero no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validar estado del tercero
        if tercero.estado_aprobacion not in ESTADOS_PERMITIDOS:
            return Response(
                {
                    'error': f'El tercero debe estar en uno de estos estados: {ESTADOS_PERMITIDOS}',
                    'estado_actual': tercero.estado_aprobacion
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener datos del request dependiendo del método
        if request.method == 'GET':
            # Para GET, usar valores por defecto
            destinatarios_adicionales = []
            opciones = {
                'incluir_cert_bancaria': False,
                'incluir_info_comercial': True,
                'incluir_info_adicional': True
            }
            emails_validos = []
        else:
            # Para POST, obtener datos del body
            data = request.data
            destinatarios_adicionales = data.get('destinatarios_adicionales', [])
            
            # Validar emails adicionales
            emails_validos = []
            for email in destinatarios_adicionales:
                try:
                    validate_email(email)
                    emails_validos.append(email.strip().lower())
                except ValidationError:
                    return Response(
                        {'error': f'Email inválido: {email}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Opciones de contenido
            opciones = {
                'incluir_cert_bancaria': data.get('incluir_cert_bancaria', False),
                'incluir_info_comercial': data.get('incluir_info_comercial', True),
                'incluir_info_adicional': data.get('incluir_info_adicional', True)
            }
        
        # Combinar destinatarios
        todos_destinatarios = list(set(DESTINATARIOS_PREDETERMINADOS + emails_validos))
        
        # Generar preview
        preview = generar_preview_correo_tercero(tercero, opciones)
        
        return Response({
            'preview': {
                'subject': preview['subject'],
                'html_content': preview['html_content'],
                'text_content': preview['text_content'],
                'destinatarios': todos_destinatarios,
                'adjuntos': preview['adjuntos'],
                'tercero_info': {
                    'id': str(tercero_id),
                    'nombre': tercero.get_nombre_completo(),
                    'estado': tercero.estado_aprobacion
                }
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en preview_correo_tercero: {str(e)}")
        return Response(
            {'error': f'Error generando vista previa: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def enviar_correo_aprobacion_tercero(tercero, destinatarios, opciones, usuario):
    """
    Función para enviar correo de aprobación de tercero
    """
    try:
        import os
        
        # Generar datos para el template
        datos = {
            'identificacion': {
                'tipo_persona': getattr(tercero, 'tipo_persona', 'No especificado'),
                'tipo_documento': tercero.get_tipo_documento_display(),
                'numero_documento': tercero.numero_documento,
                'digito_verificacion': getattr(tercero, 'digito_verificacion', None),
            },
            'informacion_personal': {
                'nombre_completo': tercero.get_nombre_completo(),
                'nombres': getattr(tercero, 'nombres', tercero.get_nombre_completo().split()[0] if tercero.get_nombre_completo() else 'N/A'),
                'apellidos': getattr(tercero, 'apellidos', ' '.join(tercero.get_nombre_completo().split()[1:]) if tercero.get_nombre_completo() else 'N/A'),
                'razon_social': getattr(tercero, 'razon_social', tercero.get_nombre_completo()),
                'fecha_nacimiento': getattr(tercero, 'fecha_nacimiento', 'N/A'),
            },
            'informacion_contacto': {
                'email': tercero.email,
                'telefono': tercero.telefono,
                'celular': getattr(tercero, 'celular', tercero.telefono),
                'ciudad': getattr(tercero, 'ciudad', 'No especificada'),
                'direccion': tercero.direccion,
                'departamento': getattr(tercero, 'departamento', 'No especificado'),
                'pais': getattr(tercero, 'pais', 'Colombia'),
            },
            'fecha_aprobacion': tercero.updated_at.strftime('%d/%m/%Y %H:%M') if tercero.updated_at else None,
            'usuario_envio': usuario.get_full_name() or usuario.username,
            'fecha_envio': timezone.now().strftime('%d/%m/%Y %H:%M'),
        }
        
        # Información comercial
        if opciones.get('incluir_info_comercial', True):
            datos['info_comercial'] = {
                'asignado_a': tercero.asignado_a.get_full_name() if tercero.asignado_a else 'No asignado',
                'observaciones_comercial': tercero.observaciones_comercial or 'Sin observaciones',
            }
        
        # Información adicional  
        if opciones.get('incluir_info_adicional', True):
            datos['info_adicional'] = {
                'created_by': getattr(tercero, 'created_by', None).get_full_name() if getattr(tercero, 'created_by', None) else 'Sistema',
                'observaciones_procesos': getattr(tercero, 'observaciones_procesos', None) or 'Sin observaciones',
                'observaciones_admin': getattr(tercero, 'observaciones_admin', None) or 'Sin observaciones',
            }
            
        # Certificación bancaria
        if opciones.get('incluir_cert_bancaria', False):
            datos['cert_bancaria'] = {
                'banco': getattr(tercero, 'banco', 'No especificado'),
                'tipo_cuenta': getattr(tercero, 'tipo_cuenta', 'No especificado'),
                'numero_cuenta': getattr(tercero, 'numero_cuenta', 'No especificado'),
            }
        
        # Generar contenido del correo usando el template
        subject = f"Tercero Aprobado: {datos['informacion_personal']['nombre_completo']} - EUROTERCEROS"
        
        # Usar el template HTML que tenemos
        html_content = render_to_string('emails/tercero_aprobado.html', datos)
        text_content = render_to_string('emails/tercero_aprobado.txt', datos)
        
        # Log para debugging
        logger.info(f"=== ENVIANDO CORREO ===")
        logger.info(f"Subject: {subject}")
        logger.info(f"Destinatarios recibidos: {destinatarios}")
        logger.info(f"Predeterminados configurados: {DESTINATARIOS_PREDETERMINADOS}")
        
        # Asegurar que los predeterminados estén incluidos SIEMPRE
        destinatarios_finales = list(DESTINATARIOS_PREDETERMINADOS)  # Empezar con predeterminados
        
        # Agregar destinatarios adicionales (sin duplicados)
        for email in destinatarios:
            if email and email not in destinatarios_finales:
                destinatarios_finales.append(email)
        
        logger.info(f"Destinatarios finales: {destinatarios_finales}")
        
        # Crear mensaje de correo
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.EMAIL_HOST_USER,
            to=destinatarios_finales
        )
        msg.attach_alternative(html_content, "text/html")
        
        # 📎 Adjuntar documentos del tercero (RUT y certificación bancaria)
        try:
            documentos_adjuntar = tercero._obtener_documentos_para_correo()
            
            if documentos_adjuntar:
                logger.info(f"Adjuntando {len(documentos_adjuntar)} documentos: {list(documentos_adjuntar.keys())}")
                
                for tipo_doc, doc_info in documentos_adjuntar.items():
                    try:
                        # Usar el path directo si está disponible
                        if 'path' in doc_info and os.path.exists(doc_info['path']):
                            with open(doc_info['path'], 'rb') as f:
                                contenido = f.read()
                            
                            # Adjuntar archivo con nombre descriptivo
                            msg.attach(doc_info['nombre'], contenido, 'application/pdf')
                            logger.info(f"Documento adjuntado: {doc_info['nombre']} ({doc_info['tipo_display']})")
                        else:
                            logger.warning(f"Archivo no encontrado para {tipo_doc}: {doc_info.get('path', 'Sin path')}")
                            
                    except Exception as attach_error:
                        logger.error(f"Error adjuntando {tipo_doc}: {str(attach_error)}")
                        # Continuar con otros documentos
                        continue
            else:
                logger.warning("No se encontraron documentos RUT o certificación bancaria para adjuntar")
                
        except Exception as documentos_error:
            logger.error(f"Error obteniendo documentos para adjuntar: {str(documentos_error)}")
            # Continuar con el envío sin documentos
        
        # Enviar correo con manejo de errores detallado
        try:
            logger.info("Intentando enviar correo...")
            result = msg.send(fail_silently=False)
            logger.info(f"Correo enviado exitosamente. Resultado: {result}")
            logger.info(f"Enviado desde: {settings.EMAIL_HOST_USER}")
            logger.info(f"Enviado a: {destinatarios_finales}")
            
            # Retornar diccionario estructurado
            return {
                'success': True,
                'result': result,
                'destinatarios': destinatarios_finales,
                'subject': subject
            }
        except Exception as email_error:
            logger.error(f"Error enviando correo: {str(email_error)}")
            logger.error(f"Configuración SMTP: Host={settings.EMAIL_HOST}, Port={settings.EMAIL_PORT}")
            return {
                'success': False,
                'error': str(email_error)
            }
        
    except Exception as e:
        logger.error(f"Error enviando correo de aprobación: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def generar_preview_correo_tercero(tercero, opciones):
    """
    Generar preview del correo sin enviarlo
    """
    try:
        import os
        
        # Generar datos igual que en envío real
        datos = {
            'identificacion': {
                'tipo_persona': getattr(tercero, 'tipo_persona', 'No especificado'),
                'tipo_documento': tercero.get_tipo_documento_display(),
                'numero_documento': tercero.numero_documento,
                'digito_verificacion': getattr(tercero, 'digito_verificacion', None),
            },
            'informacion_personal': {
                'nombre_completo': tercero.get_nombre_completo(),
                'nombres': getattr(tercero, 'nombres', tercero.get_nombre_completo().split()[0] if tercero.get_nombre_completo() else 'N/A'),
                'apellidos': getattr(tercero, 'apellidos', ' '.join(tercero.get_nombre_completo().split()[1:]) if tercero.get_nombre_completo() else 'N/A'),
                'razon_social': getattr(tercero, 'razon_social', tercero.get_nombre_completo()),
                'fecha_nacimiento': getattr(tercero, 'fecha_nacimiento', 'N/A'),
            },
            'informacion_contacto': {
                'email': tercero.email,
                'telefono': tercero.telefono,
                'celular': getattr(tercero, 'celular', tercero.telefono),
                'ciudad': getattr(tercero, 'ciudad', 'No especificada'),
                'direccion': tercero.direccion,
                'departamento': getattr(tercero, 'departamento', 'No especificado'),
                'pais': getattr(tercero, 'pais', 'Colombia'),
            },
            'fecha_aprobacion': tercero.updated_at.strftime('%d/%m/%Y %H:%M') if tercero.updated_at else None,
            'usuario_envio': 'Vista Previa',
            'fecha_envio': timezone.now().strftime('%d/%m/%Y %H:%M'),
        }
        
        # Información comercial
        if opciones.get('incluir_info_comercial', True):
            datos['info_comercial'] = {
                'asignado_a': tercero.asignado_a.get_full_name() if tercero.asignado_a else 'No asignado',
                'observaciones_comercial': tercero.observaciones_comercial or 'Sin observaciones',
            }
        
        # Certificación bancaria
        if opciones.get('incluir_cert_bancaria', False):
            datos['cert_bancaria'] = {
                'banco': getattr(tercero, 'banco', 'No especificado'),
                'tipo_cuenta': getattr(tercero, 'tipo_cuenta', 'No especificado'),
                'numero_cuenta': getattr(tercero, 'numero_cuenta', 'No especificado'),
            }
        
        # Generar contenido
        nombre_completo = tercero.get_nombre_completo()
        subject = f"Tercero Aprobado: {nombre_completo}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="background-color: #f8f9fa; padding: 20px; text-align: center;">
                <h2 style="color: #28a745;">✅ Tercero Aprobado</h2>
                <p>Sistema de Gestión de Terceros - EUROSPEED</p>
            </div>
            
            <div style="padding: 20px;">
                <div style="margin: 15px 0; padding: 10px; border-left: 4px solid #007bff;">
                    <h3>📋 Información del Tercero</h3>
                    <p><strong>Nombre:</strong> {nombre_completo}</p>
                    <p><strong>Documento:</strong> {datos['identificacion']['tipo_documento']} - {datos['identificacion']['numero_documento']}</p>
                    <p><strong>Email:</strong> {datos['informacion_contacto']['email']}</p>
                    <p><strong>Estado:</strong> {tercero.get_estado_aprobacion_display()}</p>
                </div>
                
                {'<div style="margin: 15px 0; padding: 10px; border-left: 4px solid #007bff;"><h3>🏢 Información Comercial</h3><p><strong>Asignado a:</strong> ' + datos['info_comercial']['asignado_a'] + '</p></div>' if opciones.get('incluir_info_comercial') else ''}
                
                {'<div style="margin: 15px 0; padding: 10px; border-left: 4px solid #007bff;"><h3>💳 Certificación Bancaria</h3><p><strong>Banco:</strong> ' + datos['cert_bancaria']['banco'] + '</p></div>' if opciones.get('incluir_cert_bancaria') else ''}
                
                <p>Los documentos del tercero se encontrarán adjuntos al correo.</p>
                
                <hr>
                <p><em>Este es un correo automático del Sistema de Gestión de Terceros EUROSPEED.</em></p>
            </div>
        </body>
        </html>
        """
        
        text_content = strip_tags(html_content)
        
        # Obtener adjuntos disponibles
        adjuntos = []
        campos_archivo = [
            'documento_identidad',
            'rut', 
            'camara_comercio',
            'estados_financieros',
            'certificacion_bancaria',
            'autorizacion_datos'
        ]
        
        for campo in campos_archivo:
            archivo = getattr(tercero, campo, None)
            if archivo and hasattr(archivo, 'name'):
                adjuntos.append(os.path.basename(archivo.name))
        
        return {
            'subject': subject,
            'html_content': html_content,
            'text_content': text_content,
            'adjuntos': adjuntos
        }
        
    except Exception as e:
        logger.error(f"Error generando preview: {str(e)}")
        raise Exception(f"Error generando vista previa: {str(e)}")
