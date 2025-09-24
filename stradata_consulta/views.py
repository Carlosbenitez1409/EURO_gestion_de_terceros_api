from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging

from terceros.models import Tercero
from .models import StrataDataDocumento
from .serializers import StrataDataDocumentoSerializer, StrataDataDocumentoUploadSerializer

logger = logging.getLogger(__name__)


class StratadaDocumentoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar documentos de Stradata
    """
    serializer_class = StrataDataDocumentoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar documentos por tercero si se especifica"""
        tercero_id = self.kwargs.get('tercero_id')
        if tercero_id:
            return StrataDataDocumento.objects.filter(tercero_id=tercero_id)
        return StrataDataDocumento.objects.all()
    
    def get_serializer_class(self):
        """Usar serializer específico para subida"""
        if self.action == 'create':
            return StrataDataDocumentoUploadSerializer
        return StrataDataDocumentoSerializer
    
    @action(detail=True, methods=['get'])
    def descargar(self, request, pk=None):
        """
        Acción personalizada para descargar documento
        GET /api/stradata/documentos/{id}/descargar/
        """
        documento = self.get_object()
        
        # Verificar que el archivo existe
        if not documento.archivo:
            return Response({
                'success': False,
                'error': 'Archivo no encontrado',
                'message': 'El documento no tiene archivo asociado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Importar HttpResponse para la descarga
        from django.http import HttpResponse
        import mimetypes
        import os
        
        try:
            archivo_path = documento.archivo.path
            
            # Determinar el tipo MIME
            content_type, _ = mimetypes.guess_type(archivo_path)
            if content_type is None:
                content_type = 'application/octet-stream'
            
            # Leer el archivo
            with open(archivo_path, 'rb') as archivo:
                response = HttpResponse(archivo.read(), content_type=content_type)
                
                # Configurar headers para descarga
                filename = documento.nombre or os.path.basename(archivo_path)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = os.path.getsize(archivo_path)
                
                logger.info(f"Documento Stradata descargado (ViewSet): {documento.nombre} por {request.user}")
                
                return response
                
        except FileNotFoundError:
            return Response({
                'success': False,
                'error': 'Archivo no encontrado',
                'message': 'El archivo físico no se encuentra en el servidor'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def create(self, request, *args, **kwargs):
        """Crear nuevo documento de Stradata"""
        tercero_id = self.kwargs.get('tercero_id')
        
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Usar el serializer de upload
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Guardar el documento asociado al tercero y usuario
            documento = serializer.save(
                tercero=tercero,
                subido_por=request.user
            )
            
            # Usar el serializer completo para la respuesta
            response_serializer = StrataDataDocumentoSerializer(documento)
            
            logger.info(f"Documento Stradata subido para tercero {tercero.numero_documento} por {request.user}")
            
            return Response({
                'success': True,
                'message': 'Documento subido exitosamente',
                'documento': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def list(self, request, *args, **kwargs):
        """Listar documentos de Stradata para un tercero"""
        tercero_id = self.kwargs.get('tercero_id')
        
        if tercero_id:
            # Verificar que el tercero existe
            tercero = get_object_or_404(Tercero, id=tercero_id)
            
            # Obtener documentos del tercero
            documentos = self.get_queryset()
            serializer = self.get_serializer(documentos, many=True)
            
            return Response({
                'success': True,
                'tercero_id': str(tercero.id),
                'numero_documento': tercero.numero_documento,
                'documentos': serializer.data,
                'total_documentos': documentos.count()
            }, status=status.HTTP_200_OK)
        
        # Listar todos los documentos (para admin)
        return super().list(request, *args, **kwargs)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subir_documento_stradata(request, tercero_id):
    """
    Endpoint específico para subir documentos de Stradata
    POST /api/stradata/terceros/{tercero_id}/documentos/subir/
    """
    try:
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Validar que hay un archivo en la petición
        if 'archivo' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No se proporcionó ningún archivo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        archivo = request.FILES['archivo']
        descripcion = request.data.get('descripcion', '')
        tipo_consulta = request.data.get('tipo_consulta', 'Búsqueda Unificada')
        
        # Crear el documento
        documento = StrataDataDocumento.objects.create(
            tercero=tercero,
            archivo=archivo,
            descripcion=descripcion,
            tipo_consulta=tipo_consulta,
            subido_por=request.user
        )
        
        # Serializar respuesta
        serializer = StrataDataDocumentoSerializer(documento)
        
        logger.info(f"Documento Stradata '{archivo.name}' subido para tercero {tercero.numero_documento}")
        
        return Response({
            'success': True,
            'message': 'Documento subido exitosamente',
            'documento': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error subiendo documento Stradata: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_documentos_stradata(request, tercero_id):
    """
    Endpoint específico para listar documentos de Stradata
    GET /api/stradata/terceros/{tercero_id}/documentos/
    """
    try:
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Obtener documentos
        documentos = StrataDataDocumento.objects.filter(tercero=tercero)
        serializer = StrataDataDocumentoSerializer(documentos, many=True)
        
        return Response({
            'success': True,
            'tercero_id': str(tercero.id),
            'numero_documento': tercero.numero_documento,
            'documentos': serializer.data,
            'total_documentos': documentos.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listando documentos Stradata: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def eliminar_documento_stradata(request, documento_id):
    """
    Endpoint para eliminar un documento de Stradata
    DELETE /api/stradata/documentos/{documento_id}/eliminar/
    """
    try:
        # Buscar el documento
        documento = get_object_or_404(StrataDataDocumento, id=documento_id)
        
        # Verificar permisos (opcional: agregar validación de propiedad/rol)
        if not request.user.is_staff and documento.subido_por != request.user:
            return Response({
                'success': False,
                'error': 'Sin permisos',
                'message': 'No tienes permisos para eliminar este documento'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Guardar información del documento antes de eliminarlo
        documento_info = {
            'id': documento.id,
            'nombre': documento.nombre,
            'tercero_id': str(documento.tercero.id)
        }
        
        # Eliminar el archivo físico si existe
        if documento.archivo and hasattr(documento.archivo, 'path'):
            try:
                import os
                if os.path.exists(documento.archivo.path):
                    os.remove(documento.archivo.path)
                    logger.info(f"Archivo físico eliminado: {documento.archivo.path}")
            except Exception as file_error:
                logger.warning(f"Error eliminando archivo físico: {str(file_error)}")
        
        # Eliminar el documento de la base de datos
        documento.delete()
        
        logger.info(f"Documento Stradata eliminado: {documento_info['nombre']} por {request.user}")
        
        return Response({
            'success': True,
            'message': 'Documento eliminado exitosamente',
            'documento': documento_info
        }, status=status.HTTP_200_OK)
        
    except StrataDataDocumento.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Documento no encontrado',
            'message': 'El documento solicitado no existe'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error eliminando documento Stradata: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def descargar_documento_stradata(request, documento_id):
    """
    Endpoint para descargar un documento de Stradata
    GET /api/stradata/documentos/{documento_id}/descargar/
    """
    try:
        # Buscar el documento
        documento = get_object_or_404(StrataDataDocumento, id=documento_id)
        
        # Verificar que el archivo existe
        if not documento.archivo:
            return Response({
                'success': False,
                'error': 'Archivo no encontrado',
                'message': 'El documento no tiene archivo asociado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que el archivo físico existe
        if not documento.archivo.storage.exists(documento.archivo.name):
            return Response({
                'success': False,
                'error': 'Archivo no encontrado',
                'message': 'El archivo físico no existe en el servidor'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Importar HttpResponse para la descarga
        from django.http import HttpResponse, Http404
        import mimetypes
        import os
        
        # Obtener el archivo
        try:
            archivo_path = documento.archivo.path
            
            # Determinar el tipo MIME
            content_type, _ = mimetypes.guess_type(archivo_path)
            if content_type is None:
                content_type = 'application/octet-stream'
            
            # Leer el archivo
            with open(archivo_path, 'rb') as archivo:
                response = HttpResponse(archivo.read(), content_type=content_type)
                
                # Configurar headers para descarga
                filename = documento.nombre or os.path.basename(archivo_path)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = os.path.getsize(archivo_path)
                
                # Headers adicionales
                response['Cache-Control'] = 'no-cache'
                response['X-Documento-ID'] = str(documento.id)
                response['X-Documento-UUID'] = str(documento.uuid)
                
                logger.info(f"Documento Stradata descargado: {documento.nombre} por {request.user}")
                
                return response
                
        except FileNotFoundError:
            return Response({
                'success': False,
                'error': 'Archivo no encontrado',
                'message': 'El archivo físico no se encuentra en el servidor'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except PermissionError:
            return Response({
                'success': False,
                'error': 'Error de permisos',
                'message': 'Sin permisos para acceder al archivo'
            }, status=status.HTTP_403_FORBIDDEN)
    
    except StrataDataDocumento.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Documento no encontrado',
            'message': 'El documento solicitado no existe'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error descargando documento Stradata: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def ejecutar_consulta_tercero_completo(request, tercero_id):
    """
    Endpoint para ejecutar consulta completa de un tercero y todas sus personas vinculadas
    POST /api/stradata/terceros/{tercero_id}/consultar/
    """
    try:
        # Validar credenciales
        credenciales = request.data.get('credenciales', {})
        
        if not credenciales or not credenciales.get('usuario') or not credenciales.get('password'):
            return Response({
                'success': False,
                'error': 'Credenciales requeridas',
                'message': 'Debe proporcionar usuario y password de Stradata'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener el tercero
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Construir lista completa de personas para consultar
        personas_para_consultar = []
        
        # 1. El tercero principal
        tipo_doc_tercero = 'NIT' if tercero.tipo_persona == 'juridica' else 'CC'
        personas_para_consultar.append({
            'nombre': tercero.get_nombre_completo(),
            'identificacion': tercero.numero_documento,
            'tipo': tipo_doc_tercero,
            'relacion': 'Principal'
        })
        
        # 2. Representantes legales
        for rep in tercero.representantes_legales.all():
            tipo_doc = {
                'cedula_ciudadania': 'CC',
                'cedula_extranjeria': 'CE', 
                'pasaporte': 'PP',
                'otro': 'CC'
            }.get(rep.tipo_identificacion, 'CC')
            
            personas_para_consultar.append({
                'nombre': rep.nombre_completo,
                'identificacion': rep.numero_identificacion,
                'tipo': tipo_doc,
                'relacion': 'Representante Legal'
            })
        
        # 3. Accionistas
        for accionista in tercero.accionistas.all():
            personas_para_consultar.append({
                'nombre': accionista.nombre,
                'identificacion': accionista.numero_identificacion,
                'tipo': accionista.tipo_identificacion,
                'relacion': f'Accionista ({accionista.porcentaje_participacion}%)'
            })
        
        # 4. Composición accionaria (si es diferente)
        for comp in tercero.composicion_accionaria.all():
            tipo_doc = {
                'cedula_ciudadania': 'CC',
                'cedula_extranjeria': 'CE',
                'nit': 'NIT',
                'pasaporte': 'PP',
                'otro': 'CC'
            }.get(comp.tipo_identificacion, 'CC')
            
            personas_para_consultar.append({
                'nombre': comp.nombre_razon_social,
                'identificacion': comp.numero_identificacion,
                'tipo': tipo_doc,
                'relacion': f'Composición Accionaria ({comp.porcentaje_participacion}%)'
            })
        
        # 5. Personas PEP relacionadas
        for pep in tercero.informacion_pep_nueva.all():
            personas_para_consultar.append({
                'nombre': pep.nombre,
                'identificacion': pep.numero_identificacion,
                'tipo': pep.tipo,
                'relacion': f'PEP - {pep.cargo} ({pep.parentesco})'
            })
        
        # Eliminar duplicados basados en número de identificación
        personas_unicas = {}
        for persona in personas_para_consultar:
            key = persona['identificacion']
            if key not in personas_unicas:
                personas_unicas[key] = persona
        
        personas_finales = list(personas_unicas.values())
        
        if not personas_finales:
            return Response({
                'success': False,
                'error': 'Sin personas para consultar',
                'message': 'El tercero no tiene información de personas para consultar'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Importar y usar el servicio de Stradata
        from .service import StrataDataService
        
        stradata_service = StrataDataService()
        
        # Hacer login
        login_success = stradata_service.login(
            credenciales['usuario'], 
            credenciales['password']
        )
        
        if not login_success:
            return Response({
                'success': False,
                'error': 'Error de autenticación',
                'message': 'No se pudo autenticar en Stradata. Verifique las credenciales.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Ejecutar consulta por lotes
        resultado = stradata_service.ejecutar_consulta_lotes(personas_finales)
        
        # Cerrar sesión
        stradata_service.close_session()
        
        # Log de la actividad
        logger.info(f"Consulta Stradata completa ejecutada por {request.user} - Tercero: {tercero.numero_documento} - {len(personas_finales)} personas")
        
        # Agregar información adicional al resultado
        if resultado.get('success'):
            resultado['tercero'] = {
                'id': str(tercero.id),
                'numero_documento': tercero.numero_documento,
                'nombre': tercero.get_nombre_completo()
            }
            resultado['personas_consultadas_detalle'] = personas_finales
            resultado['resumen_tipos'] = {
                'principal': 1,
                'representantes_legales': len([p for p in personas_finales if 'Representante Legal' in p.get('relacion', '')]),
                'accionistas': len([p for p in personas_finales if 'Accionista' in p.get('relacion', '')]),
                'composicion_accionaria': len([p for p in personas_finales if 'Composición Accionaria' in p.get('relacion', '')]),
                'pep': len([p for p in personas_finales if 'PEP' in p.get('relacion', '')])
            }
        
        # Determinar status code basado en el resultado
        if resultado.get('success'):
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        
        return Response(resultado, status=status_code)
        
    except Exception as e:
        logger.error(f"Error en consulta Stradata completa: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def ejecutar_consulta_stradata(request):
    """
    Endpoint para ejecutar consultas por lotes en Stradata
    POST /api/stradata/ejecutar/
    
    Payload esperado:
    {
        "credenciales": {
            "usuario": "usuario_stradata",
            "password": "password_stradata"
        },
        "personas": [
            {
                "nombre": "Nombre Persona",
                "identificacion": "123456789",
                "tipo": "CC"  // CC, NIT, etc.
            }
        ]
    }
    """
    try:
        # Validar datos de entrada
        credenciales = request.data.get('credenciales', {})
        personas = request.data.get('personas', [])
        
        if not credenciales or not credenciales.get('usuario') or not credenciales.get('password'):
            return Response({
                'success': False,
                'error': 'Credenciales requeridas',
                'message': 'Debe proporcionar usuario y password de Stradata'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not personas or not isinstance(personas, list):
            return Response({
                'success': False,
                'error': 'Datos de personas requeridos',
                'message': 'Debe proporcionar una lista de personas para consultar'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar estructura de personas
        for i, persona in enumerate(personas):
            if not isinstance(persona, dict):
                return Response({
                    'success': False,
                    'error': 'Formato inválido',
                    'message': f'Persona en posición {i} debe ser un objeto'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            required_fields = ['nombre', 'identificacion', 'tipo']
            for field in required_fields:
                if field not in persona or not persona[field]:
                    return Response({
                        'success': False,
                        'error': 'Campos requeridos',
                        'message': f'Persona en posición {i} debe tener: {", ".join(required_fields)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Importar y usar el servicio de Stradata
        from .service import StrataDataService
        
        stradata_service = StrataDataService()
        
        # Hacer login
        login_success = stradata_service.login(
            credenciales['usuario'], 
            credenciales['password']
        )
        
        if not login_success:
            return Response({
                'success': False,
                'error': 'Error de autenticación',
                'message': 'No se pudo autenticar en Stradata. Verifique las credenciales.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Ejecutar consulta por lotes
        resultado = stradata_service.ejecutar_consulta_lotes(personas)
        
        # Cerrar sesión
        stradata_service.close_session()
        
        # Log de la actividad
        logger.info(f"Consulta Stradata ejecutada por {request.user} - {len(personas)} personas")
        
        # Determinar status code basado en el resultado
        if resultado.get('success'):
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        
        return Response(resultado, status=status_code)
        
    except Exception as e:
        logger.error(f"Error en consulta Stradata: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Nuevas vistas para consulta Stradata integrada con terceros

from .service import StrataDataService

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def consultar_tercero_stradata(request, tercero_id):
    """
    Ejecuta consulta Stradata para un tercero y todas sus personas asociadas
    
    POST /stradata/consultar-tercero/{tercero_id}/
    Body: {
        "username": "usuario_stradata",
        "password": "password_stradata"
    }
    """
    try:
        # Validar datos de entrada
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'success': False,
                'error': 'Se requieren credenciales de Stradata (username y password)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener el tercero
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Preparar datos del tercero con todas sus relaciones
        tercero_data = _preparar_datos_tercero(tercero)
        
        # Ejecutar consulta Stradata
        service = StrataDataService()
        
        # Login en Stradata
        if not service.login(username, password):
            return Response({
                'success': False,
                'error': 'Error de autenticación en Stradata. Verifique sus credenciales.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Ejecutar consulta
        resultado = service.ejecutar_consulta_tercero(tercero_data, username)
        
        # Log de la operación
        logger.info(f"Consulta Stradata ejecutada para tercero {tercero_id} por usuario {request.user.username}")
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en consulta Stradata para tercero {tercero_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _preparar_datos_tercero(tercero):
    """
    Prepara los datos del tercero con todas sus relaciones para la consulta
    Actualizado para manejar tanto personas naturales como jurídicas
    """
    # Datos básicos del tercero
    tercero_data = {
        'id': tercero.id,
        'numero_documento': tercero.numero_documento,
        'tipo_documento': tercero.tipo_documento,
        'tipo_persona': getattr(tercero, 'tipo_persona', 'natural'),
    }
    
    # Agregar nombre según el tipo de persona
    if getattr(tercero, 'tipo_persona', 'natural') == 'juridica':
        # Para persona jurídica, usar razón social o nombres como fallback
        tercero_data['razon_social'] = tercero.nombres  # En el modelo, nombres almacena la razón social
        tercero_data['nombres'] = tercero.nombres
        tercero_data['apellidos'] = tercero.apellidos or ''
    else:
        # Para persona natural
        tercero_data['nombres'] = tercero.nombres
        tercero_data['apellidos'] = tercero.apellidos or ''
    
    # Representantes legales - CORREGIDO: usar numero_identificacion
    representantes = []
    if hasattr(tercero, 'representantes_legales'):
        for rep in tercero.representantes_legales.all():
            representantes.append({
                'nombre_completo': rep.nombre_completo,
                'numero_identificacion': rep.numero_identificacion,  # CORREGIDO
                'tipo_identificacion': rep.tipo_identificacion,
                'telefono': getattr(rep, 'telefono', ''),
                'direccion': getattr(rep, 'direccion', ''),
            })
    tercero_data['representantes_legales'] = representantes
    tercero_data['representantes'] = representantes  # Compatibilidad
    
    # Información PEP
    pep_info = []
    if hasattr(tercero, 'informacion_pep_nueva'):
        for pep in tercero.informacion_pep_nueva.all():
            pep_info.append({
                'nombre': pep.nombre,
                'numero_identificacion': pep.numero_identificacion,
                'tipo': pep.tipo,
                'cargo': getattr(pep, 'cargo', ''),
                'entidad': getattr(pep, 'entidad', ''),
                'parentesco': getattr(pep, 'parentesco', ''),
            })
    tercero_data['informacion_pep'] = pep_info
    tercero_data['informacion_pep_nueva'] = pep_info  # Compatibilidad
    
    # Accionistas con estructura jerárquica (incluir subaccionistas)
    accionistas = []
    subaccionistas = []
    
    if hasattr(tercero, 'accionistas'):
        # Obtener accionistas principales (nivel 0)
        accionistas_principales = tercero.accionistas.filter(nivel=0)
        
        for acc in accionistas_principales:
            # Agregar accionista principal
            accionista_data = {
                'nombre': acc.nombre,
                'numero_identificacion': acc.numero_identificacion,
                'tipo_identificacion': acc.tipo_identificacion,
                'porcentaje_participacion': getattr(acc, 'porcentaje_participacion', 0),
                'porcentaje': getattr(acc, 'porcentaje_participacion', 0),  # Compatibilidad
                'nivel': acc.nivel,
                'es_principal': True
            }
            accionistas.append(accionista_data)
            
            # Obtener y agregar subaccionistas recursivamente
            def obtener_subaccionistas_recursivo(accionista_padre, nivel=1):
                """Función recursiva para obtener todos los subaccionistas"""
                subaccionistas_lista = []
                
                for sub_acc in accionista_padre.get_sub_accionistas():
                    sub_data = {
                        'nombre': sub_acc.nombre,
                        'numero_identificacion': sub_acc.numero_identificacion,
                        'tipo_identificacion': sub_acc.tipo_identificacion,
                        'porcentaje_participacion': getattr(sub_acc, 'porcentaje_participacion', 0),
                        'porcentaje': getattr(sub_acc, 'porcentaje_participacion', 0),
                        'nivel': sub_acc.nivel,
                        'es_principal': False,
                        'accionista_padre': accionista_padre.nombre,
                        'accionista_padre_id': accionista_padre.numero_identificacion
                    }
                    subaccionistas_lista.append(sub_data)
                    
                    # Buscar subaccionistas del subaccionista (recursivo)
                    sub_subaccionistas = obtener_subaccionistas_recursivo(sub_acc, nivel + 1)
                    subaccionistas_lista.extend(sub_subaccionistas)
                
                return subaccionistas_lista
            
            # Obtener todos los subaccionistas de este accionista principal
            subs = obtener_subaccionistas_recursivo(acc)
            subaccionistas.extend(subs)
    
    tercero_data['accionistas'] = accionistas
    tercero_data['subaccionistas'] = subaccionistas
    tercero_data['todos_accionistas'] = accionistas + subaccionistas  # Lista combinada para procesamiento
    
    # Composición accionaria adicional
    composicion_accionaria = []
    if hasattr(tercero, 'composicion_accionaria'):
        for comp in tercero.composicion_accionaria.all():
            # Evitar duplicados con accionistas
            ya_existe = any(
                a['numero_identificacion'] == comp.numero_identificacion 
                for a in accionistas
            )
            if not ya_existe:
                composicion_accionaria.append({
                    'nombre_razon_social': comp.nombre_razon_social,
                    'numero_identificacion': comp.numero_identificacion,
                    'tipo_identificacion': comp.tipo_identificacion,
                    'porcentaje_participacion': getattr(comp, 'porcentaje_participacion', 0),
                })
    tercero_data['composicion_accionaria'] = composicion_accionaria
    
    return tercero_data


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resumen_personas_tercero(request, tercero_id):
    """
    Obtiene un resumen de todas las personas asociadas al tercero
    para mostrar antes de la consulta Stradata
    
    GET /stradata/resumen-personas/{tercero_id}/
    """
    try:
        tercero = get_object_or_404(Tercero, id=tercero_id)
        tercero_data = _preparar_datos_tercero(tercero)
        
        # Crear resumen de personas
        # Manejar nombre según tipo de persona
        if getattr(tercero, 'tipo_persona', 'natural') == 'juridica':
            nombre_completo = tercero.nombres  # Para jurídicas, nombres contiene la razón social
        else:
            nombre_completo = f"{tercero.nombres} {tercero.apellidos}".strip()
        
        resumen = {
            'tercero': {
                'nombre_completo': nombre_completo,
                'numero_documento': tercero.numero_documento,
            },
            'contadores': {
                'representantes_legales': len(tercero_data.get('representantes_legales', [])),
                'informacion_pep': len(tercero_data.get('informacion_pep', [])),
                'accionistas': len(tercero_data.get('accionistas', [])),
                'subaccionistas': len(tercero_data.get('subaccionistas', [])),
                'total_accionistas': len(tercero_data.get('todos_accionistas', [])),
            },
            'detalles': {}
        }
        
        # Detalles de representantes legales
        if tercero_data.get('representantes_legales'):
            resumen['detalles']['representantes_legales'] = [
                f"{rep.get('nombre_completo', '')} ({rep.get('numero_identificacion', '')})".strip()
                for rep in tercero_data['representantes_legales']
            ]
        
        # Detalles de personas PEP
        if tercero_data.get('informacion_pep'):
            resumen['detalles']['informacion_pep'] = [
                f"{pep.get('nombre', '')} ({pep.get('numero_identificacion', '')}) - {pep.get('parentesco', '')}"
                for pep in tercero_data['informacion_pep']
            ]
        
        # Detalles de accionistas
        if tercero_data.get('accionistas'):
            resumen['detalles']['accionistas'] = [
                f"{acc.get('nombre', '')} ({acc.get('numero_identificacion', '')}) - {acc.get('porcentaje_participacion', 0)}%".strip()
                for acc in tercero_data['accionistas']
            ]
        
        # Detalles de subaccionistas
        if tercero_data.get('subaccionistas'):
            resumen['detalles']['subaccionistas'] = [
                f"{sub.get('nombre', '')} ({sub.get('numero_identificacion', '')}) - {sub.get('porcentaje_participacion', 0)}% [Sub de: {sub.get('accionista_padre', '')}]".strip()
                for sub in tercero_data['subaccionistas']
            ]
        
        # Total de personas a consultar (incluir subaccionistas)
        total_personas = 1  # El tercero principal
        for categoria in ['representantes_legales', 'informacion_pep', 'todos_accionistas']:
            total_personas += len(tercero_data.get(categoria, []))
        
        resumen['total_personas_consultar'] = total_personas
        
        return Response({
            'success': True,
            'resumen': resumen
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen para tercero {tercero_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)