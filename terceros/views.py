from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Count, Q, Max
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from datetime import datetime
import logging
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
import io

User = get_user_model()

from .models import Tercero, DocumentoTercero, InformacionPEP, RepresentanteLegal, Accionista
from .serializers import (
    TerceroSerializer,
    TerceroListSerializer,
    TerceroStatsSerializer,
    TerceroPublicRegistrationSerializer,
    TerceroConDocumentosSerializer,
    DocumentoTerceroSerializer,
    TerceroVinculacionSerializer,
    TerceroCompleteSerializer,
    TerceroCompletoPEPSerializer,
    InformacionPEPSerializer,
    TerceroWorkflowSerializer
)
from .permissions import TerceroPermissions
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


class TercerosPagination(PageNumberPagination):
    """
    Paginación personalizada para terceros con configuración optimizada
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'results': data,
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
        })


def determinar_tipo_documento(archivo):
    """
    Determina el tipo de documento basado en la extensión del archivo.
    """
    # Obtiene la extensión del archivo
    extension = archivo.name.split('.')[-1].lower()

    # Lógica para determinar el tipo de documento basado en la extensión
    if extension == 'pdf':
        return 'RUT'
    elif extension in ['jpg', 'jpeg', 'png']:
        return 'Cedula'
    elif extension in ['doc', 'docx']:
        return 'Certificado'
    else:
        return 'Otros'

def determinar_tipo_documento_vinculacion(archivo, tipo_persona, clave_formdata=None):
    """
    Determina el tipo de documento para vinculación basado en:
    1. La clave del FormData (prioridad alta)
    2. El nombre del archivo y tipo de persona (fallback)
    """
    
    # Mapeo directo de claves FormData a tipos de documento
    mapeo_claves_formdata = {
        'documento-identidad': 'documento_identidad' if tipo_persona == 'natural' else 'documento_identidad_representante',
        'rut': 'rut',
        'firma': 'firma',  # Nuevo tipo de documento agregado
        'certificacion-bancaria': 'certificacion_bancaria',
        'certificacion-comercial': 'certificacion_comercial',
        'certificado-existencia': 'certificado_existencia_representacion',
        'composicion-accionaria': 'composicion_accionaria_certificada',
        'estados-financieros': 'estados_financieros_comparativos',
        'declaracion-renta': 'declaracion_renta',
    }
    
    # Si tenemos la clave del FormData, usarla primero
    if clave_formdata and clave_formdata in mapeo_claves_formdata:
        return mapeo_claves_formdata[clave_formdata]
    
    # Fallback: usar el método original basado en nombre del archivo
    nombre_archivo = archivo.name.lower()
    extension = archivo.name.split('.')[-1].lower()
    
    # Mapeo de palabras clave a tipos de documento
    mapeo_documentos = {
        'persona_natural': {
            'cedula': 'documento_identidad',
            'documento': 'documento_identidad',
            'identidad': 'documento_identidad',
            'rut': 'rut',
            'firma': 'firma',  # Nuevo mapeo agregado
            'comercial': 'certificacion_comercial',
            'bancaria': 'certificacion_bancaria',
            'bancario': 'certificacion_bancaria',
        },
        'persona_juridica': {
            'cedula': 'documento_identidad_representante',
            'documento': 'documento_identidad_representante',
            'representante': 'documento_identidad_representante',
            'rut': 'rut',
            'firma': 'firma',  # Nuevo mapeo agregado
            'existencia': 'certificado_existencia_representacion',
            'representacion': 'certificado_existencia_representacion',
            'accionaria': 'composicion_accionaria_certificada',
            'accionistas': 'composicion_accionaria_certificada',
            'financier': 'estados_financieros_comparativos',
            'balance': 'estados_financieros_comparativos',
            'renta': 'declaracion_renta',
            'declaracion': 'declaracion_renta',
            'comercial1': 'certificacion_comercial_1',
            'comercial2': 'certificacion_comercial_2',
            'comercial': 'certificacion_comercial_1',  # Por defecto primera
            'bancaria': 'certificacion_bancaria',
            'bancario': 'certificacion_bancaria',
        }
    }
    
    # Obtener mapeo según tipo de persona
    persona_key = 'persona_juridica' if tipo_persona == 'juridica' else 'persona_natural'
    documentos_tipo = mapeo_documentos.get(persona_key, {})
    
    # Buscar coincidencias en el nombre del archivo
    for palabra_clave, tipo_doc in documentos_tipo.items():
        if palabra_clave in nombre_archivo:
            return tipo_doc
    
    # Fallback por extensión
    if extension == 'pdf':
        return 'rut' if 'rut' in nombre_archivo else 'otros'
    elif extension in ['jpg', 'jpeg', 'png']:
        return 'documento_identidad' if tipo_persona == 'natural' else 'documento_identidad_representante'
    
    return 'otros'

class TerceroViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión completa de terceros con paginación optimizada
    """
    queryset = Tercero.objects.all().order_by('-created_at')
    serializer_class = TerceroSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [TerceroPermissions]
    pagination_class = TercerosPagination

    def get_serializer_class(self):
        """
        Usar serializer apropiado según la acción y autenticación
        """
        if self.action == 'list':
            return TerceroListSerializer
        elif self.action == 'create':
            if not self.request.user.is_authenticated:
                return TerceroCompleteSerializer  # Usar serializer completo para registro público
            return TerceroSerializer
        elif self.action == 'vinculacion_completa':
            return TerceroCompleteSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            # Usar serializer completo para consultas individuales (GET, PUT, PATCH)
            return TerceroCompleteSerializer
        return TerceroSerializer

    def get_queryset(self):
        """
        Filtrar terceros según parámetros de consulta con optimizaciones de performance
        """
        # Optimización: select_related y prefetch_related para evitar N+1 queries
        queryset = Tercero.objects.select_related(
            'asignado_a',
            'creado_por', 
            'aprobado_por',
            'usuario_ultimo_cambio'
        ).prefetch_related(
            'documentos',
            'historial'
        ).annotate(
            # Campos calculados para evitar queries adicionales
            documentos_count=Count('documentos', distinct=True)
        ).order_by('-created_at')

        # Filtro por comercial asignado con optimización
        assigned_to = self.request.query_params.get('assigned_to') or self.request.query_params.get('comercial_asignado')
        if assigned_to:
            if assigned_to == 'me':
                queryset = queryset.filter(asignado_a=self.request.user)
            else:
                queryset = queryset.filter(asignado_a_id=assigned_to)

        # Filtro por estado de aprobación
        estado = self.request.query_params.get('estado') or self.request.query_params.get('estado_aprobacion')
        if estado:
            queryset = queryset.filter(estado_aprobacion=estado)

        # Filtro por tipo de persona
        tipo_persona = self.request.query_params.get('tipo_persona')
        if tipo_persona:
            queryset = queryset.filter(tipo_persona=tipo_persona)

        # Filtro por tipo de formulario
        tipo_formulario = self.request.query_params.get('tipo_formulario')
        if tipo_formulario:
            queryset = queryset.filter(tipo_formulario=tipo_formulario)

        # Filtro por prioridad
        priority = self.request.query_params.get('priority') or self.request.query_params.get('prioridad_comercial')
        if priority:
            queryset = queryset.filter(prioridad_comercial=priority)

        # Búsqueda mejorada con múltiples campos
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nombres__icontains=search) |
                Q(apellidos__icontains=search) |
                Q(razon_social__icontains=search) |
                Q(numero_documento__icontains=search) |
                Q(email__icontains=search)
            )

        # Ordenamiento dinámico
        ordering = self.request.query_params.get('ordering')
        if ordering:
            # Validar que el campo de ordenamiento sea seguro
            valid_orderings = [
                'created_at', '-created_at',
                'fecha_ultimo_cambio_estado', '-fecha_ultimo_cambio_estado',
                'nombres', '-nombres',
                'apellidos', '-apellidos',
                'razon_social', '-razon_social',
                'estado_aprobacion', '-estado_aprobacion'
            ]
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        """
        Asignar usuario creador al crear tercero (si está autenticado)
        Para registro público, no asignar usuario creador
        """
        # Procesar asignación de comercial si viene en los datos
        comercial_asignado_id = None
        
        # Debug completo del request
        logger.info(f"Request method: {self.request.method}")
        logger.info(f"Request content type: {self.request.content_type}")
        logger.info(f"Request data keys: {list(self.request.data.keys()) if hasattr(self.request, 'data') else 'No data'}")
        logger.info(f"Request POST keys: {list(self.request.POST.keys()) if hasattr(self.request, 'POST') else 'No POST'}")
        
        # Inicializar variable
        comercial_asignado_id = None
        
        # Buscar comercialAsignado en diferentes lugares
        if hasattr(self.request, 'data') and 'comercialAsignado' in self.request.data:
            comercial_asignado_id = self.request.data.get('comercialAsignado')
            logger.info(f"Comercial asignado encontrado en request.data: {comercial_asignado_id}")
        elif hasattr(self.request, 'POST') and 'comercialAsignado' in self.request.POST:
            comercial_asignado_id = self.request.POST.get('comercialAsignado')
            logger.info(f"Comercial asignado encontrado en request.POST: {comercial_asignado_id}")
        else:
            logger.warning("Campo comercialAsignado NO encontrado en ningún lugar")
            logger.warning(f"Data disponible: {dict(self.request.data) if hasattr(self.request, 'data') else 'None'}")
        
        if self.request.user.is_authenticated:
            logger.info(f"Creating tercero by authenticated user: {self.request.user.username}")
            # Determinar estado inicial basado en tipo_formulario
            tipo_formulario = serializer.validated_data.get('tipo_formulario', 'vinculacion')
            
            # Estado inicial simplificado
            if tipo_formulario == 'actualizacion':
                estado_inicial = 'asignada_administrador'
            else:  # vinculacion - SIEMPRE tiene comercial (obligatorio)
                estado_inicial = 'en_curso_comercial'
            
            logger.info(f"Tipo de formulario: {tipo_formulario} -> Estado inicial: {estado_inicial}")
            
            kwargs = {
                'creado_por': self.request.user,
                'estado_aprobacion': estado_inicial
            }
            
            # SOLO asignar comercial si es tipo_formulario = 'vinculacion'
            if tipo_formulario == 'vinculacion':
                # Para vinculación, el comercial es OBLIGATORIO
                if not comercial_asignado_id:
                    return Response({
                        'error': 'Para vinculaciones, el comercial asignado es obligatorio'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Asignar comercial
                from accounts.models import User
                try:
                    comercial = User.objects.get(id=comercial_asignado_id, role='comercial')
                    kwargs['asignado_a'] = comercial
                    logger.info(f"Tercero asignado al comercial: {comercial.get_full_name()} (ID: {comercial.id})")
                except User.DoesNotExist:
                    return Response({
                        'error': f'Comercial con ID {comercial_asignado_id} no encontrado'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer.save(**kwargs)
        else:
            logger.info(f"Public tercero registration attempt from IP: {self.request.META.get('REMOTE_ADDR', 'unknown')}")
            # Determinar estado inicial basado en tipo_formulario para registro público
            tipo_formulario = serializer.validated_data.get('tipo_formulario', 'vinculacion')
            
            # TEMPORAL: Si frontend no envía tipo_formulario, inferir basado en comercial
            if 'tipo_formulario' not in serializer.validated_data:
                if comercial_asignado_id:
                    tipo_formulario = 'vinculacion'
                    logger.info(f"INFERIDO: comercial presente -> tipo_formulario = 'vinculacion'")
                else:
                    tipo_formulario = 'actualizacion'
                    logger.info(f"INFERIDO: sin comercial -> tipo_formulario = 'actualizacion'")
            
            # Estado inicial simplificado
            if tipo_formulario == 'actualizacion':
                estado_inicial = 'asignada_administrador'
            else:  # vinculacion - SIEMPRE tiene comercial (obligatorio)
                estado_inicial = 'en_curso_comercial'
            
            logger.info(f"Registro público - Tipo de formulario: {tipo_formulario} -> Estado inicial: {estado_inicial}")
            
            kwargs = {
                'creado_por': None,
                'estado_aprobacion': estado_inicial,
                'tipo_formulario': tipo_formulario  # Asegurar que se guarde el tipo inferido
            }
            logger.info(f"Procesando asignación comercial para registro público. comercial_asignado_id: {comercial_asignado_id}")
            
            # SOLO asignar comercial si es tipo_formulario = 'vinculacion'
            if tipo_formulario == 'vinculacion':
                # Para vinculación, el comercial es OBLIGATORIO
                if not comercial_asignado_id:
                    logger.error(f"Error en registro público: vinculación sin comercial asignado")
                    serializer.save(**kwargs)  # Guardar de todas formas pero logear error
                    logger.warning(f"Vinculación creada sin comercial - revisar frontend")
                else:
                    # Asignar comercial
                    logger.info(f"Iniciando asignación del comercial ID: {comercial_asignado_id}")
                    from accounts.models import User
                    from django.utils import timezone
                    try:
                        comercial = User.objects.get(id=comercial_asignado_id, role='comercial')
                        kwargs['asignado_a'] = comercial
                        kwargs['fecha_asignacion_comercial'] = timezone.now()
                        logger.info(f"Tercero de vinculación asignado al comercial: {comercial.get_full_name()} (ID: {comercial.id})")
                        logger.info(f"Estado: {estado_inicial} (vinculación con comercial)")
                        logger.info(f"kwargs para save: {kwargs}")
                    except User.DoesNotExist:
                        logger.warning(f"Comercial con ID {comercial_asignado_id} no encontrado en registro público")
            else:
                if tipo_formulario == 'actualizacion':
                    logger.info(f"Actualización va directo a administrador (sin comercial)")
                
            serializer.save(**kwargs)

    def perform_update(self, serializer):
        """
        Log de actualización
        """
        logger.info(f"Updating tercero {serializer.instance.id} by user: {self.request.user.username}")
        serializer.save()

    def update(self, request, *args, **kwargs):
        """
        Método update personalizado con validaciones por rol
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Crear serializer primero para obtener datos validados
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Validar permisos específicos para comerciales
        if hasattr(request.user, 'role') and request.user.role == 'comercial':
            # Campos permitidos para comerciales
            campos_permitidos_comercial = [
                'observaciones_comercial',
                'comentarios_aprobacion',
                'notas_internas',
                'fecha_contacto_inicial',
                'canal_contacto',
                'prioridad_comercial'
            ]
            
            # Si el tercero está devuelto a comercial, permitir cambio de estado
            if instance.estado_aprobacion == 'devuelto_comercial':
                campos_permitidos_comercial.append('estado_aprobacion')
                logger.info(f"Comercial {request.user.username} puede cambiar estado desde devuelto_comercial")
            
            # Verificar que solo se actualicen campos permitidos usando datos validados
            campos_enviados = set(serializer.validated_data.keys())
            campos_no_permitidos = campos_enviados - set(campos_permitidos_comercial)
            
            if campos_no_permitidos:
                return Response({
                    'error': f'Como comercial, solo puedes actualizar estos campos: {", ".join(campos_permitidos_comercial)}',
                    'campos_no_permitidos': list(campos_no_permitidos)
                }, status=status.HTTP_403_FORBIDDEN)

            # Verificar que el tercero esté asignado al comercial
            if instance.asignado_a != request.user:
                return Response({
                    'error': 'Solo puedes actualizar terceros asignados a ti'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Guardar estado anterior para historial
        estado_anterior = instance.estado_aprobacion
        
        self.perform_update(serializer)
        
        # Manejar cambio de estado para comerciales desde devuelto_comercial
        if (hasattr(request.user, 'role') and request.user.role == 'comercial' and 
            'estado_aprobacion' in serializer.validated_data and 
            estado_anterior == 'devuelto_comercial'):
            
            nuevo_estado = serializer.validated_data['estado_aprobacion']
            logger.info(f"Comercial {request.user.username} cambiando estado de {estado_anterior} a {nuevo_estado}")
            
            # Actualizar campos de seguimiento
            instance.usuario_ultimo_cambio = request.user
            instance.fecha_ultimo_cambio_estado = timezone.now()
            
            # Si pasa a en_curso_comercial, mantener la asignación al comercial
            if nuevo_estado == 'en_curso_comercial':
                instance.asignado_a = request.user
                instance.fecha_asignacion_actual = timezone.now()
                logger.info(f"Tercero {instance.id} asignado a comercial {request.user.username} en estado en_curso_comercial")
            
            instance.save()
            
            # Crear registro de historial
            try:
                from terceros.models import HistorialTercero
                HistorialTercero.objects.create(
                    tercero=instance,
                    fecha_accion=timezone.now(),
                    accion='cambio_estado_comercial',
                    estado_anterior=estado_anterior,
                    estado_nuevo=nuevo_estado,
                    usuario=request.user,
                    observaciones=f'Comercial retomó el proceso desde estado devuelto'
                )
                logger.info(f"Historial creado para cambio de estado {estado_anterior} -> {nuevo_estado}")
            except Exception as e:
                logger.error(f"Error creando historial: {e}")

        # NUEVA LÓGICA: Si es comercial y está agregando comentarios de aprobación, 
        # ejecutar aprobación automáticamente
        if (hasattr(request.user, 'role') and request.user.role == 'comercial' and 
            'comentarios_aprobacion' in serializer.validated_data and serializer.validated_data['comentarios_aprobacion']):
            
            logger.info(f"Ejecutando aprobación automática por comercial: {request.user.username}")
            
            # Ejecutar aprobación por comercial
            resultado_aprobacion = instance.aprobar_por_comercial(request.user)
            
            if resultado_aprobacion:
                logger.info(f"Tercero {instance.id} aprobado exitosamente por comercial {request.user.username}")
                
                # Crear notificación para administradores
                self.notify_administrators_of_approval(instance, request.user)
                
                # Recargar la instancia para obtener los datos actualizados
                instance.refresh_from_db()
                serializer = self.get_serializer(instance)
                
                # Respuesta con información de aprobación
                response_data = serializer.data
                response_data.update({
                    'aprobacion_ejecutada': True,
                    'mensaje_aprobacion': 'Tercero aprobado completamente y enviado al administrador',
                    'nuevo_estado': instance.get_estado_aprobacion_display(),
                    'asignado_administrador': instance.asignado_administrador.get_full_name() if instance.asignado_administrador else None
                })
                
                return Response(response_data)
            else:
                logger.error(f"Error en aprobación automática para tercero {instance.id}")

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """
        Método partial_update personalizado
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Log de eliminación
        """
        logger.info(f"Deleting tercero {instance.id} by user: {self.request.user.username}")
        super().perform_destroy(instance)

    def extract_form_data(self, request):
        """
        Extrae los datos del formulario del request, manejando tanto JSON como FormData
        """
        import json
        
        if hasattr(request, 'FILES') and request.FILES:
            # Si hay archivos, los datos vienen como FormData
            data = {}
            for key, value in request.data.items():
                if key != 'documentos':  # Excluir archivos de los datos del formulario
                    # Si es una lista de un solo elemento, extraer el elemento
                    if isinstance(value, list) and len(value) == 1:
                        data[key] = value[0]
                    else:
                        data[key] = value
                        
            # Parsear arrays JSON que vienen como strings
            arrays_json = ['informacionPEP', 'informacion_pep', 'representantes', 'accionistas', 'tiposOperacionesMonedaExtranjera', 'fuentesFondos', 'tiposRecursos']
            for array_field in arrays_json:
                if array_field in data and isinstance(data[array_field], str):
                    try:
                        data[array_field] = json.loads(data[array_field])
                    except json.JSONDecodeError:
                        logger.warning(f"No se pudo parsear {array_field} como JSON: {data[array_field]}")
                        data[array_field] = []
                        
            return data
        else:
            # Si no hay archivos, usar datos directamente
            return request.data

    def create(self, request, *args, **kwargs):
        """
        Crear tercero con formulario de vinculación completo
        Maneja tanto JSON como FormData con archivos
        """
        # Extraer datos del request (puede ser JSON o FormData)
        form_data = self.extract_form_data(request)
        
        logger.info(f"Datos recibidos en create: {form_data}")
        
        # Usar el serializer de vinculación si viene con datos completos
        if form_data.get('tipo_formulario') == 'vinculacion':
            serializer = TerceroVinculacionSerializer(data=form_data)
        else:
            serializer = self.get_serializer(data=form_data)
        
        serializer.is_valid(raise_exception=True)
        
        # Crear el Tercero usando perform_create para manejar asignación de comerciales
        self.perform_create(serializer)
        tercero = serializer.instance
        
        # ===== PROCESAR INFORMACIÓN PEP CRÍTICA (SARLAFT) =====
        # Obtener información PEP tanto del formato frontend (informacionPEP) como backend (informacion_pep)
        logger.info(f"🔍 DEBUG PEP - serializer.validated_data tiene informacion_pep: {'informacion_pep' in serializer.validated_data}")
        logger.info(f"🔍 DEBUG PEP - serializer.validated_data tiene informacionPEP: {'informacionPEP' in serializer.validated_data}")
        logger.info(f"🔍 DEBUG PEP - request.data tiene informacion_pep: {'informacion_pep' in request.data}")
        logger.info(f"🔍 DEBUG PEP - request.data tiene informacionPEP: {'informacionPEP' in request.data}")
        
        informacion_pep_data = (
            serializer.validated_data.get('informacion_pep', []) or 
            serializer.validated_data.get('informacionPEP', []) or
            request.data.get('informacionPEP', []) or
            request.data.get('informacion_pep', [])  # ✅ AGREGAR ESTE CASO FALTANTE
        )
        
        logger.info(f"🔍 DEBUG PEP - informacion_pep_data inicial: {informacion_pep_data}")
        logger.info(f"🔍 DEBUG PEP - tipo de informacion_pep_data: {type(informacion_pep_data)}")
        
        # 🔍 Si viene como string JSON, parsearlo
        if isinstance(informacion_pep_data, str):
            try:
                import json
                informacion_pep_data = json.loads(informacion_pep_data)
                logger.info(f"🔄 PEP parseado desde JSON string: {len(informacion_pep_data)} registros")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando JSON de información PEP: {e}")
                informacion_pep_data = []
        
        # Asegurar que sea una lista
        if not isinstance(informacion_pep_data, list):
            informacion_pep_data = []
            
        logger.info(f"🔍 DEBUG PEP - informacion_pep_data final: {len(informacion_pep_data)} registros")
        
        if informacion_pep_data:
            logger.info(f"Procesando {len(informacion_pep_data)} registros PEP para tercero {tercero.id}")
            
            # Validar que si es PEP, tenga al menos 1 registro
            if tercero.persona_expuesta_politica and not informacion_pep_data:
                return Response({
                    'error': 'Si es persona expuesta políticamente, debe proporcionar al menos 1 registro en informacionPEP[]'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Crear registros PEP
            pep_registros_creados = []
            for pep_data in informacion_pep_data:
                try:
                    # Validar campos obligatorios del formulario PEP
                    campos_requeridos = ['nombre', 'tipo', 'numero_identificacion', 'cargo', 'parentesco']
                    if not all(key in pep_data for key in campos_requeridos):
                        return Response({
                            'error': f'Cada registro PEP debe tener: {", ".join(campos_requeridos)}'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Procesar fechas si vienen como strings
                    fecha_vinculacion = pep_data.get('fecha_vinculacion')
                    fecha_retiro = pep_data.get('fecha_retiro')
                    
                    # Convertir fechas de string a date si es necesario
                    if fecha_vinculacion and isinstance(fecha_vinculacion, str):
                        try:
                            from datetime import datetime
                            fecha_vinculacion = datetime.strptime(fecha_vinculacion, '%Y-%m-%d').date() if fecha_vinculacion else None
                        except ValueError:
                            try:
                                fecha_vinculacion = datetime.strptime(fecha_vinculacion, '%d/%m/%Y').date()
                            except ValueError:
                                fecha_vinculacion = None
                                
                    if fecha_retiro and isinstance(fecha_retiro, str):
                        try:
                            from datetime import datetime
                            fecha_retiro = datetime.strptime(fecha_retiro, '%Y-%m-%d').date() if fecha_retiro else None
                        except ValueError:
                            try:
                                fecha_retiro = datetime.strptime(fecha_retiro, '%d/%m/%Y').date()
                            except ValueError:
                                fecha_retiro = None

                    # Crear registro PEP con todos los campos del formulario
                    pep_registro = InformacionPEP.objects.create(
                        tercero=tercero,
                        nombre=pep_data['nombre'],
                        tipo=pep_data['tipo'],
                        numero_identificacion=pep_data['numero_identificacion'],
                        # Nuevos campos del formulario público
                        cargo=pep_data.get('cargo', 'No especificado'),
                        parentesco=pep_data.get('parentesco', 'No especificado'),
                        fecha_vinculacion=fecha_vinculacion,
                        fecha_retiro=fecha_retiro,
                        cuentas_financieras_exterior=pep_data.get('cuentas_financieras_exterior', False),
                        # Campos legacy (mantener compatibilidad)
                        patrimonio_fiducia=pep_data.get('patrimonio_fiducia', False),
                        relaciones_comerciales=pep_data.get('relaciones_comerciales', False)
                    )
                    pep_registros_creados.append(pep_registro)
                    logger.info(f"Registro PEP creado: {pep_registro.nombre} ({pep_registro.tipo})")
                    
                except Exception as e:
                    logger.error(f"Error creando registro PEP: {str(e)}")
                    return Response({
                        'error': f'Error procesando información PEP: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"✅ {len(pep_registros_creados)} registros PEP creados exitosamente para tercero {tercero.id}")
        
        # ===== PROCESAR REPRESENTANTES LEGALES =====
        logger.info(f"🔍 DEBUG REPS - form_data keys: {list(form_data.keys())}")
        logger.info(f"🔍 DEBUG REPS - form_data representantes: {form_data.get('representantes', 'NO_ENCONTRADO')}")
        
        representantes_data = form_data.get('representantes', [])
        logger.info(f"🔍 DEBUG REPS - representantes_data: {representantes_data}")
        logger.info(f"🔍 DEBUG REPS - tipo representantes_data: {type(representantes_data)}")
        logger.info(f"🔍 DEBUG REPS - longitud representantes_data: {len(representantes_data) if representantes_data else 0}")
        
        # Si es string, intentar parsear manualmente
        if isinstance(representantes_data, str):
            logger.warning(f"⚠️ Representantes llegó como string, parseando: {representantes_data[:100]}...")
            try:
                representantes_data = json.loads(representantes_data)
                logger.info(f"✅ Representantes parseados correctamente: {len(representantes_data)} items")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando representantes JSON: {e}")
                representantes_data = []
        
        if representantes_data:
            logger.info(f"Procesando {len(representantes_data)} representantes para tercero {tercero.id}")
            
            for rep_data in representantes_data:
                try:
                    # Validar campos obligatorios
                    campos_requeridos = ['nombreCompleto', 'tipoIdentificacion', 'numeroIdentificacion', 'direccion', 'telefono']
                    if not all(key in rep_data for key in campos_requeridos):
                        return Response({
                            'error': f'Cada representante debe tener: {", ".join(campos_requeridos)}'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Crear representante legal
                    RepresentanteLegal.objects.create(
                        tercero=tercero,
                        nombre_completo=rep_data['nombreCompleto'],
                        tipo_identificacion=rep_data['tipoIdentificacion'],
                        numero_identificacion=rep_data['numeroIdentificacion'],
                        direccion=rep_data['direccion'],
                        telefono=rep_data['telefono']
                    )
                    logger.info(f"Representante creado: {rep_data['nombreCompleto']}")
                    
                except Exception as e:
                    logger.error(f"Error creando representante: {str(e)}")
                    return Response({
                        'error': f'Error procesando representantes: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # ===== PROCESAR ACCIONISTAS =====
        accionistas_data = form_data.get('accionistas', [])
        logger.info(f"🔍 DEBUG ACCIONISTAS - accionistas_data: {accionistas_data}")
        logger.info(f"🔍 DEBUG ACCIONISTAS - tipo accionistas_data: {type(accionistas_data)}")
        logger.info(f"🔍 DEBUG ACCIONISTAS - longitud accionistas_data: {len(accionistas_data) if accionistas_data else 0}")
        
        # Si es string, intentar parsear manualmente
        if isinstance(accionistas_data, str):
            logger.warning(f"⚠️ Accionistas llegó como string, parseando: {accionistas_data[:100]}...")
            try:
                accionistas_data = json.loads(accionistas_data)
                logger.info(f"✅ Accionistas parseados correctamente: {len(accionistas_data)} items")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando accionistas JSON: {e}")
                accionistas_data = []
        
        if accionistas_data:
            logger.info(f"Procesando {len(accionistas_data)} accionistas para tercero {tercero.id}")
            
            # Validar que la suma de porcentajes no exceda 100%
            total_porcentaje = sum(float(ac.get('porcentajeParticipacion', 0)) for ac in accionistas_data)
            if total_porcentaje > 100:
                return Response({
                    'error': f'La suma de porcentajes de participación ({total_porcentaje}%) no puede exceder 100%'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            for acc_data in accionistas_data:
                try:
                    # Validar campos obligatorios
                    campos_requeridos = ['nombre', 'tipoIdentificacion', 'numeroIdentificacion', 'porcentajeParticipacion']
                    if not all(key in acc_data for key in campos_requeridos):
                        return Response({
                            'error': f'Cada accionista debe tener: {", ".join(campos_requeridos)}'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Crear accionista
                    Accionista.objects.create(
                        tercero=tercero,
                        nombre=acc_data['nombre'],
                        tipo_identificacion=acc_data['tipoIdentificacion'],
                        numero_identificacion=acc_data['numeroIdentificacion'],
                        porcentaje_participacion=float(acc_data['porcentajeParticipacion'])
                    )
                    logger.info(f"Accionista creado: {acc_data['nombre']} ({acc_data['porcentajeParticipacion']}%)")
                    
                except Exception as e:
                    logger.error(f"Error creando accionista: {str(e)}")
                    return Response({
                        'error': f'Error procesando accionistas: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # ===== FIN PROCESAMIENTO REPRESENTANTES Y ACCIONISTAS =====
        
        # ===== FIN PROCESAMIENTO PEP =====
        
        # Manejar la subida de documentos si existen
        # Los documentos pueden venir como lista 'documentos' o como archivos individuales
        documentos = request.FILES.getlist('documentos')
        
        # También buscar documentos individuales (documento-identidad, rut, certificacion-bancaria, etc.)
        documentos_individuales = []
        claves_documentos = {}  # Mapear archivo a su clave FormData
        for key, file in request.FILES.items():
            if key != 'documentos':  # Evitar duplicar si también viene en la lista 'documentos'
                documentos_individuales.append(file)
                claves_documentos[file] = key  # Guardar la clave para cada archivo
                logger.info(f"Documento individual encontrado: {key} -> {file.name}")
        
        # Combinar ambas listas
        todos_documentos = documentos + documentos_individuales
        logger.info(f"Documentos recibidos: {len(todos_documentos)} (lista: {len(documentos)}, individuales: {len(documentos_individuales)})")
        
        if todos_documentos:
            tipo_persona = tercero.tipo_persona
            
            for archivo in todos_documentos:
                # Validar tamaño (máx. 5MB)
                if archivo.size > 5 * 1024 * 1024:
                    return Response({
                        'error': f'El archivo {archivo.name} excede el tamaño máximo de 5MB'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validar formato
                extension = archivo.name.split('.')[-1].lower()
                if extension not in ['pdf', 'png', 'jpg', 'jpeg']:
                    return Response({
                        'error': f'Formato no válido para {archivo.name}. Solo se permiten PDF, PNG, JPG'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Obtener la clave del FormData para este archivo (si existe)
                clave_formdata = claves_documentos.get(archivo, None)
                tipo_documento = determinar_tipo_documento_vinculacion(archivo, tipo_persona, clave_formdata)
                
                logger.info(f"Procesando: {archivo.name} -> clave: {clave_formdata} -> tipo: {tipo_documento}")
                
                # Guardar documento
                DocumentoTercero.objects.create(
                    tercero=tercero,
                    tipo_documento=tipo_documento,
                    archivo=archivo,
                    nombre_original=archivo.name,
                    tamano_archivo=archivo.size
                )
        
        # Respuesta personalizada
        if request.user.is_authenticated:
            response_serializer = TerceroVinculacionSerializer(tercero)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': True,
                'message': '¡Vinculación registrada exitosamente!',
                'data': {
                    'id': str(tercero.id),
                    'numero_documento': tercero.numero_documento,
                    'nombre_completo': f"{tercero.nombres} {tercero.apellidos}" if tercero.tipo_persona == 'natural' else tercero.razon_social,
                    'email': tercero.email,
                    'estado': tercero.estado_aprobacion,
                    'fecha_registro': tercero.created_at.isoformat()
                },
                'next_steps': {
                    'message': 'Su solicitud de vinculación ha sido registrada exitosamente y está en proceso de revisión.',
                    'timeline': 'Recibirá una notificación por email en los próximos 3-5 días hábiles.',
                    'documentos_recibidos': len(todos_documentos),
                    'contact': 'Si tiene preguntas, puede contactarnos a través de nuestros canales oficiales.'
                }
            }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def con_documentos(self, request, pk=None):
        """
        Obtener tercero con información completa de documentos
        GET /api/terceros/{id}/con_documentos/
        """
        tercero = self.get_object()
        serializer = TerceroConDocumentosSerializer(tercero)

        logger.info(f"Getting tercero with documents: {tercero.numero_documento} by {request.user.username}")

        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], permission_classes=[AllowAny])
    def documentos(self, request, pk=None):
        """
        Subir documentos para un tercero específico (acceso público para registro)
        POST /api/terceros/{id}/documentos/
        """
        tercero = self.get_object()
        
        logger.info(f"Uploading documents for tercero: {tercero.numero_documento}")
        logger.info(f"Files received: {list(request.FILES.keys())}")
        
        documentos_creados = []
        errores = []
        
        # Procesar cada archivo enviado
        for field_name, archivo in request.FILES.items():
            try:
                # Mapear el nombre del campo al tipo de documento
                tipo_documento = field_name.replace('-', '_')
                
                # Crear el documento
                documento = DocumentoTercero.objects.create(
                    tercero=tercero,
                    tipo_documento=tipo_documento,
                    archivo=archivo,
                    nombre_original=archivo.name
                )
                
                documentos_creados.append({
                    'id': documento.id,
                    'tipo': tipo_documento,
                    'nombre': archivo.name,
                    'url': documento.archivo.url if documento.archivo else None
                })
                
                logger.info(f"Document created: {tipo_documento} for tercero {tercero.numero_documento}")
                
            except Exception as e:
                error_msg = f"Error procesando {field_name}: {str(e)}"
                errores.append(error_msg)
                logger.error(error_msg)
        
        if errores:
            return Response({
                'success': False,
                'message': 'Algunos documentos no pudieron ser procesados',
                'documentos_creados': documentos_creados,
                'errores': errores
            }, status=status.HTTP_207_MULTI_STATUS)
        
        return Response({
            'success': True,
            'message': f'{len(documentos_creados)} documentos subidos exitosamente',
            'documentos': documentos_creados
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Endpoint para estadísticas de terceros
        GET /api/terceros/stats/
        """
        logger.info(f"Getting terceros stats for user: {request.user.username}")

        # Obtener el filtro base (usar el mismo filtro que get_queryset)
        queryset = Tercero.objects.all()
        
        # Aplicar filtro por comercial asignado si está presente
        assigned_to = request.query_params.get('assigned_to') or request.query_params.get('comercial_asignado')
        if assigned_to:
            queryset = queryset.filter(asignado_a_id=assigned_to)

        # Contar por estado
        total_terceros = queryset.count()
        pendientes = queryset.filter(estado_aprobacion='pendiente').count()
        en_revision = queryset.filter(estado_aprobacion='en_revision').count()
        aprobados = queryset.filter(estado_aprobacion='aprobado').count()
        rechazados = queryset.filter(estado_aprobacion='rechazado').count()
        requiere_ajustes = queryset.filter(estado_aprobacion='requiere_ajustes').count()

        # Estadísticas por tipo
        por_tipo_persona = dict(
            queryset.values('tipo_persona').annotate(count=Count('id')).values_list('tipo_persona', 'count')
        )

        por_tipo_documento = dict(
            queryset.values('tipo_documento').annotate(count=Count('id')).values_list('tipo_documento', 'count')
        )

        # Estadísticas del mes actual
        inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        creados_este_mes = queryset.filter(created_at__gte=inicio_mes).count()
        aprobados_este_mes = queryset.filter(
            updated_at__gte=inicio_mes,
            estado_aprobacion='aprobado'
        ).count()

        stats_data = {
            'total_terceros': total_terceros,
            'pendientes_aprobacion': pendientes,
            'en_revision': en_revision,
            'aprobados': aprobados,
            'rechazados': rechazados,
            'requiere_ajustes': requiere_ajustes,
            'por_tipo_persona': por_tipo_persona,
            'por_tipo_documento': por_tipo_documento,
            'creados_este_mes': creados_este_mes,
            'aprobados_este_mes': aprobados_este_mes,
        }

        serializer = TerceroStatsSerializer(stats_data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        """
        Aprobar un tercero
        POST /api/terceros/{id}/aprobar/
        
        Permisos:
        - Administrador: ✅ Acceso total
        - Oficial de cumplimiento: ✅ Acceso total  
        - Procesos: ✅ Puede aprobar terceros (NUEVO)
        - Comercial: ❌ No puede aprobar directamente (usar aprobar_comercial)
        """
        tercero = self.get_object()

        if tercero.estado_aprobacion == 'aprobado':
            return Response(
                {'error': 'El tercero ya está aprobado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener comentarios/observaciones opcionales
        observaciones = (
            request.data.get('observaciones', '') or 
            request.data.get('comentario', '') or 
            request.data.get('comment', '')
        ).strip()

        tercero.estado_aprobacion = 'aprobado'
        tercero.aprobado_por = request.user
        tercero.fecha_aprobacion = timezone.now()
        
        # Si hay observaciones, agregarlas con formato estructurado
        if observaciones:
            user_role = getattr(request.user, 'role', 'usuario').upper()
            username = request.user.get_full_name() or request.user.username
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Formato: [ROLE - User - Timestamp]: Comment
            comment_formatted = f"[{user_role} - {username} - {timestamp}]: {observaciones}"
            
            # Agregar al campo de observaciones existente
            if tercero.observaciones:
                tercero.observaciones += f"\n{comment_formatted}"
            else:
                tercero.observaciones = comment_formatted
        
        tercero.save()

        logger.info(f"Tercero {tercero.id} aprobado por usuario: {request.user.username} (rol: {getattr(request.user, 'role', 'N/A')})" + (f" - Comentario: {observaciones}" if observaciones else ""))

        serializer = self.get_serializer(tercero)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        """
        Rechazar un tercero
        POST /api/terceros/{id}/rechazar/
        
        Permisos:
        - Administrador: ✅ Acceso total
        - Oficial de cumplimiento: ✅ Acceso total
        - Procesos: ✅ Puede rechazar terceros (NUEVO)
        - Comercial: ❌ No puede rechazar directamente
        
        Body requerido:
        {
            "observaciones": "Motivo del rechazo (obligatorio)"
        }
        """
        tercero = self.get_object()
        # Aceptar observaciones de múltiples campos para flexibilidad
        observaciones = (
            request.data.get('observaciones', '') or 
            request.data.get('comentario', '') or 
            request.data.get('comment', '')
        ).strip()

        # Validar que hay observaciones o comentarios para el rechazo
        if not observaciones:
            return Response(
                {'error': 'Las observaciones son obligatorias para rechazar'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cambiar estado a rechazado
        tercero.estado_aprobacion = 'rechazado'
        tercero.fecha_aprobacion = timezone.now()  # Fecha de decisión
        
        # Agregar comentario con formato estructurado
        user_role = getattr(request.user, 'role', 'usuario').upper()
        username = request.user.get_full_name() or request.user.username
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Formato: [ROLE - User - Timestamp]: Comment
        comment_formatted = f"[{user_role} - {username} - {timestamp}]: {observaciones}"
        
        # Agregar al campo de observaciones existente
        if tercero.observaciones:
            tercero.observaciones += f"\n{comment_formatted}"
        else:
            tercero.observaciones = comment_formatted
            
        tercero.save()

        logger.info(f"Tercero {tercero.id} rechazado por usuario: {request.user.username} (rol: {getattr(request.user, 'role', 'N/A')}) - Comentario: {observaciones}")

        serializer = self.get_serializer(tercero)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """
        Cambiar estado de un tercero según workflow completo
        POST /api/terceros/{id}/cambiar_estado/
        Body: {
            "nuevo_estado": "aprobado_comercial|rechazado_comercial|...",
            "observaciones": "Comentarios opcionales",
            "asignar_a": "user_id_opcional"
        }
        """
        tercero = self.get_object()
        # Aceptar tanto 'nuevo_estado' como 'estado' para compatibilidad con frontend
        nuevo_estado = request.data.get('nuevo_estado') or request.data.get('estado')
        observaciones = request.data.get('observaciones', '')
        asignar_a_id = request.data.get('asignar_a')

        # Mapeo de estados del frontend al backend para compatibilidad
        estado_mapping = {
            # Mapeo del nuevo flujo
            'pendiente': 'pendiente',
            'en_espera_correccion': 'en_espera_correccion',
            'en_curso_comercial': 'en_curso_comercial', 
            'en_curso_administrador': 'en_curso_administrador',
            'en_curso_procesos': 'en_curso_procesos',
            'en_curso_cumplimiento': 'en_curso_cumplimiento',
            'asignada_administrador': 'asignada_administrador',
            'asignada_procesos': 'asignada_procesos', 
            'asignada_oficial_cumplimiento': 'asignada_oficial_cumplimiento',
            'devuelto_comercial': 'devuelto_comercial',
            'aprobado': 'aprobado',
            'rechazado': 'rechazado',
            'finalizado': 'finalizado',
            
            # Mapeo legacy para compatibilidad
            'asignada_a_administrador': 'asignado_administrador',
            'asignada_a_comercial': 'asignado_comercial',
            'asignada_a_procesos': 'asignado_procesos',
        }
        
        # Aplicar mapeo si existe
        nuevo_estado = estado_mapping.get(nuevo_estado, nuevo_estado)

        # Validar que el estado sea válido
        estados_validos = [choice[0] for choice in tercero.EstadoAprobacion.choices]
        if nuevo_estado not in estados_validos:
            return Response(
                {'error': f'Estado inválido. Estados válidos: {estados_validos}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar si es una reasignación dentro del mismo tipo de estado
        es_reasignacion_valida = False
        if asignar_a_id:
            # Permitir reasignación a administrador desde comercial
            if (nuevo_estado in ['asignada_administrador', 'en_curso_administrador'] and 
                tercero.estado_aprobacion in ['en_curso_comercial', 'asignado_comercial'] and
                User.objects.filter(id=asignar_a_id, role='administrador', is_active=True).exists()):
                es_reasignacion_valida = True
            
            # Permitir reasignación entre comerciales 
            elif (nuevo_estado in ['en_curso_comercial', 'asignado_comercial'] and 
                  tercero.estado_aprobacion in ['en_curso_comercial', 'asignado_comercial'] and
                  User.objects.filter(id=asignar_a_id, role='comercial', is_active=True).exists()):
                es_reasignacion_valida = True
            
            # Permitir reasignación entre procesos
            elif (nuevo_estado in ['en_curso_procesos', 'asignada_procesos'] and 
                  tercero.estado_aprobacion in ['en_curso_procesos', 'asignada_procesos'] and
                  User.objects.filter(id=asignar_a_id, role='procesos', is_active=True).exists()):
                es_reasignacion_valida = True

        # Validar transición usando el método del modelo (solo si no es reasignación válida)
        if not es_reasignacion_valida and not tercero.puede_cambiar_a_estado(nuevo_estado, request.user):
            transiciones_permitidas = tercero.obtener_transiciones_permitidas(request.user)
            return Response(
                {
                    'error': f'Transición no permitida de {tercero.estado_aprobacion} a {nuevo_estado}',
                    'transiciones_permitidas': list(transiciones_permitidas.keys()),
                    'rol_usuario': getattr(request.user, 'role', 'sin_rol')
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validaciones específicas
        if 'rechazado' in nuevo_estado and not observaciones:
            return Response(
                {'error': 'Las observaciones son obligatorias para rechazar'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Guardar estado anterior
        estado_anterior = tercero.estado_aprobacion

        # Actualizar tercero
        tercero.estado_aprobacion = nuevo_estado
        tercero.usuario_ultimo_cambio = request.user
        tercero.fecha_ultimo_cambio_estado = timezone.now()

        # Manejar observaciones por departamento
        if request.user.role == 'procesos':
            tercero.observaciones_procesos = observaciones
        elif request.user.role == 'oficial_cumplimiento':
            tercero.observaciones_cumplimiento = observaciones
        else:
            tercero.observaciones = observaciones

        # Lógica de asignaciones según el nuevo y legacy estado
        self._manejar_asignacion_por_estado(tercero, nuevo_estado, asignar_a_id)

        tercero.save()

        # Enviar notificaciones por email según el workflow
        self._enviar_notificacion_cambio_estado(tercero, estado_anterior, nuevo_estado, observaciones)

        return Response({
            'mensaje': 'Estado cambiado exitosamente',
            'tercero_id': str(tercero.id),
            'estado_anterior': estado_anterior,
            'estado_nuevo': nuevo_estado,
            'usuario_asignado': tercero.usuario_asignado.get_full_name() if tercero.usuario_asignado else None,
            'rol_asignado': tercero.rol_asignado
        }, status=status.HTTP_200_OK)
    
    def _manejar_asignacion_por_estado(self, tercero, nuevo_estado, asignar_a_id):
        """Maneja las asignaciones según el estado (nuevo flujo y legacy)"""
        
        # Mapeo de estados a roles y campos
        estado_config = {
            # Nuevos estados
            'en_curso_comercial': {'rol': 'comercial', 'campo_legacy': 'asignado_a'},
            'asignada_administrador': {'rol': 'administrador', 'campo_legacy': 'asignado_administrador'},
            'en_curso_administrador': {'rol': 'administrador', 'campo_legacy': 'asignado_administrador'},
            'asignada_procesos': {'rol': 'procesos', 'campo_legacy': 'asignado_a_procesos'},
            'en_curso_procesos': {'rol': 'procesos', 'campo_legacy': 'asignado_a_procesos'},
            'asignada_oficial_cumplimiento': {'rol': 'oficial_cumplimiento', 'campo_legacy': 'asignado_cumplimiento'},
            'en_curso_cumplimiento': {'rol': 'oficial_cumplimiento', 'campo_legacy': 'asignado_cumplimiento'},
            'devuelto_comercial': {'rol': 'comercial', 'campo_legacy': 'asignado_a'},
            
            # Estados legacy
            'asignado_comercial': {'rol': 'comercial', 'campo_legacy': 'asignado_a'},
            'asignado_administrador': {'rol': 'administrador', 'campo_legacy': 'asignado_administrador'},
            'asignado_procesos': {'rol': 'procesos', 'campo_legacy': 'asignado_a_procesos'},
            'enviado_cumplimiento': {'rol': 'oficial_cumplimiento', 'campo_legacy': 'asignado_cumplimiento'},
        }
        
        config = estado_config.get(nuevo_estado)
        if not config:
            # Estados que no requieren asignación (aprobado, rechazado, etc.)
            tercero.usuario_asignado = None
            tercero.rol_asignado = None
            tercero.fecha_asignacion_actual = None
            return
        
        rol_requerido = config['rol']
        campo_legacy = config['campo_legacy']
        
        # Buscar usuario a asignar
        usuario_asignar = None
        
        if asignar_a_id:
            # Usuario específico proporcionado
            try:
                usuario_asignar = User.objects.get(
                    id=asignar_a_id, 
                    role=rol_requerido, 
                    is_active=True
                )
            except User.DoesNotExist:
                # Si no se encuentra el usuario específico, buscar automáticamente
                pass
        
        if not usuario_asignar:
            # Asignación automática
            if rol_requerido == 'comercial':
                usuario_asignar = self._obtener_comercial_con_menos_carga()
            elif rol_requerido == 'administrador':
                usuario_asignar = User.objects.filter(role='administrador', is_active=True).first()
            elif rol_requerido == 'procesos':
                from terceros.models import asignar_procesos_automaticamente
                usuario_asignar = asignar_procesos_automaticamente()
            elif rol_requerido == 'oficial_cumplimiento':
                usuario_asignar = User.objects.filter(role='oficial_cumplimiento', is_active=True).first()
        
        if usuario_asignar:
            # Actualizar campos centralizados
            tercero.usuario_asignado = usuario_asignar
            tercero.rol_asignado = rol_requerido
            tercero.fecha_asignacion_actual = timezone.now()
            
            # Actualizar campos legacy para compatibilidad
            setattr(tercero, campo_legacy, usuario_asignar)
            
            # Actualizar fecha específica del campo legacy
            fecha_campo = f'fecha_asignacion_{rol_requerido}' if rol_requerido != 'oficial_cumplimiento' else 'fecha_asignacion_cumplimiento'
            if hasattr(tercero, fecha_campo):
                setattr(tercero, fecha_campo, timezone.now())
        else:
            raise ValueError(f'No hay usuarios {rol_requerido} disponibles para asignación')
    
    def _obtener_comercial_con_menos_carga(self):
        """Obtiene el comercial con menos terceros asignados"""
        from django.db.models import Count
        return User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            num_terceros=Count('terceros_asignados_comercial')
        ).order_by('num_terceros').first()

    def _enviar_notificacion_cambio_estado(self, tercero, estado_anterior, estado_nuevo, observaciones):
        """Enviar notificaciones automáticas según el workflow"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            # Rechazo por comercial -> Email al usuario original
            if estado_nuevo == 'rechazado_comercial':
                if tercero.created_by and tercero.created_by.email:
                    send_mail(
                        subject=f'Solicitud de Registro de Tercero - Requiere Ajustes: {tercero.nombre_completo}',
                        message=f'''
Estimado/a {tercero.created_by.get_full_name()},

Su solicitud de registro del tercero "{tercero.nombre_completo}" ha sido revisada por nuestro equipo comercial y requiere algunos ajustes.

Observaciones del comercial:
{observaciones}

Por favor, revise la información y realice las correcciones necesarias.

Saludos cordiales,
Equipo Comercial
                        ''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[tercero.created_by.email],
                        fail_silently=True
                    )

            # Rechazo por procesos -> Email al comercial asignado
            elif estado_nuevo == 'rechazado_procesos':
                if tercero.asignado_a and tercero.asignado_a.email:
                    send_mail(
                        subject=f'Tercero Devuelto por Procesos - {tercero.nombre_completo}',
                        message=f'''
Estimado/a {tercero.asignado_a.get_full_name()},

El tercero "{tercero.nombre_completo}" ha sido revisado por el equipo de procesos y ha sido devuelto para revisión.

Observaciones de procesos:
{observaciones}

Por favor, revise con el cliente y realice las correcciones necesarias.

Saludos cordiales,
Equipo de Procesos
                        ''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[tercero.asignado_a.email],
                        fail_silently=True
                    )

            # NUEVO: Comercial aprueba → Notificar al administrador asignado
            elif estado_nuevo == 'asignado_administrador':
                if tercero.asignado_administrador and tercero.asignado_administrador.email:
                    comercial_nombre = tercero.asignado_a.get_full_name() if tercero.asignado_a else 'No asignado'
                    send_mail(
                        subject=f'🔄 Nuevo Tercero Aprobado por Comercial - {tercero.nombre_completo}',
                        message=f'''
Estimado/a Administrador {tercero.asignado_administrador.get_full_name()},

El tercero "{tercero.nombre_completo}" ha sido APROBADO por el área comercial y requiere su gestión administrativa.

📋 DETALLES DEL TERCERO:
• Nombre: {tercero.nombre_completo}
• Documento: {tercero.numero_documento}
• Email: {tercero.email}
• Teléfono: {tercero.telefono}
• Comercial responsable: {comercial_nombre}

✅ PRÓXIMOS PASOS:
Como administrador, puede:
1. Asignar a Procesos para revisión detallada
2. Enviar directamente a Cumplimiento
3. Aprobar final para envío a Contabilidad
4. Realizar cualquier otro cambio necesario

📝 OBSERVACIONES DEL COMERCIAL:
{observaciones if observaciones else 'Sin observaciones adicionales'}

🔗 Acceda al sistema para gestionar este tercero.

Saludos cordiales,
Sistema de Gestión de Terceros - EURO
                        ''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[tercero.asignado_administrador.email],
                        fail_silently=True
                    )
                    logger.info(f"Notificación enviada al administrador {tercero.asignado_administrador.email}")

            # Aprobación final -> Email a contabilidad
            elif estado_nuevo == 'aprobado_final':
                # Obtener usuarios de contabilidad
                usuarios_contabilidad = User.objects.filter(role='contabilidad', is_active=True)
                emails_contabilidad = [u.email for u in usuarios_contabilidad if u.email]
                
                if emails_contabilidad:
                    send_mail(
                        subject=f'Nuevo Tercero Aprobado - {tercero.nombre_completo}',
                        message=f'''
Estimado equipo de Contabilidad,

El tercero "{tercero.nombre_completo}" ha completado exitosamente el proceso de aprobación y está listo para su gestión contable.

Detalles del tercero:
- Nombre: {tercero.nombre_completo}
- Tipo: {tercero.get_tipo_persona_display()}
- Documento: {tercero.numero_documento}
- Comercial asignado: {tercero.asignado_a.get_full_name() if tercero.asignado_a else 'No asignado'}

Puede acceder a la información completa en el sistema.

Saludos cordiales,
Sistema de Gestión de Terceros
                        ''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=emails_contabilidad,
                        fail_silently=True
                    )

        except Exception as e:
            logger.error(f"Error enviando notificación para tercero {tercero.id}: {str(e)}")

    def _notificar_rechazo_a_comercial(self, tercero, observaciones):
        """
        Notifica al comercial asignado cuando procesos rechaza un tercero
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            if tercero.asignado_a and tercero.asignado_a.email:
                send_mail(
                    subject=f'⚠️ Tercero Devuelto por Procesos - {tercero.nombre_completo}',
                    message=f'''
Estimado/a {tercero.asignado_a.get_full_name()},

El tercero "{tercero.nombre_completo}" ha sido revisado por el equipo de procesos y requiere correcciones antes de continuar.

📋 OBSERVACIONES DE PROCESOS:
{observaciones}

🔄 PRÓXIMOS PASOS:
1. Revisar las observaciones con el cliente
2. Realizar las correcciones necesarias
3. Actualizar la información en el sistema

📞 Para cualquier consulta, puede contactar al equipo de procesos.

Saludos cordiales,
Equipo de Procesos - EURO
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[tercero.asignado_a.email],
                    fail_silently=True
                )
                logger.info(f"Notificación de rechazo enviada al comercial {tercero.asignado_a.email}")
        except Exception as e:
            logger.error(f"Error enviando notificación de rechazo a comercial: {str(e)}")

    def _notificar_rechazo_comercial_a_tercero(self, tercero, observaciones):
        """
        Notifica al tercero cuando el comercial no acepta la solicitud
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            if tercero.email:
                send_mail(
                    subject=f'📋 Solicitud de Registro - Información Adicional Requerida',
                    message=f'''
Estimado/a {tercero.nombre_completo},

Gracias por su interés en registrarse como tercero en EURO.

Su solicitud ha sido revisada y necesitamos información adicional para continuar con el proceso:

📝 INFORMACIÓN REQUERIDA:
{observaciones}

🔄 PRÓXIMOS PASOS:
1. Proporcione la información adicional solicitada
2. Contacte a su comercial asignado para actualizar los datos
3. Su solicitud será revisada nuevamente

📞 CONTACTO:
Comercial asignado: {tercero.asignado_a.get_full_name() if tercero.asignado_a else 'Por asignar'}
Email: {tercero.asignado_a.email if tercero.asignado_a else 'Por asignar'}

Agradecemos su comprensión y colaboración.

Atentamente,
Equipo Comercial - EURO
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[tercero.email],
                    fail_silently=True
                )
                logger.info(f"Notificación de rechazo comercial enviada al tercero {tercero.email}")
        except Exception as e:
            logger.error(f"Error enviando notificación de rechazo comercial a tercero: {str(e)}")

    def _notificar_aprobacion_final_contabilidad(self, tercero):
        """
        Notifica a contabilidad cuando un tercero es aprobado final
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            # Obtener usuarios de contabilidad
            usuarios_contabilidad = User.objects.filter(role='contabilidad', is_active=True)
            emails_contabilidad = [u.email for u in usuarios_contabilidad if u.email]
            
            if emails_contabilidad:
                # Preparar información detallada del tercero
                tipo_persona = tercero.get_tipo_persona_display()
                comercial = tercero.asignado_a.get_full_name() if tercero.asignado_a else 'No asignado'
                
                send_mail(
                    subject=f'✅ Nuevo Tercero Aprobado - {tercero.nombre_completo}',
                    message=f'''
Estimado equipo de Contabilidad,

Se ha completado exitosamente el proceso de aprobación para el siguiente tercero:

👤 INFORMACIÓN DEL TERCERO:
• Nombre: {tercero.nombre_completo}
• Tipo: {tipo_persona}
• Documento: {tercero.numero_documento}
• Email: {tercero.email}
• Teléfono: {tercero.telefono}

👥 INFORMACIÓN DEL PROCESO:
• Comercial asignado: {comercial}
• Fecha de aprobación: {timezone.now().strftime('%d/%m/%Y %H:%M')}
• Aprobado por: Procesos

🔗 PRÓXIMOS PASOS:
1. Crear el tercero en el sistema contable
2. Asignar códigos de tercero correspondientes
3. Configurar condiciones comerciales según sea necesario

📱 Puede acceder a toda la información y documentos en el sistema de gestión de terceros.

Saludos cordiales,
Sistema de Gestión de Terceros - EURO
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=emails_contabilidad,
                    fail_silently=True
                )
                logger.info(f"Notificación de aprobación final enviada a contabilidad: {emails_contabilidad}")
            else:
                logger.warning("No se encontraron usuarios de contabilidad para notificar")
                
        except Exception as e:
            logger.error(f"Error enviando notificación de aprobación final a contabilidad: {str(e)}")

    def _notificar_cumplimiento_aprobacion_final(self, tercero):
        """
        Notifica a contabilidad cuando cumplimiento aprueba final un tercero
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            usuarios_contabilidad = User.objects.filter(role='contabilidad', is_active=True)
            emails_contabilidad = [u.email for u in usuarios_contabilidad if u.email]
            
            if emails_contabilidad:
                cumplimiento_usuario = tercero.asignado_cumplimiento.get_full_name() if tercero.asignado_cumplimiento else 'Oficial de Cumplimiento'
                
                send_mail(
                    subject=f'✅ Tercero Aprobado por Cumplimiento - {tercero.nombre_completo}',
                    message=f'''
Estimado equipo de Contabilidad,

El tercero "{tercero.nombre_completo}" ha sido aprobado por el área de cumplimiento y está listo para su gestión contable.

👤 INFORMACIÓN DEL TERCERO:
• Nombre: {tercero.nombre_completo}
• Documento: {tercero.numero_documento}
• Email: {tercero.email}
• Teléfono: {tercero.telefono}

✅ APROBACIONES COMPLETADAS:
• Comercial: ✓
• Procesos: ✓  
• Cumplimiento: ✓ ({cumplimiento_usuario})

🔗 El tercero está ahora disponible para:
1. Creación en sistema contable
2. Asignación de códigos
3. Configuración de condiciones comerciales

Saludos cordiales,
Equipo de Cumplimiento - EURO
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=emails_contabilidad,
                    fail_silently=True
                )
                logger.info(f"Notificación de aprobación por cumplimiento enviada a contabilidad")
                
        except Exception as e:
            logger.error(f"Error enviando notificación de cumplimiento a contabilidad: {str(e)}")

    @action(detail=False, methods=['get'])
    def transiciones_disponibles(self, request):
        """
        Obtener transiciones disponibles para el usuario actual
        GET /api/terceros/transiciones_disponibles/
        """
        # Crear un tercero temporal para obtener las transiciones
        tercero_temp = Tercero()
        transiciones = {}
        
        for estado in Tercero.EstadoAprobacion.choices:
            estado_codigo = estado[0]
            tercero_temp.estado_aprobacion = estado_codigo
            transiciones[estado_codigo] = tercero_temp.obtener_transiciones_permitidas(request.user)

        return Response({
            'transiciones_por_estado': transiciones,
            'rol_usuario': getattr(request.user, 'role', 'sin_rol')
        })

    @action(detail=True, methods=['post'])
    def procesos_aprobar(self, request, pk=None):
        """
        Endpoint específico para acciones de procesos
        POST /api/terceros/{id}/procesos_aprobar/
        Body: {
            "accion": "aprobar|rechazar|enviar_cumplimiento|enviar_contabilidad",
            "destinatario": "cumplimiento|contabilidad",  # opcional
            "observaciones": "comentarios"
        }
        """
        tercero = self.get_object()
        
        # Validar que el usuario tenga rol de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response(
                {'error': 'Solo usuarios con rol de procesos pueden ejecutar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        accion = request.data.get('accion')
        destinatario = request.data.get('destinatario')
        observaciones = request.data.get('observaciones', '')

        if accion not in ['aprobar', 'rechazar', 'enviar_cumplimiento', 'enviar_contabilidad']:
            return Response(
                {'error': 'Acción inválida. Opciones: aprobar, rechazar, enviar_cumplimiento, enviar_contabilidad'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mapear acciones a estados
        estado_mapping = {
            'aprobar': 'aprobado_procesos',
            'rechazar': 'rechazado_procesos',
            'enviar_cumplimiento': 'enviado_cumplimiento',
            'enviar_contabilidad': 'aprobado_final'
        }

        nuevo_estado = estado_mapping[accion]

        # Validar transición
        if not tercero.puede_cambiar_a_estado(nuevo_estado, request.user):
            return Response(
                {'error': f'No se puede cambiar a estado {nuevo_estado} desde {tercero.estado_aprobacion}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ejecutar cambio de estado
        estado_anterior = tercero.estado_aprobacion
        tercero.estado_aprobacion = nuevo_estado
        tercero.observaciones_procesos = observaciones
        tercero.usuario_ultimo_cambio = request.user
        tercero.fecha_ultimo_cambio_estado = timezone.now()

        # Asignar según destinatario si se especifica
        destinatario_email = None
        if destinatario == 'cumplimiento' and accion == 'enviar_cumplimiento':
            usuarios_cumplimiento = User.objects.filter(role='oficial_cumplimiento', is_active=True)
            if usuarios_cumplimiento.exists():
                tercero.asignado_cumplimiento = usuarios_cumplimiento.first()
                destinatario_email = usuarios_cumplimiento.first().email

        elif destinatario == 'contabilidad' and accion == 'enviar_contabilidad':
            usuarios_contabilidad = User.objects.filter(role='contabilidad', is_active=True)
            destinatario_email = usuarios_contabilidad.first().email if usuarios_contabilidad.exists() else None

        tercero.save()

        # Enviar notificación
        self._enviar_notificacion_cambio_estado(tercero, estado_anterior, nuevo_estado, observaciones)

        logger.info(f"Procesos - Tercero {tercero.id}: {accion} ejecutado por {request.user.username}")

        return Response({
            'success': True,
            'accion_ejecutada': accion,
            'estado_nuevo': nuevo_estado,
            'destinatario_email': destinatario_email,
            'tercero_id': str(tercero.id)
        })

    @action(detail=True, methods=['post'])
    def cumplimiento_revisar(self, request, pk=None):
        """
        Endpoint específico para acciones de cumplimiento
        POST /api/terceros/{id}/cumplimiento_revisar/
        Body: {
            "accion": "aprobar|rechazar",
            "enviar_a": "contabilidad|procesos",
            "observaciones": "comentarios"
        }
        """
        tercero = self.get_object()
        
        # Validar que el usuario tenga rol de cumplimiento
        if not hasattr(request.user, 'role') or request.user.role != 'oficial_cumplimiento':
            return Response(
                {'error': 'Solo usuarios con rol de oficial de cumplimiento pueden ejecutar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        accion = request.data.get('accion')
        enviar_a = request.data.get('enviar_a')
        observaciones = request.data.get('observaciones', '')

        if accion not in ['aprobar', 'rechazar']:
            return Response(
                {'error': 'Acción inválida. Opciones: aprobar, rechazar'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determinar nuevo estado
        if accion == 'aprobar':
            if enviar_a == 'contabilidad':
                nuevo_estado = 'aprobado_final'
            else:
                nuevo_estado = 'aprobado_cumplimiento'
        else:  # rechazar
            if enviar_a == 'procesos':
                nuevo_estado = 'rechazado_cumplimiento'
            else:
                nuevo_estado = 'rechazado_cumplimiento'

        # Validar transición
        if not tercero.puede_cambiar_a_estado(nuevo_estado, request.user):
            return Response(
                {'error': f'No se puede cambiar a estado {nuevo_estado} desde {tercero.estado_aprobacion}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ejecutar cambio
        estado_anterior = tercero.estado_aprobacion
        tercero.estado_aprobacion = nuevo_estado
        tercero.observaciones_cumplimiento = observaciones
        tercero.usuario_ultimo_cambio = request.user
        tercero.fecha_ultimo_cambio_estado = timezone.now()
        tercero.save()

        # Enviar notificación
        self._enviar_notificacion_cambio_estado(tercero, estado_anterior, nuevo_estado, observaciones)

        logger.info(f"Cumplimiento - Tercero {tercero.id}: {accion} ejecutado por {request.user.username}")

        return Response({
            'success': True,
            'accion_ejecutada': accion,
            'estado_nuevo': nuevo_estado,
            'enviado_a': enviar_a,
            'tercero_id': str(tercero.id)
        })

    @action(detail=True, methods=['post'])
    def comercial_decidir(self, request, pk=None):
        """
        Endpoint específico para que comercial tome decisiones sobre un tercero
        POST /api/terceros/{id}/comercial_decidir/
        
        Body: {
            "accion": "aprobar|rechazar",
            "observaciones": "comentarios opcionales"
        }
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de comercial
        if not hasattr(request.user, 'role') or request.user.role != 'comercial':
            return Response(
                {'error': 'Solo usuarios comerciales pueden usar este endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar que el tercero esté asignado al comercial actual
        if tercero.asignado_a != request.user:
            return Response(
                {'error': 'Este tercero no está asignado a usted'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar estado correcto
        if tercero.estado_aprobacion != 'asignado_comercial':
            return Response(
                {'error': 'El tercero no está en estado válido para decisión comercial'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        accion = request.data.get('accion')
        observaciones = request.data.get('observaciones', '')
        
        if accion == 'aprobar':
            nuevo_estado = 'aprobado_comercial'
        elif accion == 'rechazar':
            nuevo_estado = 'rechazado_comercial'
            # Al rechazar, enviar email al tercero
            self._notificar_rechazo_comercial_a_tercero(tercero, observaciones)
        else:
            return Response(
                {'error': 'Acción no válida. Use: aprobar o rechazar'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Realizar el cambio
        estado_anterior = tercero.estado_aprobacion
        tercero.estado_aprobacion = nuevo_estado
        tercero.observaciones = observaciones  # Observaciones generales del comercial
        tercero.usuario_ultimo_cambio = request.user
        tercero.fecha_ultimo_cambio_estado = timezone.now()
        tercero.save()
        
        logger.info(f"Comercial - Tercero {tercero.id}: {accion} ejecutado por {request.user.username}")
        
        return Response({
            'success': True,
            'message': f'Tercero {accion} por comercial exitosamente',
            'estado_anterior': estado_anterior,
            'estado_nuevo': nuevo_estado,
            'tercero_id': str(tercero.id)
        })

    @action(detail=True, methods=['post'])
    def cumplimiento_decidir(self, request, pk=None):
        """
        Endpoint específico para que cumplimiento tome decisiones sobre un tercero
        POST /api/terceros/{id}/cumplimiento_decidir/
        
        Body: {
            "accion": "aprobar_final|rechazar",
            "observaciones": "comentarios opcionales"
        }
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de cumplimiento
        if not hasattr(request.user, 'role') or request.user.role != 'oficial_cumplimiento':
            return Response(
                {'error': 'Solo usuarios de cumplimiento pueden usar este endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar estado correcto
        if tercero.estado_aprobacion != 'enviado_cumplimiento':
            return Response(
                {'error': 'El tercero no está en estado válido para decisión de cumplimiento'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        accion = request.data.get('accion')
        observaciones = request.data.get('observaciones', '')
        
        if accion == 'aprobar_final':
            nuevo_estado = 'aprobado_final'
            # Enviar email a contabilidad
            self._notificar_cumplimiento_aprobacion_final(tercero)
        elif accion == 'rechazar':
            nuevo_estado = 'rechazado_cumplimiento'
            # Al rechazar, vuelve a procesos
        else:
            return Response(
                {'error': 'Acción no válida. Use: aprobar_final o rechazar'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Realizar el cambio
        estado_anterior = tercero.estado_aprobacion
        tercero.estado_aprobacion = nuevo_estado
        tercero.observaciones_cumplimiento = observaciones
        tercero.usuario_ultimo_cambio = request.user
        tercero.fecha_ultimo_cambio_estado = timezone.now()
        tercero.save()
        
        logger.info(f"Cumplimiento - Tercero {tercero.id}: {accion} ejecutado por {request.user.username}")
        
        return Response({
            'success': True,
            'message': f'Tercero {accion} por cumplimiento exitosamente',
            'estado_anterior': estado_anterior,
            'estado_nuevo': nuevo_estado,
            'tercero_id': str(tercero.id)
        })

    @action(detail=True, methods=['post'])
    def administrador_gestionar(self, request, pk=None):
        """
        Endpoint específico para que administradores gestionen y asignen terceros
        POST /api/terceros/{id}/administrador_gestionar/
        
        Body: {
            "accion": "asignar_procesos|enviar_cumplimiento|aprobar_final|rechazar_final|regresar_comercial",
            "asignar_a": "user_id_opcional", // ID del usuario al que asignar
            "observaciones": "comentarios opcionales"
        }
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de administrador
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response(
                {'error': 'Solo usuarios administradores pueden usar este endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar estado correcto
        if tercero.estado_aprobacion != 'asignado_administrador':
            return Response(
                {'error': 'El tercero no está asignado al administrador'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        accion = request.data.get('accion')
        asignar_a_id = request.data.get('asignar_a')
        observaciones = request.data.get('observaciones', '')
        
        # Mapear acciones a estados
        estados_mapping = {
            'asignar_procesos': 'asignado_procesos',
            'enviar_cumplimiento': 'enviado_cumplimiento', 
            'aprobar_final': 'aprobado_final',
            'rechazar_final': 'rechazado_final',
            'regresar_comercial': 'asignado_comercial'
        }
        
        if accion not in estados_mapping:
            return Response(
                {'error': f'Acción inválida. Opciones: {list(estados_mapping.keys())}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        nuevo_estado = estados_mapping[accion]
        
        # Lógica de asignación según la acción
        usuario_asignado = None
        if accion == 'asignar_procesos':
            if asignar_a_id:
                try:
                    usuario_procesos = User.objects.get(id=asignar_a_id, role='procesos', is_active=True)
                    tercero.asignado_a_procesos = usuario_procesos
                    usuario_asignado = usuario_procesos
                except User.DoesNotExist:
                    return Response(
                        {'error': 'Usuario de procesos no encontrado o inactivo'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Asignar automáticamente al primer usuario de procesos disponible
                usuario_procesos = User.objects.filter(role='procesos', is_active=True).first()
                if usuario_procesos:
                    tercero.asignado_a_procesos = usuario_procesos
                    usuario_asignado = usuario_procesos
                else:
                    return Response(
                        {'error': 'No hay usuarios de procesos disponibles'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
        elif accion == 'enviar_cumplimiento':
            if asignar_a_id:
                try:
                    oficial_cumplimiento = User.objects.get(id=asignar_a_id, role='oficial_cumplimiento', is_active=True)
                    tercero.asignado_cumplimiento = oficial_cumplimiento
                    usuario_asignado = oficial_cumplimiento
                except User.DoesNotExist:
                    return Response(
                        {'error': 'Oficial de cumplimiento no encontrado o inactivo'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Asignar automáticamente al primer oficial de cumplimiento disponible
                oficial_cumplimiento = User.objects.filter(role='oficial_cumplimiento', is_active=True).first()
                if oficial_cumplimiento:
                    tercero.asignado_cumplimiento = oficial_cumplimiento
                    usuario_asignado = oficial_cumplimiento
                else:
                    return Response(
                        {'error': 'No hay oficiales de cumplimiento disponibles'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        elif accion == 'regresar_comercial':
            # Mantener el comercial original asignado
            if not tercero.asignado_a:
                return Response(
                    {'error': 'No hay comercial asignado al tercero para regresar'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Realizar el cambio
        estado_anterior = tercero.estado_aprobacion
        tercero.estado_aprobacion = nuevo_estado
        tercero.observaciones_administrador = observaciones
        tercero.usuario_ultimo_cambio = request.user
        tercero.fecha_ultimo_cambio_estado = timezone.now()
        tercero.save()
        
        # Enviar notificaciones específicas
        if accion == 'aprobar_final':
            self._notificar_aprobacion_final_contabilidad(tercero)
        
        logger.info(f"Administrador - Tercero {tercero.id}: {accion} ejecutado por {request.user.username}")
        
        return Response({
            'success': True,
            'message': f'Tercero gestionado por administrador: {accion}',
            'estado_anterior': estado_anterior,
            'estado_nuevo': nuevo_estado,
            'usuario_asignado': usuario_asignado.get_full_name() if usuario_asignado else None,
            'tercero_id': str(tercero.id)
        })

    @action(detail=False, methods=['get'])
    def usuarios_por_rol(self, request):
        """
        Obtener usuarios disponibles por rol para asignaciones
        GET /api/terceros/usuarios_por_rol/?rol=comercial|procesos|oficial_cumplimiento|contabilidad
        """
        rol_solicitado = request.query_params.get('rol')
        
        if not rol_solicitado:
            return Response({
                'error': 'Parámetro rol es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        roles_validos = ['comercial', 'procesos', 'oficial_cumplimiento', 'contabilidad', 'administrador']
        if rol_solicitado not in roles_validos:
            return Response({
                'error': f'Rol inválido. Roles válidos: {roles_validos}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Obtener usuarios del rol solicitado
        usuarios = User.objects.filter(
            role=rol_solicitado,
            is_active=True
        ).values('id', 'username', 'first_name', 'last_name', 'email')

        return Response({
            'rol': rol_solicitado,
            'usuarios': list(usuarios),
            'total': len(usuarios)
        })

    @action(detail=False, methods=['get'])
    def estadisticas_workflow(self, request):
        """
        Estadísticas del workflow de terceros
        GET /api/terceros/estadisticas_workflow/
        """
        from django.db.models import Count
        
        # Contar terceros por estado
        estadisticas_estados = Tercero.objects.values('estado_aprobacion').annotate(
            cantidad=Count('id')
        ).order_by('estado_aprobacion')

        # Terceros asignados por rol
        terceros_asignados = {
            'comercial': Tercero.objects.filter(asignado_a__isnull=False).count(),
            'procesos': Tercero.objects.filter(asignado_a_procesos__isnull=False).count(),
            'cumplimiento': Tercero.objects.filter(asignado_cumplimiento__isnull=False).count()
        }

        # Terceros pendientes de asignación
        pendientes_asignacion = {
            'sin_comercial': Tercero.objects.filter(
                estado_aprobacion='pendiente',
                asignado_a__isnull=True
            ).count(),
            'sin_procesos': Tercero.objects.filter(
                estado_aprobacion__in=['aprobado_comercial', 'asignado_procesos'],
                asignado_a_procesos__isnull=True
            ).count(),
            'sin_cumplimiento': Tercero.objects.filter(
                estado_aprobacion='enviado_cumplimiento',
                asignado_cumplimiento__isnull=True
            ).count()
        }

        return Response({
            'estadisticas_por_estado': list(estadisticas_estados),
            'terceros_asignados': terceros_asignados,
            'pendientes_asignacion': pendientes_asignacion,
            'total_terceros': Tercero.objects.count(),
            'fecha_consulta': timezone.now()
        })

    @action(detail=False, methods=['get'])
    def workflow_list(self, request):
        """
        Lista de terceros con información completa de workflow
        GET /api/terceros/workflow_list/?estado=pendiente&asignado_a=user_id
        """
        queryset = self.get_queryset()
        
        # Filtros específicos de workflow
        estado = request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado_aprobacion=estado)
        
        asignado_a = request.query_params.get('asignado_a')
        if asignado_a:
            queryset = queryset.filter(asignado_a_id=asignado_a)
        
        asignado_procesos = request.query_params.get('asignado_procesos')
        if asignado_procesos:
            queryset = queryset.filter(asignado_a_procesos_id=asignado_procesos)
        
        asignado_cumplimiento = request.query_params.get('asignado_cumplimiento')
        if asignado_cumplimiento:
            queryset = queryset.filter(asignado_cumplimiento_id=asignado_cumplimiento)
        
        # Solo terceros del usuario actual según su rol
        user_role = getattr(request.user, 'role', None)
        if user_role == 'comercial':
            queryset = queryset.filter(asignado_a=request.user)
        elif user_role == 'procesos':
            queryset = queryset.filter(asignado_a_procesos=request.user)
        elif user_role == 'oficial_cumplimiento':
            queryset = queryset.filter(asignado_cumplimiento=request.user)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TerceroWorkflowSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = TerceroWorkflowSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

        serializer = self.get_serializer(tercero)
        return Response({
            'tercero': serializer.data,
            'cambio': {
                'estado_anterior': estado_anterior,
                'estado_nuevo': nuevo_estado,
                'observaciones': observaciones,
                'usuario': request.user.username
            }
        })

    @action(detail=False, methods=['get'])
    def estados_disponibles(self, request):
        """
        Obtener todos los estados disponibles y transiciones permitidas
        GET /api/terceros/estados_disponibles/
        """
        estados = [
            {'value': choice[0], 'label': choice[1]}
            for choice in Tercero.EstadoAprobacion.choices
        ]

        transiciones = {
            'pendiente': ['en_revision', 'aprobado', 'rechazado'],
            'en_revision': ['aprobado', 'rechazado', 'requiere_ajustes'],
            'requiere_ajustes': ['en_revision', 'pendiente'],
            'aprobado': [],
            'rechazado': ['pendiente', 'en_revision']
        }

        return Response({
            'estados': estados,
            'transiciones_permitidas': transiciones
        })

    @action(detail=False, methods=['get'])
    def mis_terceros_asignados(self, request):
        """
        Obtener terceros asignados al comercial autenticado
        GET /api/terceros/mis_terceros_asignados/
        """
        if request.user.role != 'comercial':
            return Response(
                {'error': 'Solo los comerciales pueden acceder a sus terceros asignados'},
                status=status.HTTP_403_FORBIDDEN
            )

        terceros = Tercero.objects.filter(asignado_a=request.user).order_by('-created_at')
        serializer = TerceroListSerializer(terceros, many=True)
        
        # Estadísticas adicionales
        stats = {
            'total_asignados': terceros.count(),
            'pendientes': terceros.filter(estado_aprobacion='pendiente').count(),
            'en_revision': terceros.filter(estado_aprobacion='en_revision').count(),
            'aprobados': terceros.filter(estado_aprobacion='aprobado').count(),
            'rechazados': terceros.filter(estado_aprobacion='rechazado').count(),
        }

        return Response({
            'terceros': serializer.data,
            'estadisticas': stats
        })

    @action(detail=True, methods=['post'])
    def reasignar_comercial(self, request, pk=None):
        """
        Reasignar un tercero a otro comercial
        POST /api/terceros/{id}/reasignar_comercial/
        Body: {"nuevo_comercial_id": "uuid"}
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Solo procesos puede reasignar
        if request.user.role != 'procesos':
            return Response(
                {'error': 'Solo el área de procesos puede reasignar terceros'},
                status=status.HTTP_403_FORBIDDEN
            )

        tercero = self.get_object()
        nuevo_comercial_id = request.data.get('nuevo_comercial_id')

        if not nuevo_comercial_id:
            return Response(
                {'error': 'El ID del nuevo comercial es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            nuevo_comercial = User.objects.get(
                id=nuevo_comercial_id,
                role='comercial',
                is_active=True
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Comercial no encontrado o inactivo'},
                status=status.HTTP_404_NOT_FOUND
            )

        comercial_anterior = tercero.asignado_a
        tercero.asignado_a = nuevo_comercial
        tercero.save()

        logger.info(f"Tercero {tercero.id} reasignado de {comercial_anterior} a {nuevo_comercial} por {request.user.username}")

        return Response({
            'mensaje': 'Tercero reasignado exitosamente',
            'comercial_anterior': comercial_anterior.get_full_name() if comercial_anterior else None,
            'comercial_nuevo': nuevo_comercial.get_full_name(),
            'tercero_id': str(tercero.id)
        })

    @action(detail=False, methods=['get'])
    def balance_asignaciones(self, request):
        """
        Obtener balance de asignaciones entre comerciales
        GET /api/terceros/balance_asignaciones/
        """
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        User = get_user_model()
        
        # Solo procesos puede ver el balance
        if request.user.role != 'procesos':
            return Response(
                {'error': 'Solo el área de procesos puede ver el balance de asignaciones'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Obtener comerciales con sus asignaciones
        comerciales = User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            total_asignados=Count('terceros_asignados_comercial'),
            pendientes=Count('terceros_asignados_comercial', filter=Q(terceros_asignados_comercial__estado_aprobacion='pendiente')),
            en_revision=Count('terceros_asignados_comercial', filter=Q(terceros_asignados_comercial__estado_aprobacion='en_revision')),
            aprobados=Count('terceros_asignados_comercial', filter=Q(terceros_asignados_comercial__estado_aprobacion='aprobado')),
            rechazados=Count('terceros_asignados_comercial', filter=Q(terceros_asignados_comercial__estado_aprobacion='rechazado'))
        ).order_by('total_asignados')

        balance = []
        for comercial in comerciales:
            balance.append({
                'id': str(comercial.id),
                'nombre_completo': comercial.get_full_name(),
                'email': comercial.email,
                'total_asignados': comercial.total_asignados,
                'pendientes': comercial.pendientes,
                'en_revision': comercial.en_revision,
                'aprobados': comercial.aprobados,
                'rechazados': comercial.rechazados
            })

        return Response({
            'balance_comerciales': balance,
            'total_comerciales_activos': comerciales.count()
        })

    @action(detail=True, methods=['post'])
    def asignar_a_procesos(self, request, pk=None):
        """
        Asignar un tercero a un usuario de procesos (solo comerciales pueden hacer esto)
        POST /api/terceros/{id}/asignar_a_procesos/
        Body: {"usuario_procesos_id": "uuid"} (opcional, si no se envía asigna automáticamente)
        """
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from terceros.models import asignar_procesos_automaticamente
        
        User = get_user_model()
        
        # Solo comerciales pueden asignar a procesos
        if request.user.role != 'comercial':
            return Response(
                {'error': 'Solo los comerciales pueden asignar terceros a procesos'},
                status=status.HTTP_403_FORBIDDEN
            )

        tercero = self.get_object()
        
        # Verificar que el tercero esté asignado al comercial que hace la petición
        if tercero.asignado_a != request.user:
            return Response(
                {'error': 'Solo puedes asignar terceros que están asignados a ti'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verificar que el tercero no esté ya asignado a procesos
        if tercero.asignado_a_procesos:
            return Response(
                {'error': f'Este tercero ya está asignado a {tercero.asignado_a_procesos.get_full_name()}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario_procesos_id = request.data.get('usuario_procesos_id')
        
        if usuario_procesos_id:
            # Asignación manual a usuario específico
            try:
                usuario_procesos = User.objects.get(
                    id=usuario_procesos_id,
                    role='procesos',
                    is_active=True
                )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Usuario de procesos no encontrado o inactivo'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Asignación automática equitativa
            usuario_procesos = asignar_procesos_automaticamente()
            if not usuario_procesos:
                return Response(
                    {'error': 'No hay usuarios de procesos disponibles'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Realizar la asignación
        tercero.asignado_a_procesos = usuario_procesos
        tercero.fecha_asignacion_procesos = timezone.now()
        tercero.estado_aprobacion = 'en_revision'  # Cambiar estado automáticamente
        tercero.save()

        logger.info(f"Tercero {tercero.id} asignado a procesos ({usuario_procesos.get_full_name()}) por comercial {request.user.username}")

        return Response({
            'mensaje': 'Tercero asignado a procesos exitosamente',
            'usuario_procesos': usuario_procesos.get_full_name(),
            'fecha_asignacion': tercero.fecha_asignacion_procesos,
            'nuevo_estado': tercero.estado_aprobacion
        })

    @action(detail=False, methods=['get'])
    def mis_terceros_para_procesos(self, request):
        """
        Obtener terceros asignados al usuario de procesos autenticado
        GET /api/terceros/mis_terceros_para_procesos/
        """
        if request.user.role != 'procesos':
            return Response(
                {'error': 'Solo los usuarios de procesos pueden acceder a esta funcionalidad'},
                status=status.HTTP_403_FORBIDDEN
            )

        terceros = Tercero.objects.filter(asignado_a_procesos=request.user).order_by('-fecha_asignacion_procesos')
        serializer = TerceroListSerializer(terceros, many=True)
        
        # Estadísticas adicionales
        stats = {
            'total_asignados': terceros.count(),
            'en_revision': terceros.filter(estado_aprobacion='en_revision').count(),
            'requiere_ajustes': terceros.filter(estado_aprobacion='requiere_ajustes').count(),
            'aprobados': terceros.filter(estado_aprobacion='aprobado').count(),
            'rechazados': terceros.filter(estado_aprobacion='rechazado').count(),
        }

        return Response({
            'terceros': serializer.data,
            'estadisticas': stats
        })

    @action(detail=False, methods=['get'])
    def balance_asignaciones_procesos(self, request):
        """
        Obtener balance de asignaciones entre usuarios de procesos
        GET /api/terceros/balance_asignaciones_procesos/
        """
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        User = get_user_model()
        
        # Solo procesos y administradores pueden ver el balance
        if request.user.role not in ['procesos', 'admin']:
            return Response(
                {'error': 'Solo procesos o administradores pueden ver el balance'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Obtener usuarios de procesos con sus asignaciones
        usuarios_procesos = User.objects.filter(
            role='procesos',
            is_active=True
        ).annotate(
            total_asignados=Count('terceros_asignados_procesos'),
            en_revision=Count('terceros_asignados_procesos', filter=Q(terceros_asignados_procesos__estado_aprobacion='en_revision')),
            requiere_ajustes=Count('terceros_asignados_procesos', filter=Q(terceros_asignados_procesos__estado_aprobacion='requiere_ajustes')),
            aprobados=Count('terceros_asignados_procesos', filter=Q(terceros_asignados_procesos__estado_aprobacion='aprobado')),
            rechazados=Count('terceros_asignados_procesos', filter=Q(terceros_asignados_procesos__estado_aprobacion='rechazado'))
        ).order_by('total_asignados')

        balance = []
        for usuario in usuarios_procesos:
            balance.append({
                'id': str(usuario.id),
                'nombre_completo': usuario.get_full_name(),
                'email': usuario.email,
                'total_asignados': usuario.total_asignados,
                'en_revision': usuario.en_revision,
                'requiere_ajustes': usuario.requiere_ajustes,
                'aprobados': usuario.aprobados,
                'rechazados': usuario.rechazados
            })

        return Response({
            'balance_procesos': balance,
            'total_usuarios_procesos_activos': usuarios_procesos.count()
        })

    @action(detail=False, methods=['post'])
    def vinculacion_completa(self, request):
        """
        Endpoint específico para formulario completo de vinculación según PROMPT
        POST /api/terceros/vinculacion_completa/
        """
        serializer = TerceroCompleteSerializer(data=request.data)
        
        if serializer.is_valid():
            # Crear el tercero con todas las relaciones
            tercero = serializer.save()
            
            logger.info(f"Tercero de vinculación completa creado: {tercero.id} - {tercero.numero_documento}")
            
            # Respuesta según formato del PROMPT
            return Response({
                'success': True,
                'message': 'Tercero creado exitosamente',
                'data': TerceroCompleteSerializer(tercero).data,
                'next_steps': {
                    'message': 'Su solicitud está en revisión. Recibirá notificación por email.',
                    'expected_time': '24-48 horas'
                }
            }, status=status.HTTP_201_CREATED)
        else:
            # Respuesta de error según formato del PROMPT
            return Response({
                'success': False,
                'message': 'Error en la validación de datos',
                'errors': serializer.errors,
                'error_code': 'VALIDATION_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def detalle_completo(self, request, pk=None):
        """
        Obtener detalle completo de tercero con todas las relaciones incluyendo PEP
        GET /api/terceros/{id}/detalle_completo/
        """
        tercero = self.get_object()
        
        # Usar el serializer que incluye información PEP
        serializer = TerceroCompletoPEPSerializer(tercero)
        
        # Agregar información adicional de representantes y accionistas
        data = serializer.data
        
        # Agregar representantes legales
        representantes = tercero.representantes_legales.all()
        data['representantes_legales'] = [{
            'id': rep.id,
            'nombre_completo': rep.nombre_completo,
            'tipo_identificacion': rep.tipo_identificacion,
            'numero_identificacion': rep.numero_identificacion,
            'direccion': rep.direccion,
            'telefono': rep.telefono
        } for rep in representantes]
        
        # Agregar accionistas
        accionistas = tercero.accionistas.all()
        data['accionistas_detalle'] = [{
            'id': acc.id,
            'nombre': acc.nombre,
            'tipo_identificacion': acc.tipo_identificacion,
            'numero_identificacion': acc.numero_identificacion,
            'porcentaje_participacion': str(acc.porcentaje_participacion)
        } for acc in accionistas]
        
        # Agregar información PEP detallada con todos los campos del formulario
        informacion_pep = tercero.informacion_pep_nueva.all()
        data['informacion_pep_detalle'] = [{
            'id': pep.id,
            'nombre': pep.nombre,
            'tipo': pep.tipo,
            'numero_identificacion': pep.numero_identificacion,
            # Nuevos campos del formulario público
            'cargo': pep.cargo,
            'parentesco': pep.parentesco,
            'fecha_vinculacion': pep.fecha_vinculacion.isoformat() if pep.fecha_vinculacion else None,
            'fecha_retiro': pep.fecha_retiro.isoformat() if pep.fecha_retiro else None,
            'cuentas_financieras_exterior': pep.cuentas_financieras_exterior,
            # Campos legacy (mantener compatibilidad)
            'patrimonio_fiducia': pep.patrimonio_fiducia,
            'relaciones_comerciales': pep.relaciones_comerciales,
            'created_at': pep.created_at.isoformat()
        } for pep in informacion_pep]
        
        return Response({
            'success': True,
            'data': data,
            'resumen_sarlaft': {
                'es_pep': tercero.persona_expuesta_politica or False,
                'total_registros_pep': len(informacion_pep),
                'total_representantes': len(representantes),
                'total_accionistas': len(accionistas),
                'suma_porcentajes_accionarios': sum(acc.porcentaje_participacion for acc in accionistas),
                'declaraciones_completas': {
                    'constituye_patrimonios': tercero.constituyePatrimoniosAutonomos,
                    'declaracion_transparencia': tercero.declaracionTransparencia,
                    'manejo_alto_efectivo': tercero.manejoAltoEfectivo,
                    'autorizacion_datos': tercero.autorizacionTratamientoDatos
                }
            }
        })
    
    @action(detail=True, methods=['post'])
    def asignar_comercial_equitativo(self, request, pk=None):
        """
        Asigna un comercial de forma equitativa al tercero.
        Solo asigna si el tercero NO tiene comercial asignado.
        Solo usuarios con rol 'procesos' pueden usar este endpoint.
        
        POST /api/terceros/{id}/asignar_comercial_equitativo/
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden asignar comerciales'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Si ya tiene comercial asignado, no permitir reasignación con este endpoint
        if tercero.asignado_a:
            return Response({
                'success': False,
                'error': 'El tercero ya tiene un comercial asignado. Use reasignar_comercial_equitativo para cambiar.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener comercial específico del request o usar el menos cargado
        comercial_id = request.data.get('comercial_id')
        if comercial_id:
            try:
                comercial = User.objects.get(id=comercial_id, role='comercial', is_active=True)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Comercial no encontrado o inactivo'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Usar el comercial con menos carga
            comerciales = tercero.get_comerciales_disponibles()
            if not comerciales.exists():
                return Response({
                    'success': False,
                    'error': 'No hay comerciales disponibles'
                }, status=status.HTTP_400_BAD_REQUEST)
            comercial = comerciales.first()
        
        # Intentar asignar comercial
        success = tercero.asignar_comercial(comercial)
        
        if success:
            # Recargar el tercero para obtener los datos actualizados
            tercero.refresh_from_db()
            return Response({
                'success': True,
                'message': f'Tercero asignado exitosamente al comercial {tercero.asignado_a.get_full_name()}',
                'comercial': {
                    'id': tercero.asignado_a.id,
                    'nombre': tercero.asignado_a.get_full_name(),
                    'email': tercero.asignado_a.email
                }
            })
        else:
            if tercero.asignado_a:
                return Response({
                    'success': False,
                    'error': f'El tercero ya tiene un comercial asignado: {tercero.asignado_a.get_full_name()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'success': False,
                    'error': 'No hay comerciales disponibles para asignar'
                }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reasignar_comercial_equitativo(self, request, pk=None):
        """
        Reasigna un comercial de forma equitativa al tercero, incluso si ya tiene uno.
        Solo usuarios con rol 'procesos' pueden usar este endpoint.
        
        POST /api/terceros/{id}/reasignar_comercial_equitativo/
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden reasignar comerciales'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener comercial específico del request o usar el menos cargado
        comercial_id = request.data.get('comercial_id')
        if comercial_id:
            try:
                comercial = User.objects.get(id=comercial_id, role='comercial', is_active=True)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Comercial no encontrado o inactivo'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Usar el comercial con menos carga
            comerciales = tercero.get_comerciales_disponibles()
            if not comerciales.exists():
                return Response({
                    'success': False,
                    'error': 'No hay comerciales disponibles'
                }, status=status.HTTP_400_BAD_REQUEST)
            comercial = comerciales.first()
        
        comercial_anterior = tercero.asignado_a
        success = tercero.asignar_comercial(comercial)
        
        if success:
            tercero.refresh_from_db()
            mensaje = f'Tercero reasignado exitosamente al comercial {tercero.asignado_a.get_full_name()}'
            if comercial_anterior:
                mensaje += f' (anteriormente asignado a {comercial_anterior.get_full_name()})'
            
            return Response({
                'success': True,
                'message': mensaje,
                'comercial': {
                    'id': tercero.asignado_a.id,
                    'nombre': tercero.asignado_a.get_full_name(),
                    'email': tercero.asignado_a.email
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'No hay comerciales disponibles para reasignar'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def desasignar_comercial(self, request, pk=None):
        """
        Quita el comercial asignado al tercero.
        Solo usuarios con rol 'procesos' pueden usar este endpoint.
        
        POST /api/terceros/{id}/desasignar_comercial/
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden desasignar comerciales'
            }, status=status.HTTP_403_FORBIDDEN)
        
        comercial_anterior = tercero.asignado_a
        success = tercero.desasignar_comercial()
        
        if success:
            return Response({
                'success': True,
                'message': f'Comercial {comercial_anterior.get_full_name()} desasignado exitosamente del tercero'
            })
        else:
            return Response({
                'success': False,
                'error': 'El tercero no tiene comercial asignado'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def asignar_o_reasignar_comercial(self, request, pk=None):
        """
        Asigna o reasigna un comercial de forma equitativa al tercero.
        Funciona sin importar si ya tiene comercial asignado.
        Solo usuarios con rol 'procesos' pueden usar este endpoint.
        
        POST /api/terceros/{id}/asignar_o_reasignar_comercial/
        """
        tercero = self.get_object()
        
        # Verificar que el usuario tenga permisos de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden asignar/reasignar comerciales'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener comercial específico del request o usar el menos cargado
        comercial_id = request.data.get('comercial_id')
        if comercial_id:
            try:
                comercial = User.objects.get(id=comercial_id, role='comercial', is_active=True)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Comercial no encontrado o inactivo'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Usar el comercial con menos carga
            comerciales = tercero.get_comerciales_disponibles()
            if not comerciales.exists():
                return Response({
                    'success': False,
                    'error': 'No hay comerciales disponibles'
                }, status=status.HTTP_400_BAD_REQUEST)
            comercial = comerciales.first()
        
        comercial_anterior = tercero.asignado_a
        success = tercero.asignar_comercial(comercial)
        
        if success:
            tercero.refresh_from_db()
            if comercial_anterior:
                if comercial_anterior != tercero.asignado_a:
                    mensaje = f'Tercero reasignado de {comercial_anterior.get_full_name()} a {tercero.asignado_a.get_full_name()}'
                else:
                    mensaje = f'Tercero mantiene la asignación con {tercero.asignado_a.get_full_name()}'
            else:
                mensaje = f'Tercero asignado exitosamente al comercial {tercero.asignado_a.get_full_name()}'
            
            return Response({
                'success': True,
                'message': mensaje,
                'comercial': {
                    'id': tercero.asignado_a.id,
                    'nombre': tercero.asignado_a.get_full_name(),
                    'email': tercero.asignado_a.email
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'No hay comerciales disponibles'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def comerciales_disponibles(self, request):
        """
        Obtiene la lista de comerciales disponibles con su carga actual
        Solo usuarios con rol 'procesos' pueden usar este endpoint.
        
        GET /api/terceros/comerciales_disponibles/
        """
        # Verificar que el usuario tenga permisos de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden ver comerciales disponibles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.db.models import Count
        
        comerciales = User.objects.filter(
            role='comercial',
            is_active=True
        ).exclude(
            username__contains='test'  # Excluir usuarios de prueba
        ).annotate(
            num_terceros_asignados=Count('terceros_asignados_comercial')
        ).order_by('num_terceros_asignados')
        
        comerciales_data = []
        for comercial in comerciales:
            comerciales_data.append({
                'id': comercial.id,
                'nombre': comercial.get_full_name(),
                'email': comercial.email,
                'terceros_asignados': comercial.num_terceros_asignados
            })
        
        return Response({
            'success': True,
            'comerciales': comerciales_data
        })

    @action(detail=False, methods=['get'])
    def terceros_para_cumplimiento(self, request):
        """
        Obtiene terceros que requieren revisión de cumplimiento (PEP, riesgo alto, etc.)
        Solo para oficial de cumplimiento y administradores
        
        GET /api/terceros/terceros_para_cumplimiento/
        """
        if request.user.role not in ['oficial_cumplimiento', 'administrador']:
            return Response({
                'success': False,
                'error': 'Solo oficiales de cumplimiento y administradores pueden acceder'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Filtrar terceros que requieren atención especial de cumplimiento
        terceros = Tercero.objects.filter(
            Q(personaExpuestaPolitica=True) |  # PEP
            Q(manejoAltoEfectivo=True) |       # Alto efectivo
            Q(constituyePatrimoniosAutonomos=True) |  # Patrimonios autónomos
            Q(estado_aprobacion='en_revision')  # En revisión
        ).order_by('-created_at')
        
        serializer = TerceroListSerializer(terceros, many=True)
        
        # Estadísticas de cumplimiento
        stats = {
            'total_revision_cumplimiento': terceros.count(),
            'pep_pendientes': terceros.filter(personaExpuestaPolitica=True, estado_aprobacion__in=['pendiente', 'en_revision']).count(),
            'alto_efectivo': terceros.filter(manejoAltoEfectivo=True).count(),
            'patrimonios_autonomos': terceros.filter(constituyePatrimoniosAutonomos=True).count(),
            'en_revision': terceros.filter(estado_aprobacion='en_revision').count(),
            'requiere_ajustes': terceros.filter(estado_aprobacion='requiere_ajustes').count()
        }
        
        return Response({
            'success': True,
            'terceros': serializer.data,
            'estadisticas_cumplimiento': stats
        })

    @action(detail=True, methods=['get'])
    def analisis_sarlaft(self, request, pk=None):
        """
        Análisis SARLAFT detallado de un tercero
        Solo para oficial de cumplimiento y administradores
        
        GET /api/terceros/{id}/analisis_sarlaft/
        """
        if request.user.role not in ['oficial_cumplimiento', 'administrador']:
            return Response({
                'success': False,
                'error': 'Solo oficiales de cumplimiento y administradores pueden acceder'
            }, status=status.HTTP_403_FORBIDDEN)
        
        tercero = self.get_object()
        
        # Calcular nivel de riesgo SARLAFT
        riesgo_score = 0
        alertas = []
        
        # Factores de riesgo
        if tercero.persona_expuesta_politica:
            riesgo_score += 30
            alertas.append({
                'tipo': 'PEP',
                'descripcion': 'Persona Expuesta Políticamente',
                'nivel': 'ALTO',
                'registros_pep': tercero.informacion_pep_nueva.count()
            })
        
        if tercero.manejoAltoEfectivo:
            riesgo_score += 20
            alertas.append({
                'tipo': 'EFECTIVO',
                'descripcion': 'Manejo de alto volumen en efectivo',
                'nivel': 'MEDIO'
            })
        
        if tercero.constituyePatrimoniosAutonomos:
            riesgo_score += 15
            alertas.append({
                'tipo': 'PATRIMONIOS',
                'descripcion': 'Constituye patrimonios autónomos',
                'nivel': 'MEDIO'
            })
        
        # Validaciones de integridad
        validaciones = []
        
        # Verificar representantes legales para personas jurídicas
        if tercero.tipo_persona == 'juridica':
            num_representantes = tercero.representantes_legales.count()
            if num_representantes == 0:
                validaciones.append({
                    'campo': 'representantes_legales',
                    'estado': 'FALTANTE',
                    'mensaje': 'Persona jurídica sin representantes legales'
                })
            else:
                validaciones.append({
                    'campo': 'representantes_legales',
                    'estado': 'COMPLETO',
                    'mensaje': f'{num_representantes} representante(s) registrado(s)'
                })
            
            # Verificar accionistas
            accionistas = tercero.accionistas.all()
            total_porcentaje = sum(acc.porcentaje_participacion for acc in accionistas)
            if total_porcentaje < 100:
                validaciones.append({
                    'campo': 'accionistas',
                    'estado': 'INCOMPLETO',
                    'mensaje': f'Composición accionaria incompleta: {total_porcentaje}%'
                })
            else:
                validaciones.append({
                    'campo': 'accionistas',
                    'estado': 'COMPLETO',
                    'mensaje': f'Composición accionaria completa: {total_porcentaje}%'
                })
        
        # Verificar información PEP si aplica
        if tercero.persona_expuesta_politica:
            num_registros_pep = tercero.informacion_pep_nueva.count()
            if num_registros_pep == 0:
                validaciones.append({
                    'campo': 'informacion_pep',
                    'estado': 'FALTANTE',
                    'mensaje': 'Marcado como PEP pero sin registros de información PEP'
                })
            else:
                validaciones.append({
                    'campo': 'informacion_pep',
                    'estado': 'COMPLETO',
                    'mensaje': f'{num_registros_pep} registro(s) PEP documentado(s)'
                })
        
        # Determinar nivel de riesgo final
        if riesgo_score >= 40:
            nivel_riesgo = 'ALTO'
        elif riesgo_score >= 20:
            nivel_riesgo = 'MEDIO'
        else:
            nivel_riesgo = 'BAJO'
        
        # Verificar documentos críticos
        documentos_criticos = tercero.documentos.filter(
            tipo_documento__in=['cedula_representante', 'rut', 'camara_comercio', 'estados_financieros']
        )
        
        return Response({
            'success': True,
            'tercero_id': str(tercero.id),
            'numero_documento': tercero.numero_documento,
            'analisis_sarlaft': {
                'nivel_riesgo': nivel_riesgo,
                'score_riesgo': riesgo_score,
                'alertas': alertas,
                'validaciones': validaciones,
                'factores_evaluados': {
                    'persona_expuesta_politica': tercero.persona_expuesta_politica,
                    'manejo_alto_efectivo': tercero.manejoAltoEfectivo,
                    'patrimonios_autonomos': tercero.constituyePatrimoniosAutonomos,
                    'declaracion_transparencia': tercero.declaracionTransparencia,
                    'autorizacion_datos': tercero.autorizacionTratamientoDatos
                },
                'documentos_criticos': {
                    'total_requeridos': 4 if tercero.tipo_persona == 'juridica' else 2,
                    'total_recibidos': documentos_criticos.count(),
                    'documentos': [
                        {
                            'tipo': doc.tipo_documento,
                            'nombre': doc.nombre_original,
                            'fecha_subida': doc.fecha_subida
                        } for doc in documentos_criticos
                    ]
                }
            },
            'recomendacion': self._generar_recomendacion_cumplimiento(tercero, nivel_riesgo, validaciones)
        })

    def _generar_recomendacion_cumplimiento(self, tercero, nivel_riesgo, validaciones):
        """Genera recomendación basada en el análisis SARLAFT"""
        recomendaciones = []
        
        if nivel_riesgo == 'ALTO':
            recomendaciones.append('Requiere aprobación del oficial de cumplimiento')
            recomendaciones.append('Documentación adicional requerida')
            recomendaciones.append('Monitoreo continuo recomendado')
        elif nivel_riesgo == 'MEDIO':
            recomendaciones.append('Revisión detallada de documentación')
            recomendaciones.append('Validación de información PEP si aplica')
        else:
            recomendaciones.append('Proceso estándar de vinculación')
        
        # Recomendaciones específicas por validaciones fallidas
        for validacion in validaciones:
            if validacion['estado'] in ['FALTANTE', 'INCOMPLETO']:
                if validacion['campo'] == 'representantes_legales':
                    recomendaciones.append('Solicitar información de representantes legales')
                elif validacion['campo'] == 'accionistas':
                    recomendaciones.append('Completar información de composición accionaria')
                elif validacion['campo'] == 'informacion_pep':
                    recomendaciones.append('Documentar completamente información PEP')
        
        return {
            'accion_recomendada': 'APROBAR' if nivel_riesgo == 'BAJO' else 'REVISAR_DETALLADO',
            'requiere_supervision': nivel_riesgo in ['ALTO', 'MEDIO'],
            'observaciones': recomendaciones
        }

    @action(detail=True, methods=['post'])
    def marcar_revision_cumplimiento(self, request, pk=None):
        """
        Marcar tercero como revisado por cumplimiento
        Solo para oficial de cumplimiento y administradores
        
        POST /api/terceros/{id}/marcar_revision_cumplimiento/
        Body: {"observaciones_cumplimiento": "string", "aprobado": boolean}
        """
        if request.user.role not in ['oficial_cumplimiento', 'administrador']:
            return Response({
                'success': False,
                'error': 'Solo oficiales de cumplimiento y administradores pueden marcar revisiones'
            }, status=status.HTTP_403_FORBIDDEN)
        
        tercero = self.get_object()
        observaciones = request.data.get('observaciones_cumplimiento', '')
        aprobado = request.data.get('aprobado', False)
        
        # Crear registro de revisión de cumplimiento (si existe el modelo)
        try:
            from .models import RevisionCumplimiento
            RevisionCumplimiento.objects.create(
                tercero=tercero,
                usuario=request.user,
                observaciones=observaciones,
                aprobado=aprobado
            )
        except ImportError:
            # El modelo no existe, solo actualizar el tercero
            pass
        
        # Actualizar estado del tercero
        if aprobado:
            tercero.estado_aprobacion = 'aprobado'
            tercero.aprobado_por = request.user
        else:
            tercero.estado_aprobacion = 'requiere_ajustes'
        
        # Agregar observaciones de cumplimiento
        if observaciones:
            observaciones_existentes = tercero.observaciones or ''
            if observaciones_existentes:
                tercero.observaciones = f"{observaciones_existentes}\n\n[CUMPLIMIENTO - {request.user.get_full_name()}]: {observaciones}"
            else:
                tercero.observaciones = f"[CUMPLIMIENTO - {request.user.get_full_name()}]: {observaciones}"
        
        tercero.save()
        
        logger.info(f"Tercero {tercero.id} revisado por cumplimiento por {request.user.username} - Aprobado: {aprobado}")
        
        return Response({
            'success': True,
            'message': f'Tercero {"aprobado" if aprobado else "requiere ajustes"} por cumplimiento',
            'nuevo_estado': tercero.estado_aprobacion,
            'observaciones_agregadas': bool(observaciones)
        })

    @action(detail=False, methods=['get'])
    def reportes_cumplimiento(self, request):
        """
        Reportes de cumplimiento SARLAFT
        Solo para oficial de cumplimiento y administradores
        
        GET /api/terceros/reportes_cumplimiento/
        """
        if request.user.role not in ['oficial_cumplimiento', 'administrador']:
            return Response({
                'success': False,
                'error': 'Solo oficiales de cumplimiento y administradores pueden generar reportes'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.utils import timezone
        from datetime import timedelta
        
        # Periodo de análisis (últimos 30 días por defecto)
        periodo_dias = int(request.query_params.get('periodo_dias', 30))
        fecha_inicio = timezone.now() - timedelta(days=periodo_dias)
        
        # Estadísticas generales
        total_terceros = Tercero.objects.count()
        terceros_periodo = Tercero.objects.filter(created_at__gte=fecha_inicio)
        
        # Estadísticas PEP
        total_pep = Tercero.objects.filter(personaExpuestaPolitica=True).count()
        pep_pendientes = Tercero.objects.filter(
            personaExpuestaPolitica=True,
            estado_aprobacion__in=['pendiente', 'en_revision']
        ).count()
        
        # Estadísticas de riesgo
        alto_efectivo = Tercero.objects.filter(manejoAltoEfectivo=True).count()
        patrimonios_autonomos = Tercero.objects.filter(constituyePatrimoniosAutonomos=True).count()
        
        # Terceros por estado de aprobación
        por_estado = dict(
            Tercero.objects.values('estado_aprobacion').annotate(
                count=Count('id')
            ).values_list('estado_aprobacion', 'count')
        )
        
        # Terceros con alertas SARLAFT
        terceros_alto_riesgo = Tercero.objects.filter(
            Q(personaExpuestaPolitica=True) & 
            Q(manejoAltoEfectivo=True)
        ).count()
        
        return Response({
            'success': True,
            'periodo_analisis': {
                'fecha_inicio': fecha_inicio.date(),
                'fecha_fin': timezone.now().date(),
                'dias': periodo_dias
            },
            'estadisticas_generales': {
                'total_terceros': total_terceros,
                'nuevos_en_periodo': terceros_periodo.count(),
                'por_estado_aprobacion': por_estado
            },
            'estadisticas_sarlaft': {
                'total_pep': total_pep,
                'pep_pendientes_revision': pep_pendientes,
                'manejo_alto_efectivo': alto_efectivo,
                'patrimonios_autonomos': patrimonios_autonomos,
                'terceros_alto_riesgo': terceros_alto_riesgo
            },
            'alertas_cumplimiento': {
                'pep_sin_documentar': Tercero.objects.filter(
                    personaExpuestaPolitica=True,
                    informacion_pep__isnull=True
                ).count(),
                'personas_juridicas_sin_representantes': Tercero.objects.filter(
                    tipo_persona='juridica',
                    representantes_legales__isnull=True
                ).count(),
                'composicion_accionaria_incompleta': self._contar_accionistas_incompletos()
            }
        })

    def _contar_accionistas_incompletos(self):
        """Cuenta personas jurídicas con composición accionaria incompleta"""
        from django.db.models import Sum
        
        personas_juridicas = Tercero.objects.filter(tipo_persona='juridica')
        incompletas = 0
        
        for tercero in personas_juridicas:
            total_porcentaje = tercero.accionistas.aggregate(
                total=Sum('porcentaje_participacion')
            )['total'] or 0
            
            if total_porcentaje < 100:
                incompletas += 1
        
        return incompletas

    @action(detail=False, methods=['get'])
    def auditoria_sistema(self, request):
        """
        Auditoría completa del sistema para administradores
        Solo para administradores
        
        GET /api/terceros/auditoria_sistema/
        """
        if request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden acceder a la auditoría del sistema'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Avg, Max, Min
        
        # Estadísticas de rendimiento del sistema
        total_terceros = Tercero.objects.count()
        
        # Análisis de tiempos de procesamiento
        terceros_con_fechas = Tercero.objects.exclude(
            Q(created_at__isnull=True) | Q(updated_at__isnull=True)
        )
        
        tiempos_procesamiento = []
        for tercero in terceros_con_fechas:
            if tercero.estado_aprobacion == 'aprobado' and tercero.updated_at and tercero.created_at:
                tiempo_delta = tercero.updated_at - tercero.created_at
                tiempos_procesamiento.append(tiempo_delta.total_seconds() / 3600)  # En horas
        
        # Estadísticas de usuarios y asignaciones
        usuarios_stats = User.objects.filter(is_active=True).values('role').annotate(
            count=Count('id')
        )
        
        # Distribución de carga por comerciales
        from django.db.models import Count
        carga_comerciales = User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            terceros_asignados=Count('terceros_asignados_comercial')
        ).order_by('-terceros_asignados')
        
        # Análisis de documentos
        docs_stats = DocumentoTercero.objects.aggregate(
            total_documentos=Count('id'),
            tamano_promedio=Avg('tamano_archivo'),
            documento_mas_grande=Max('tamano_archivo'),
            documento_mas_pequeno=Min('tamano_archivo')
        )
        
        # Problemas identificados
        problemas = []
        
        # 1. Terceros PEP sin información PEP
        pep_sin_info = Tercero.objects.filter(
            personaExpuestaPolitica=True,
            informacion_pep__isnull=True
        ).count()
        if pep_sin_info > 0:
            problemas.append({
                'tipo': 'DATOS_INCONSISTENTES',
                'descripcion': f'{pep_sin_info} terceros marcados como PEP sin información PEP',
                'severidad': 'ALTA'
            })
        
        # 2. Personas jurídicas sin representantes
        juridicas_sin_rep = Tercero.objects.filter(
            tipo_persona='juridica',
            representantes_legales__isnull=True
        ).count()
        if juridicas_sin_rep > 0:
            problemas.append({
                'tipo': 'DATOS_INCOMPLETOS',
                'descripcion': f'{juridicas_sin_rep} personas jurídicas sin representantes legales',
                'severidad': 'MEDIA'
            })
        
        # 3. Terceros pendientes hace más de 30 días
        fecha_limite = timezone.now() - timedelta(days=30)
        terceros_antiguos = Tercero.objects.filter(
            estado_aprobacion='pendiente',
            created_at__lt=fecha_limite
        ).count()
        if terceros_antiguos > 0:
            problemas.append({
                'tipo': 'PROCESO_RETRASADO',
                'descripcion': f'{terceros_antiguos} terceros pendientes por más de 30 días',
                'severidad': 'MEDIA'
            })
        
        # 4. Desbalance en asignaciones
        if carga_comerciales.exists():
            max_carga = carga_comerciales.first().terceros_asignados
            min_carga = carga_comerciales.last().terceros_asignados
            if max_carga - min_carga > 10:
                problemas.append({
                    'tipo': 'DESBALANCE_CARGA',
                    'descripcion': f'Desbalance en asignaciones: {max_carga} vs {min_carga}',
                    'severidad': 'BAJA'
                })
        
        return Response({
            'success': True,
            'auditoria_timestamp': timezone.now(),
            'estadisticas_generales': {
                'total_terceros': total_terceros,
                'tiempo_promedio_procesamiento_horas': sum(tiempos_procesamiento) / len(tiempos_procesamiento) if tiempos_procesamiento else 0,
                'terceros_procesados_ultimo_mes': Tercero.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count()
            },
            'usuarios_sistema': dict(usuarios_stats.values_list('role', 'count')),
            'distribucion_carga_comerciales': [
                {
                    'comercial': com.get_full_name(),
                    'email': com.email,
                    'terceros_asignados': com.terceros_asignados
                } for com in carga_comerciales
            ],
            'estadisticas_documentos': {
                'total_documentos': docs_stats['total_documentos'] or 0,
                'tamano_promedio_mb': round((docs_stats['tamano_promedio'] or 0) / (1024*1024), 2),
                'documento_mas_grande_mb': round((docs_stats['documento_mas_grande'] or 0) / (1024*1024), 2),
                'documento_mas_pequeno_kb': round((docs_stats['documento_mas_pequeno'] or 0) / 1024, 2)
            },
            'problemas_identificados': problemas,
            'recomendaciones': self._generar_recomendaciones_admin(problemas, carga_comerciales)
        })

    def _generar_recomendaciones_admin(self, problemas, carga_comerciales):
        """Genera recomendaciones para el administrador basadas en la auditoría"""
        recomendaciones = []
        
        for problema in problemas:
            if problema['tipo'] == 'DATOS_INCONSISTENTES':
                recomendaciones.append('Revisar y corregir terceros PEP sin información PEP documentada')
            elif problema['tipo'] == 'DATOS_INCOMPLETOS':
                recomendaciones.append('Solicitar información faltante de representantes legales')
            elif problema['tipo'] == 'PROCESO_RETRASADO':
                recomendaciones.append('Revisar terceros pendientes antiguos y acelerar procesamiento')
            elif problema['tipo'] == 'DESBALANCE_CARGA':
                recomendaciones.append('Redistribuir asignaciones entre comerciales para balancear carga')
        
        if not problemas:
            recomendaciones.append('Sistema funcionando dentro de parámetros normales')
        
        return recomendaciones

    @action(detail=False, methods=['post'])
    def redistribuir_asignaciones(self, request):
        """
        Redistribuir automáticamente las asignaciones entre comerciales
        Solo para administradores
        
        POST /api/terceros/redistribuir_asignaciones/
        Body: {"modo": "equitativo"} (opcional)
        """
        if request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden redistribuir asignaciones'
            }, status=status.HTTP_403_FORBIDDEN)
        
        modo = request.data.get('modo', 'equitativo')
        
        # Obtener todos los comerciales activos
        comerciales = User.objects.filter(role='comercial', is_active=True)
        if not comerciales.exists():
            return Response({
                'success': False,
                'error': 'No hay comerciales activos para redistribuir'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener terceros sin comercial asignado o con desbalance
        terceros_sin_asignar = Tercero.objects.filter(asignado_a__isnull=True)
        
        if modo == 'equitativo':
            # Redistribución equitativa
            num_comerciales = comerciales.count()
            terceros_redistribuidos = 0
            
            for i, tercero in enumerate(terceros_sin_asignar):
                comercial = comerciales[i % num_comerciales]
                tercero.asignado_a = comercial
                tercero.save()
                terceros_redistribuidos += 1
            
            return Response({
                'success': True,
                'message': f'{terceros_redistribuidos} terceros redistribuidos equitativamente',
                'distribucion': [
                    {
                        'comercial': com.get_full_name(),
                        'nuevos_asignados': terceros_redistribuidos // num_comerciales + (1 if terceros_redistribuidos % num_comerciales > list(comerciales).index(com) else 0)
                    } for com in comerciales
                ]
            })
        
        return Response({
            'success': False,
            'error': 'Modo de redistribución no válido'
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def dashboard_administrador(self, request):
        """
        Dashboard específico para administradores con métricas avanzadas
        Solo para administradores
        
        GET /api/terceros/dashboard_administrador/
        """
        if request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden acceder al dashboard administrativo'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Avg
        
        # Métricas de rendimiento del último mes
        ultimo_mes = timezone.now() - timedelta(days=30)
        ultima_semana = timezone.now() - timedelta(days=7)
        
        # KPIs principales
        kpis = {
            'terceros_total': Tercero.objects.count(),
            'terceros_ultimo_mes': Tercero.objects.filter(created_at__gte=ultimo_mes).count(),
            'terceros_ultima_semana': Tercero.objects.filter(created_at__gte=ultima_semana).count(),
            'aprobados_ultimo_mes': Tercero.objects.filter(
                estado_aprobacion='aprobado',
                updated_at__gte=ultimo_mes
            ).count(),
            'tasa_aprobacion_mes': 0,  # Se calculará después
            'tiempo_promedio_aprobacion_dias': 0  # Se calculará después
        }
        
        # Calcular tasa de aprobación
        total_procesados_mes = Tercero.objects.filter(
            updated_at__gte=ultimo_mes,
            estado_aprobacion__in=['aprobado', 'rechazado']
        ).count()
        
        if total_procesados_mes > 0:
            kpis['tasa_aprobacion_mes'] = round(
                (kpis['aprobados_ultimo_mes'] / total_procesados_mes) * 100, 2
            )
        
        # Estadísticas por roles
        usuarios_por_rol = User.objects.filter(is_active=True).values('role').annotate(
            count=Count('id')
        )
        
        # Top comerciales por productividad
        top_comerciales = User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            terceros_aprobados_mes=Count(
                'terceros_asignados',
                filter=Q(
                    terceros_asignados__estado_aprobacion='aprobado',
                    terceros_asignados__updated_at__gte=ultimo_mes
                )
            ),
            total_asignados=Count('terceros_asignados_comercial')
        ).order_by('-terceros_aprobados_mes')[:5]
        
        # Análisis de cumplimiento SARLAFT
        sarlaft_stats = {
            'total_pep': Tercero.objects.filter(personaExpuestaPolitica=True).count(),
            'pep_pendientes': Tercero.objects.filter(
                personaExpuestaPolitica=True,
                estado_aprobacion__in=['pendiente', 'en_revision']
            ).count(),
            'alto_riesgo': Tercero.objects.filter(
                Q(personaExpuestaPolitica=True) & Q(manejoAltoEfectivo=True)
            ).count(),
            'requieren_atencion': Tercero.objects.filter(
                Q(personaExpuestaPolitica=True) | Q(manejoAltoEfectivo=True),
                estado_aprobacion__in=['pendiente', 'en_revision']
            ).count()
        }
        
        # Tendencias de los últimos 7 días
        tendencias = []
        for i in range(7):
            fecha = timezone.now() - timedelta(days=i)
            fecha_inicio = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
            fecha_fin = fecha_inicio + timedelta(days=1)
            
            terceros_dia = Tercero.objects.filter(
                created_at__gte=fecha_inicio,
                created_at__lt=fecha_fin
            ).count()
            
            aprobados_dia = Tercero.objects.filter(
                estado_aprobacion='aprobado',
                updated_at__gte=fecha_inicio,
                updated_at__lt=fecha_fin
            ).count()
            
            tendencias.append({
                'fecha': fecha_inicio.date(),
                'nuevos_terceros': terceros_dia,
                'aprobados': aprobados_dia
            })
        
        return Response({
            'success': True,
            'dashboard_timestamp': timezone.now(),
            'kpis_principales': kpis,
            'usuarios_sistema': dict(usuarios_por_rol.values_list('role', 'count')),
            'top_comerciales': [
                {
                    'nombre': com.get_full_name(),
                    'email': com.email,
                    'aprobados_mes': com.terceros_aprobados_mes,
                    'total_asignados': com.total_asignados,
                    'tasa_exito': round(
                        (com.terceros_aprobados_mes / com.total_asignados * 100) if com.total_asignados > 0 else 0, 2
                    )
                } for com in top_comerciales
            ],
            'cumplimiento_sarlaft': sarlaft_stats,
            'tendencias_7_dias': list(reversed(tendencias)),
            'alertas_sistema': self._generar_alertas_sistema()
        })

    def _generar_alertas_sistema(self):
        """Genera alertas del sistema para administradores"""
        alertas = []
        
        from django.utils import timezone
        from datetime import timedelta
        
        # Alerta: Terceros pendientes antiguos
        fecha_limite = timezone.now() - timedelta(days=15)
        terceros_antiguos = Tercero.objects.filter(
            estado_aprobacion='pendiente',
            created_at__lt=fecha_limite
        ).count()
        
        if terceros_antiguos > 0:
            alertas.append({
                'tipo': 'WARNING',
                'mensaje': f'{terceros_antiguos} terceros pendientes por más de 15 días',
                'accion': 'Revisar y acelerar procesamiento'
            })
        
        # Alerta: PEP sin documentar
        pep_sin_info = Tercero.objects.filter(
            personaExpuestaPolitica=True,
            informacion_pep__isnull=True
        ).count()
        
        if pep_sin_info > 0:
            alertas.append({
                'tipo': 'ERROR',
                'mensaje': f'{pep_sin_info} terceros PEP sin información documentada',
                'accion': 'Completar información PEP crítica'
            })
        
        # Alerta: Usuarios inactivos
        usuarios_inactivos = User.objects.filter(
            is_active=False,
            last_login__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if usuarios_inactivos > 0:
            alertas.append({
                'tipo': 'INFO',
                'mensaje': f'{usuarios_inactivos} usuarios recientemente inactivos',
                'accion': 'Revisar estado de usuarios'
            })
        
        if not alertas:
            alertas.append({
                'tipo': 'SUCCESS',
                'mensaje': 'Sistema funcionando correctamente',
                'accion': 'Ninguna acción requerida'
            })
        
        return alertas
    
    # Nuevos endpoints para el flujo extendido
    @action(detail=True, methods=['post'])
    def aprobar_comercial(self, request, pk=None):
        """
        Comercial aprueba tercero y lo envía al administrador
        POST /api/terceros/{id}/aprobar_comercial/
        """
        tercero = self.get_object()
        
        # Verificar que sea comercial
        if not hasattr(request.user, 'role') or request.user.role != 'comercial':
            return Response({
                'success': False,
                'error': 'Solo comerciales pueden aprobar terceros'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar que el tercero esté asignado al comercial
        if tercero.asignado_a != request.user:
            return Response({
                'success': False,
                'error': 'Solo puedes aprobar terceros asignados a ti'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Aprobar
        resultado = tercero.aprobar_por_comercial(request.user)
        
        if resultado:
            return Response({
                'success': True,
                'message': 'Tercero aprobado exitosamente y enviado al administrador',
                'tercero': {
                    'id': str(tercero.id),
                    'estado': tercero.get_estado_aprobacion_display(),
                    'aprobado_por': tercero.aprobado_por_comercial.get_full_name(),
                    'fecha_aprobacion': tercero.fecha_aprobacion_comercial,
                    'asignado_administrador': tercero.asignado_administrador.get_full_name() if tercero.asignado_administrador else None
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Error al aprobar tercero'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """
        Permite agregar comentarios.
        POST /api/terceros/{id}/add_comment/
        
        Permisos:
        - Comercial: Comentarios de aprobación en terceros asignados
        - Procesos: Comentarios generales en cualquier tercero (NUEVO)
        - Administrador/Oficial cumplimiento: Comentarios en cualquier tercero
        
        Body:
        {
            "comment": "Texto del comentario",
            "comment_type": "observacion|aprobacion|nota_interna|proceso" (opcional)
        }
        """
        tercero = self.get_object()
        user_role = getattr(request.user, 'role', None)
        
        # Obtener el comentario del request
        comentario = request.data.get('comment', '')
        tipo_comentario = request.data.get('comment_type', 'observacion')
        
        if not comentario:
            return Response({
                'success': False,
                'error': 'El comentario no puede estar vacío'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Lógica específica por rol
        if user_role == 'comercial':
            # Verificar que el tercero esté asignado al comercial
            if tercero.asignado_a != request.user:
                return Response({
                    'success': False,
                    'error': 'Solo puedes agregar comentarios a terceros asignados a ti'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Agregar comentario según el tipo
            if tipo_comentario == 'aprobacion':
                tercero.comentarios_aprobacion = comentario
            elif tipo_comentario == 'observacion':
                tercero.observaciones_comercial = comentario
            elif tipo_comentario == 'nota_interna':
                tercero.notas_internas = comentario
            else:
                tercero.observaciones_comercial = comentario
            
            # Actualizar fecha de contacto si no existe
            if not tercero.fecha_contacto_inicial:
                tercero.fecha_contacto_inicial = timezone.now()
            
            tercero.save()
            
            # Crear notificación para administradores si es comentario de aprobación
            if tipo_comentario == 'aprobacion':
                self.notify_administrators_of_comment(tercero, request.user, comentario)
        
        elif user_role == 'procesos':
            # Procesos puede agregar comentarios de proceso en cualquier tercero
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            user_name = request.user.get_full_name() or request.user.username
            comentario_con_metadata = f"[PROCESOS - {user_name} - {timestamp}]: {comentario}"
            
            if tipo_comentario == 'proceso' or tipo_comentario == 'observacion':
                # Agregar a observaciones generales con metadata de procesos
                if tercero.observaciones:
                    tercero.observaciones += f"\n\n{comentario_con_metadata}"
                else:
                    tercero.observaciones = comentario_con_metadata
            elif tipo_comentario == 'nota_interna':
                # Agregar a notas internas
                if tercero.notas_internas:
                    tercero.notas_internas += f"\n\n{comentario_con_metadata}"
                else:
                    tercero.notas_internas = comentario_con_metadata
            
            tercero.save()
            
            logger.info(f"Comentario de PROCESOS agregado al tercero {tercero.id} por usuario: {request.user.username}")
        
        elif user_role in ['administrador', 'oficial_cumplimiento']:
            # Administradores y oficiales de cumplimiento pueden agregar cualquier tipo de comentario
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            user_name = request.user.get_full_name() or request.user.username
            role_prefix = user_role.upper()
            comentario_con_metadata = f"[{role_prefix} - {user_name} - {timestamp}]: {comentario}"
            
            if tipo_comentario == 'observacion':
                if tercero.observaciones:
                    tercero.observaciones += f"\n\n{comentario_con_metadata}"
                else:
                    tercero.observaciones = comentario_con_metadata
            elif tipo_comentario == 'nota_interna':
                if tercero.notas_internas:
                    tercero.notas_internas += f"\n\n{comentario_con_metadata}"
                else:
                    tercero.notas_internas = comentario_con_metadata
            elif tipo_comentario == 'aprobacion':
                tercero.comentarios_aprobacion = comentario
            
            tercero.save()
            
            logger.info(f"Comentario de {role_prefix} agregado al tercero {tercero.id} por usuario: {request.user.username}")
        
        else:
            return Response({
                'success': False,
                'error': 'No tienes permisos para agregar comentarios'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return Response({
            'success': True,
            'message': 'Comentario agregado exitosamente',
            'tercero_id': str(tercero.id),
            'comment_type': tipo_comentario,
            'comment': comentario
        })

    @action(detail=True, methods=['get'])
    def get_comments(self, request, pk=None):
        """
        Obtiene todos los comentarios de un tercero de manera estructurada
        GET /api/terceros/{id}/get_comments/
        
        Permisos:
        - Procesos: Puede ver todos los comentarios (NUEVO)
        - Administrador/Oficial cumplimiento: Puede ver todos los comentarios
        - Comercial: Solo comentarios de terceros asignados
        
        Response:
        {
            "success": true,
            "tercero_id": "uuid",
            "comments": {
                "observaciones": [{"texto": "...", "metadata": "..."}],
                "notas_internas": [{"texto": "...", "metadata": "..."}],
                "comentarios_comercial": "...",
                "comentarios_aprobacion": "..."
            }
        }
        """
        tercero = self.get_object()
        user_role = getattr(request.user, 'role', None)
        
        # Verificar permisos por rol
        if user_role == 'comercial':
            if tercero.asignado_a != request.user:
                return Response({
                    'success': False,
                    'error': 'Solo puedes ver comentarios de terceros asignados a ti'
                }, status=status.HTTP_403_FORBIDDEN)
        elif user_role not in ['procesos', 'administrador', 'oficial_cumplimiento']:
            return Response({
                'success': False,
                'error': 'No tienes permisos para ver comentarios'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Parsear observaciones estructuradas
        observaciones_parsed = []
        if tercero.observaciones:
            # Dividir por líneas que contienen metadata [ROL - Usuario - Fecha]
            import re
            pattern = r'\[(PROCESOS|ADMINISTRADOR|OFICIAL_CUMPLIMIENTO|COMERCIAL) - ([^-]+) - ([^\]]+)\]: (.*?)(?=\n\[|$)'
            matches = re.findall(pattern, tercero.observaciones, re.DOTALL)
            
            for match in matches:
                rol, usuario, fecha, texto = match
                observaciones_parsed.append({
                    'rol': rol,
                    'usuario': usuario.strip(),
                    'fecha': fecha.strip(),
                    'texto': texto.strip()
                })
        
        # Parsear notas internas estructuradas
        notas_internas_parsed = []
        if tercero.notas_internas:
            import re
            pattern = r'\[(PROCESOS|ADMINISTRADOR|OFICIAL_CUMPLIMIENTO|COMERCIAL) - ([^-]+) - ([^\]]+)\]: (.*?)(?=\n\[|$)'
            matches = re.findall(pattern, tercero.notas_internas, re.DOTALL)
            
            for match in matches:
                rol, usuario, fecha, texto = match
                notas_internas_parsed.append({
                    'rol': rol,
                    'usuario': usuario.strip(),
                    'fecha': fecha.strip(),
                    'texto': texto.strip()
                })
        
        return Response({
            'success': True,
            'tercero_id': str(tercero.id),
            'comments': {
                'observaciones': observaciones_parsed,
                'notas_internas': notas_internas_parsed,
                'comentarios_comercial': tercero.observaciones_comercial or '',
                'comentarios_aprobacion': tercero.comentarios_aprobacion or '',
                'observaciones_raw': tercero.observaciones or '',
                'notas_internas_raw': tercero.notas_internas or ''
            },
            'metadata': {
                'total_observaciones': len(observaciones_parsed),
                'total_notas_internas': len(notas_internas_parsed),
                'tiene_comentarios_comercial': bool(tercero.observaciones_comercial),
                'tiene_comentarios_aprobacion': bool(tercero.comentarios_aprobacion)
            }
        })

    def notify_administrators_of_comment(self, tercero, comercial_user, comentario):
        """
        Notifica a los administradores cuando un comercial agrega un comentario de aprobación
        """
        try:
            from notifications.models import Notificacion
            
            # Obtener administradores activos
            admin_users = User.objects.filter(role='administrador', is_active=True)
            
            for admin in admin_users:
                Notificacion.objects.create(
                    usuario=admin,
                    titulo="Nuevo comentario de comercial",
                    mensaje=f"El comercial {comercial_user.get_full_name()} ha agregado un comentario al tercero {tercero.numero_documento} - {tercero.nombres}: {comentario[:100]}{'...' if len(comentario) > 100 else ''}",
                    tipo='tercero_asignado',
                    prioridad='media',
                    tercero_relacionado=tercero,
                    usuario_relacionado=comercial_user,
                    datos_extra={
                        'comercial_id': str(comercial_user.id),
                        'comercial_nombre': comercial_user.get_full_name(),
                        'tercero_id': str(tercero.id),
                        'tercero_numero_documento': tercero.numero_documento,
                        'comment_type': 'aprobacion'
                    }
                )
        except Exception as e:
            logger.error(f"Error creando notificación: {str(e)}")

    def notify_administrators_of_approval(self, tercero, comercial_user):
        """
        Notifica a los administradores cuando un comercial aprueba un tercero
        """
        try:
            from notifications.models import Notificacion
            
            # Obtener administradores activos
            admin_users = User.objects.filter(role='administrador', is_active=True)
            
            for admin in admin_users:
                Notificacion.objects.create(
                    usuario=admin,
                    titulo="Tercero aprobado por comercial",
                    mensaje=f"El comercial {comercial_user.get_full_name()} ha aprobado completamente el tercero {tercero.numero_documento} - {tercero.nombres}. El tercero está ahora aprobado y listo para gestión.",
                    tipo='tercero_aprobado',
                    prioridad='alta',
                    tercero_relacionado=tercero,
                    usuario_relacionado=comercial_user,
                    datos_extra={
                        'comercial_id': str(comercial_user.id),
                        'comercial_nombre': comercial_user.get_full_name(),
                        'tercero_id': str(tercero.id),
                        'tercero_numero_documento': tercero.numero_documento,
                        'estado_anterior': 'pendiente',
                        'estado_nuevo': tercero.estado_aprobacion,
                        'accion': 'aprobacion_final_comercial'
                    }
                )
                logger.info(f"Notificación de aprobación enviada a administrador: {admin.get_full_name()}")
                
        except Exception as e:
            logger.error(f"Error creando notificación de aprobación: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def pendientes_administrador(self, request):
        """
        Ver terceros aprobados por comerciales para gestión del administrador
        GET /api/terceros/pendientes_administrador/
        """
        # Solo administradores
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden ver terceros aprobados'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            estado_aprobacion='aprobado_final',
            asignado_administrador=request.user
        ).order_by('-fecha_aprobacion_comercial')
        
        terceros_data = []
        for tercero in terceros:
            terceros_data.append({
                'id': str(tercero.id),
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'tipo_persona': tercero.get_tipo_persona_display(),
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name(),
                'fecha_aprobacion_comercial': tercero.fecha_aprobacion_comercial,
                'email': tercero.email,
                'telefono': tercero.telefono
            })
        
        return Response({
            'success': True,
            'terceros': terceros_data,
            'total': len(terceros_data)
        })

    @action(detail=False, methods=['get'])
    def terceros_aprobados(self, request):
        """
        Ver todos los terceros aprobados por comerciales para administradores
        GET /api/terceros/terceros_aprobados/
        """
        # Solo administradores
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden ver terceros aprobados'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            estado_aprobacion='aprobado_final'
        ).order_by('-fecha_aprobacion_comercial')
        
        terceros_data = []
        for tercero in terceros:
            terceros_data.append({
                'id': str(tercero.id),
                'nombres': tercero.nombres,
                'apellidos': tercero.apellidos,
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'tipo_persona': tercero.get_tipo_persona_display(),
                'estado': 'Aprobado Final',
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name() if tercero.aprobado_por_comercial else None,
                'fecha_aprobacion_comercial': tercero.fecha_aprobacion_comercial,
                'fecha_aprobacion_final': tercero.fecha_aprobacion,
                'asignado_administrador': tercero.asignado_administrador.get_full_name() if tercero.asignado_administrador else None,
                'email': tercero.email,
                'telefono': tercero.telefono,
                'comentarios_aprobacion': tercero.comentarios_aprobacion,
                'observaciones_comercial': tercero.observaciones_comercial
            })
        
        return Response({
            'success': True,
            'terceros_aprobados': terceros_data,
            'total': len(terceros_data),
            'mensaje': 'Terceros aprobados por comerciales - listos para gestión'
        })
    
    @action(detail=True, methods=['post'])
    def asignar_a_procesos_admin(self, request, pk=None):
        """
        Administrador asigna tercero a usuario de procesos
        POST /api/terceros/{id}/asignar_a_procesos_admin/
        Body: {"usuario_procesos_id": "uuid"}
        """
        tercero = self.get_object()
        
        # Solo administradores
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden asignar a procesos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        usuario_procesos_id = request.data.get('usuario_procesos_id')
        if not usuario_procesos_id:
            return Response({
                'success': False,
                'error': 'El ID del usuario de procesos es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            usuario_procesos = User.objects.get(id=usuario_procesos_id, role='procesos', is_active=True)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Usuario de procesos no encontrado o inactivo'
            }, status=status.HTTP_404_NOT_FOUND)
        
        resultado = tercero.asignar_a_procesos_por_admin(request.user, usuario_procesos)
        
        if resultado:
            return Response({
                'success': True,
                'message': f'Tercero asignado exitosamente a {usuario_procesos.get_full_name()}',
                'tercero': {
                    'id': str(tercero.id),
                    'estado': tercero.get_estado_aprobacion_display(),
                    'asignado_a_procesos': usuario_procesos.get_full_name(),
                    'fecha_asignacion': tercero.fecha_asignacion_procesos
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Error al asignar tercero a procesos'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def mis_asignaciones_procesos(self, request):
        """
        Ver terceros asignados al usuario de procesos actual
        GET /api/terceros/mis_asignaciones_procesos/
        """
        # Solo usuarios de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden ver sus asignaciones'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            asignado_a_procesos=request.user,
            estado_aprobacion='asignado_procesos'
        ).order_by('-fecha_asignacion_procesos')
        
        terceros_data = []
        for tercero in terceros:
            terceros_data.append({
                'id': str(tercero.id),
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'tipo_persona': tercero.get_tipo_persona_display(),
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name(),
                'fecha_asignacion': tercero.fecha_asignacion_procesos,
                'email': tercero.email,
                'telefono': tercero.telefono
            })
        
        return Response({
            'success': True,
            'terceros': terceros_data,
            'total': len(terceros_data)
        })
    
    @action(detail=True, methods=['post'])
    def aprobar_procesos(self, request, pk=None):
        """
        Usuario de procesos aprueba tercero definitivamente
        POST /api/terceros/{id}/aprobar_procesos/
        """
        tercero = self.get_object()
        
        # Solo usuarios de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden aprobar terceros'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar que esté asignado al usuario
        if tercero.asignado_a_procesos != request.user:
            return Response({
                'success': False,
                'error': 'Solo puedes aprobar terceros asignados a ti'
            }, status=status.HTTP_403_FORBIDDEN)
        
        resultado = tercero.aprobar_por_procesos(request.user)
        
        if resultado:
            return Response({
                'success': True,
                'message': 'Tercero aprobado definitivamente',
                'tercero': {
                    'id': str(tercero.id),
                    'estado': tercero.get_estado_aprobacion_display(),
                    'aprobado_por_procesos': tercero.aprobado_por_procesos.get_full_name(),
                    'fecha_aprobacion_final': tercero.fecha_aprobacion
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Error al aprobar tercero'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def enviar_a_cumplimiento(self, request, pk=None):
        """
        Usuario de procesos envía tercero a cumplimiento
        POST /api/terceros/{id}/enviar_a_cumplimiento/
        """
        tercero = self.get_object()
        
        # Solo usuarios de procesos
        if not hasattr(request.user, 'role') or request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden enviar a cumplimiento'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar que esté asignado al usuario
        if tercero.asignado_a_procesos != request.user:
            return Response({
                'success': False,
                'error': 'Solo puedes gestionar terceros asignados a ti'
            }, status=status.HTTP_403_FORBIDDEN)
        
        resultado = tercero.enviar_a_cumplimiento(request.user)
        
        if resultado:
            return Response({
                'success': True,
                'message': f'Tercero enviado a cumplimiento: {tercero.asignado_cumplimiento.get_full_name()}',
                'tercero': {
                    'id': str(tercero.id),
                    'estado': tercero.get_estado_aprobacion_display(),
                    'asignado_cumplimiento': tercero.asignado_cumplimiento.get_full_name(),
                    'fecha_asignacion_cumplimiento': tercero.fecha_asignacion_cumplimiento
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Error al enviar tercero a cumplimiento'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def mis_asignaciones_cumplimiento(self, request):
        """
        Ver terceros asignados al oficial de cumplimiento actual
        GET /api/terceros/mis_asignaciones_cumplimiento/
        """
        # Solo oficiales de cumplimiento
        if not hasattr(request.user, 'role') or request.user.role != 'oficial_cumplimiento':
            return Response({
                'success': False,
                'error': 'Solo oficiales de cumplimiento pueden ver sus asignaciones'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            asignado_cumplimiento=request.user,
            estado_aprobacion='enviado_cumplimiento'
        ).order_by('-fecha_asignacion_cumplimiento')
        
        terceros_data = []
        for tercero in terceros:
            terceros_data.append({
                'id': str(tercero.id),
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'tipo_persona': tercero.get_tipo_persona_display(),
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name(),
                'asignado_por_procesos': tercero.asignado_a_procesos.get_full_name(),
                'fecha_asignacion': tercero.fecha_asignacion_cumplimiento,
                'email': tercero.email,
                'telefono': tercero.telefono
            })
        
        return Response({
            'success': True,
            'terceros': terceros_data,
            'total': len(terceros_data)
        })
    
    @action(detail=True, methods=['post'])
    def aprobar_cumplimiento(self, request, pk=None):
        """
        Oficial de cumplimiento aprueba tercero definitivamente
        POST /api/terceros/{id}/aprobar_cumplimiento/
        """
        tercero = self.get_object()
        
        # Solo oficiales de cumplimiento
        if not hasattr(request.user, 'role') or request.user.role != 'oficial_cumplimiento':
            return Response({
                'success': False,
                'error': 'Solo oficiales de cumplimiento pueden aprobar terceros'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar que esté asignado al usuario
        if tercero.asignado_cumplimiento != request.user:
            return Response({
                'success': False,
                'error': 'Solo puedes aprobar terceros asignados a ti'
            }, status=status.HTTP_403_FORBIDDEN)
        
        resultado = tercero.aprobar_por_cumplimiento(request.user)
        
        if resultado:
            return Response({
                'success': True,
                'message': 'Tercero aprobado definitivamente por cumplimiento',
                'tercero': {
                    'id': str(tercero.id),
                    'estado': tercero.get_estado_aprobacion_display(),
                    'fecha_aprobacion_final': tercero.fecha_aprobacion
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Error al aprobar tercero'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def asignar_a_usuario(self, request, pk=None):
        """
        Asignar tercero a cualquier usuario (para administradores)
        POST /api/terceros/{id}/asignar_a_usuario/
        Body: {"usuario_id": "uuid", "tipo_asignacion": "comercial|procesos|cumplimiento"}
        """
        tercero = self.get_object()
        
        # Solo administradores pueden asignar a cualquier usuario
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden asignar terceros a usuarios'
            }, status=status.HTTP_403_FORBIDDEN)
        
        usuario_id = request.data.get('usuario_id')
        tipo_asignacion = request.data.get('tipo_asignacion', 'comercial')
        
        if not usuario_id:
            return Response({
                'success': False,
                'error': 'El ID del usuario es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            usuario = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Usuario no encontrado o inactivo'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Asignar según el tipo
        if tipo_asignacion == 'comercial':
            tercero.asignado_a = usuario
            tercero.save()
            mensaje = f'Tercero asignado al comercial: {usuario.get_full_name()}'
        elif tipo_asignacion == 'procesos':
            tercero.asignado_a_procesos = usuario
            tercero.fecha_asignacion_procesos = timezone.now()
            if tercero.estado_aprobacion in ['pendiente', 'pendiente_administrador']:
                tercero.estado_aprobacion = 'asignado_procesos'
            tercero.save()
            mensaje = f'Tercero asignado a procesos: {usuario.get_full_name()}'
        elif tipo_asignacion == 'cumplimiento':
            tercero.asignado_cumplimiento = usuario
            tercero.fecha_asignacion_cumplimiento = timezone.now()
            tercero.estado_aprobacion = 'enviado_cumplimiento'
            tercero.save()
            mensaje = f'Tercero asignado a cumplimiento: {usuario.get_full_name()}'
        else:
            return Response({
                'success': False,
                'error': 'Tipo de asignación no válido. Use: comercial, procesos o cumplimiento'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': mensaje,
            'tercero': {
                'id': str(tercero.id),
                'estado': tercero.get_estado_aprobacion_display(),
                'asignado_a': usuario.get_full_name(),
                'tipo_asignacion': tipo_asignacion
            }
        })

    # NUEVOS ENDPOINTS PARA EL FLUJO EXTENDIDO
    
    @action(detail=True, methods=['post'])
    def aprobar_comercial(self, request, pk=None):
        """
        Aprueba un tercero en la etapa comercial y lo envía al administrador
        POST /api/terceros/{id}/aprobar_comercial/
        """
        tercero = self.get_object()
        
        # Verificar que el usuario sea comercial
        if request.user.role != 'comercial':
            return Response({
                'error': 'Solo usuarios comerciales pueden aprobar en esta etapa'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar que el tercero esté en estado correcto
        if tercero.estado_aprobacion not in ['pendiente', 'en_revision']:
            return Response({
                'error': f'El tercero está en estado {tercero.get_estado_aprobacion_display()}, no se puede aprobar'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Aprobar por comercial
        if tercero.aprobar_por_comercial(request.user):
            return Response({
                'success': True,
                'message': 'Tercero aprobado y enviado al administrador',
                'estado_actual': tercero.get_estado_aprobacion_display(),
                'aprobado_por': tercero.aprobado_por_comercial.get_full_name(),
                'fecha_aprobacion': tercero.fecha_aprobacion_comercial
            })
        else:
            return Response({
                'error': 'Error al aprobar el tercero'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def pendientes_administrador(self, request):
        """
        Lista terceros pendientes de asignación por administrador
        GET /api/terceros/pendientes_administrador/
        """
        if request.user.role != 'administrador':
            return Response({
                'error': 'Solo administradores pueden ver esta lista'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            estado_aprobacion='pendiente_administrador'
        ).select_related('aprobado_por_comercial')
        
        data = []
        for tercero in terceros:
            data.append({
                'id': str(tercero.id),
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name() if tercero.aprobado_por_comercial else None,
                'fecha_aprobacion_comercial': tercero.fecha_aprobacion_comercial,
                'fecha_registro': tercero.created_at
            })
        
        return Response({
            'terceros_pendientes': data,
            'total': len(data)
        })
    
    @action(detail=True, methods=['post'])
    def asignar_a_procesos_admin(self, request, pk=None):
        """
        Permite al administrador asignar un tercero a un usuario específico de procesos
        POST /api/terceros/{id}/asignar_a_procesos_admin/
        Body: {"usuario_procesos_id": "uuid"}
        """
        tercero = self.get_object()
        
        if request.user.role != 'administrador':
            return Response({
                'error': 'Solo administradores pueden asignar a procesos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        usuario_procesos_id = request.data.get('usuario_procesos_id')
        if not usuario_procesos_id:
            return Response({
                'error': 'Debe especificar usuario_procesos_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            usuario_procesos = User.objects.get(id=usuario_procesos_id, role='procesos', is_active=True)
        except User.DoesNotExist:
            return Response({
                'error': 'Usuario de procesos no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if tercero.asignar_a_procesos_por_admin(request.user, usuario_procesos):
            return Response({
                'success': True,
                'message': 'Tercero asignado a procesos correctamente',
                'asignado_a': usuario_procesos.get_full_name(),
                'estado_actual': tercero.get_estado_aprobacion_display()
            })
        else:
            return Response({
                'error': 'Error al asignar a procesos'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def mis_asignaciones_procesos(self, request):
        """
        Lista terceros asignados al usuario de procesos logueado
        GET /api/terceros/mis_asignaciones_procesos/
        """
        if request.user.role != 'procesos':
            return Response({
                'error': 'Solo usuarios de procesos pueden ver esta lista'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            asignado_a_procesos=request.user,
            estado_aprobacion='asignado_procesos'
        ).select_related('aprobado_por_comercial', 'asignado_administrador')
        
        data = []
        for tercero in terceros:
            data.append({
                'id': str(tercero.id),
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name() if tercero.aprobado_por_comercial else None,
                'asignado_por_admin': tercero.asignado_administrador.get_full_name() if tercero.asignado_administrador else None,
                'fecha_asignacion': tercero.fecha_asignacion_procesos,
                'fecha_registro': tercero.created_at
            })
        
        return Response({
            'terceros_asignados': data,
            'total': len(data)
        })
    
    @action(detail=True, methods=['post'])
    def aprobar_procesos(self, request, pk=None):
        """
        Aprueba un tercero en la etapa de procesos - aprobación final
        POST /api/terceros/{id}/aprobar_procesos/
        """
        tercero = self.get_object()
        
        if request.user.role != 'procesos':
            return Response({
                'error': 'Solo usuarios de procesos pueden aprobar en esta etapa'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if tercero.asignado_a_procesos != request.user:
            return Response({
                'error': 'Este tercero no está asignado a usted'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if tercero.aprobar_por_procesos(request.user):
            return Response({
                'success': True,
                'message': 'Tercero aprobado definitivamente',
                'estado_final': tercero.get_estado_aprobacion_display(),
                'fecha_aprobacion_final': tercero.fecha_aprobacion
            })
        else:
            return Response({
                'error': 'Error al aprobar el tercero'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def enviar_a_cumplimiento(self, request, pk=None):
        """
        Envía un tercero al oficial de cumplimiento para revisión
        POST /api/terceros/{id}/enviar_a_cumplimiento/
        Body: {"motivo": "descripción del motivo"} (opcional)
        """
        tercero = self.get_object()
        
        if request.user.role != 'procesos':
            return Response({
                'error': 'Solo usuarios de procesos pueden enviar a cumplimiento'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if tercero.asignado_a_procesos != request.user:
            return Response({
                'error': 'Este tercero no está asignado a usted'
            }, status=status.HTTP_403_FORBIDDEN)
        
        motivo = request.data.get('motivo', 'Requiere revisión de cumplimiento')
        
        if tercero.enviar_a_cumplimiento(request.user):
            # Agregar observación sobre el envío a cumplimiento
            observacion_anterior = tercero.observaciones or ""
            tercero.observaciones = f"{observacion_anterior}\n[{timezone.now()}] Enviado a cumplimiento por {request.user.get_full_name()}: {motivo}".strip()
            tercero.save()
            
            return Response({
                'success': True,
                'message': 'Tercero enviado al área de cumplimiento',
                'asignado_cumplimiento': tercero.asignado_cumplimiento.get_full_name() if tercero.asignado_cumplimiento else None,
                'estado_actual': tercero.get_estado_aprobacion_display()
            })
        else:
            return Response({
                'error': 'Error al enviar a cumplimiento'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def mis_asignaciones_cumplimiento(self, request):
        """
        Lista terceros asignados al oficial de cumplimiento logueado
        GET /api/terceros/mis_asignaciones_cumplimiento/
        """
        if request.user.role != 'oficial_cumplimiento':
            return Response({
                'error': 'Solo oficiales de cumplimiento pueden ver esta lista'
            }, status=status.HTTP_403_FORBIDDEN)
        
        terceros = Tercero.objects.filter(
            asignado_cumplimiento=request.user,
            estado_aprobacion='enviado_cumplimiento'
        ).select_related('aprobado_por_comercial', 'asignado_a_procesos')
        
        data = []
        for tercero in terceros:
            data.append({
                'id': str(tercero.id),
                'razon_social': tercero.razon_social,
                'numero_documento': tercero.numero_documento,
                'aprobado_por_comercial': tercero.aprobado_por_comercial.get_full_name() if tercero.aprobado_por_comercial else None,
                'enviado_por_procesos': tercero.asignado_a_procesos.get_full_name() if tercero.asignado_a_procesos else None,
                'fecha_asignacion': tercero.fecha_asignacion_cumplimiento,
                'observaciones': tercero.observaciones
            })
        
        return Response({
            'terceros_asignados': data,
            'total': len(data)
        })
    
    @action(detail=True, methods=['post'])
    def aprobar_cumplimiento(self, request, pk=None):
        """
        Aprueba un tercero desde el área de cumplimiento
        POST /api/terceros/{id}/aprobar_cumplimiento/
        Body: {"observaciones": "comentarios finales"} (opcional)
        """
        tercero = self.get_object()
        
        if request.user.role != 'oficial_cumplimiento':
            return Response({
                'error': 'Solo oficiales de cumplimiento pueden aprobar en esta etapa'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if tercero.asignado_cumplimiento != request.user:
            return Response({
                'error': 'Este tercero no está asignado a usted'
            }, status=status.HTTP_403_FORBIDDEN)
        
        observaciones_finales = request.data.get('observaciones', '')
        
        if tercero.aprobar_por_cumplimiento(request.user):
            # Agregar observación de aprobación final
            if observaciones_finales:
                observacion_anterior = tercero.observaciones or ""
                tercero.observaciones = f"{observacion_anterior}\n[{timezone.now()}] Aprobado por cumplimiento ({request.user.get_full_name()}): {observaciones_finales}".strip()
                tercero.save()
            
            return Response({
                'success': True,
                'message': 'Tercero aprobado definitivamente por cumplimiento',
                'estado_final': tercero.get_estado_aprobacion_display(),
                'fecha_aprobacion_final': tercero.fecha_aprobacion
            })
        else:
            return Response({
                'error': 'Error al aprobar el tercero'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def historial_completo(self, request, pk=None):
        """
        Obtiene el historial completo del tercero con todas las acciones
        GET /api/terceros/{id}/historial_completo/
        """
        tercero = self.get_object()
        
        # Verificar permisos
        if not request.user.is_authenticated:
            return Response({
                'error': 'Autenticación requerida'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            historial = tercero.obtener_historial_completo()
            from .serializers import HistorialTerceroSerializer
            historial_serializado = HistorialTerceroSerializer(historial, many=True).data
            
            return Response({
                'success': True,
                'tercero_id': str(tercero.id),
                'tercero_nombre': str(tercero),
                'total_acciones': historial.count(),
                'historial': historial_serializado
            })
        except Exception as e:
            return Response({
                'error': f'Error al obtener historial: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def resumen_workflow(self, request, pk=None):
        """
        Obtiene un resumen del workflow del tercero con información de auditoría
        GET /api/terceros/{id}/resumen_workflow/
        """
        tercero = self.get_object()
        
        # Verificar permisos
        if not request.user.is_authenticated:
            return Response({
                'error': 'Autenticación requerida'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            resumen = tercero.generar_resumen_workflow()
            
            # Agregar información adicional de auditoría
            resumen['usuario_creacion'] = {
                'username': tercero.creado_por.username if tercero.creado_por else None,
                'full_name': tercero.creado_por.get_full_name() if tercero.creado_por else None,
                'role': getattr(tercero.creado_por, 'role', None) if tercero.creado_por else None
            }
            
            resumen['usuario_ultima_modificacion'] = {
                'username': tercero.usuario_ultimo_cambio.username if tercero.usuario_ultimo_cambio else None,
                'full_name': tercero.usuario_ultimo_cambio.get_full_name() if tercero.usuario_ultimo_cambio else None,
                'role': getattr(tercero.usuario_ultimo_cambio, 'role', None) if tercero.usuario_ultimo_cambio else None
            }
            
            # Convertir usuarios de las etapas a formato serializable
            for etapa in resumen['etapas_completadas'].values():
                if etapa['aprobado_por']:
                    etapa['aprobado_por'] = {
                        'username': etapa['aprobado_por'].username,
                        'full_name': etapa['aprobado_por'].get_full_name(),
                        'role': getattr(etapa['aprobado_por'], 'role', None)
                    }
            
            return Response({
                'success': True,
                'tercero_id': str(tercero.id),
                'tercero_nombre': str(tercero),
                'resumen': resumen
            })
        except Exception as e:
            return Response({
                'error': f'Error al generar resumen: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def auditoria_completa(self, request, pk=None):
        """
        Obtiene información completa de auditoría: historial, comentarios, asignaciones
        GET /api/terceros/{id}/auditoria_completa/
        
        Respuesta:
        {
            "success": true,
            "tercero": {...},
            "asignacion_actual": {...},
            "comentarios_estructurados": {...},
            "historial_cambios": [...],
            "timeline": [...]
        }
        """
        tercero = self.get_object()
        
        # Verificar permisos
        if not request.user.is_authenticated:
            return Response({
                'error': 'Autenticación requerida'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        user_role = getattr(request.user, 'role', None)
        
        # Verificar permisos por rol
        if user_role == 'comercial':
            if tercero.asignado_a != request.user:
                return Response({
                    'success': False,
                    'error': 'Solo puedes ver auditoría de terceros asignados a ti'
                }, status=status.HTTP_403_FORBIDDEN)
        elif user_role not in ['procesos', 'administrador', 'oficial_cumplimiento']:
            return Response({
                'success': False,
                'error': 'No tienes permisos para ver información de auditoría'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # 1. Información básica del tercero
            tercero_info = {
                'id': str(tercero.id),
                'nombres': tercero.nombres,
                'apellidos': tercero.apellidos,
                'numero_documento': tercero.numero_documento,
                'estado_actual': tercero.estado_aprobacion,
                'estado_display': tercero.get_estado_aprobacion_display(),
                'fecha_creacion': tercero.created_at,
                'usuario_creacion': tercero.creado_por.get_full_name() if tercero.creado_por else None,
                'fecha_ultimo_cambio': tercero.fecha_ultimo_cambio_estado,
                'usuario_ultimo_cambio': tercero.usuario_ultimo_cambio.get_full_name() if tercero.usuario_ultimo_cambio else None,
            }
            
            # 2. Asignación actual
            asignacion_actual = None
            if tercero.asignado_a:
                asignacion_actual = {
                    'usuario': tercero.asignado_a.username,
                    'nombre_completo': tercero.asignado_a.get_full_name(),
                    'email': tercero.asignado_a.email,
                    'role': getattr(tercero.asignado_a, 'role', None),
                    'role_display': getattr(tercero.asignado_a, 'get_role_display', lambda: None)()
                }
            
            # 3. Comentarios estructurados (parsear observaciones y notas)
            import re
            pattern = r'\[(PROCESOS|ADMINISTRADOR|OFICIAL_CUMPLIMIENTO|COMERCIAL) - ([^-]+) - ([^\]]+)\]: (.*?)(?=\n\[|$)'
            
            observaciones_parsed = []
            if tercero.observaciones:
                matches = re.findall(pattern, tercero.observaciones, re.DOTALL)
                for match in matches:
                    rol, usuario, fecha, texto = match
                    observaciones_parsed.append({
                        'tipo': 'observacion',
                        'rol': rol,
                        'usuario': usuario.strip(),
                        'fecha': fecha.strip(),
                        'texto': texto.strip()
                    })
            
            notas_parsed = []
            if tercero.notas_internas:
                matches = re.findall(pattern, tercero.notas_internas, re.DOTALL)
                for match in matches:
                    rol, usuario, fecha, texto = match
                    notas_parsed.append({
                        'tipo': 'nota_interna',
                        'rol': rol,
                        'usuario': usuario.strip(),
                        'fecha': fecha.strip(),
                        'texto': texto.strip()
                    })
            
            comentarios_estructurados = {
                'observaciones': observaciones_parsed,
                'notas_internas': notas_parsed,
                'comentarios_comercial': tercero.observaciones_comercial or '',
                'comentarios_aprobacion': tercero.comentarios_aprobacion or '',
                'total_comentarios': len(observaciones_parsed) + len(notas_parsed)
            }
            
            # 4. Historial de cambios
            historial_cambios = []
            historial = tercero.obtener_historial_completo()
            for registro in historial:
                historial_cambios.append({
                    'fecha': registro.fecha_accion,
                    'accion': registro.get_accion_display(),
                    'usuario': registro.usuario.username if registro.usuario else None,
                    'usuario_nombre': registro.usuario.get_full_name() if registro.usuario else None,
                    'estado_anterior': registro.estado_anterior,
                    'estado_nuevo': registro.estado_nuevo,
                    'observaciones': registro.observaciones
                })
            
            # 5. Timeline combinado (comentarios + historial ordenado por fecha)
            timeline = []
            
            # Agregar comentarios al timeline
            for obs in observaciones_parsed:
                try:
                    from datetime import datetime
                    fecha_dt = datetime.strptime(obs['fecha'], '%Y-%m-%d %H:%M:%S')
                    timeline.append({
                        'fecha': fecha_dt,
                        'tipo': 'comentario',
                        'subtipo': 'observacion',
                        'usuario': obs['usuario'],
                        'rol': obs['rol'],
                        'descripcion': f"Comentario: {obs['texto'][:100]}..."
                    })
                except:
                    pass
            
            for nota in notas_parsed:
                try:
                    from datetime import datetime
                    fecha_dt = datetime.strptime(nota['fecha'], '%Y-%m-%d %H:%M:%S')
                    timeline.append({
                        'fecha': fecha_dt,
                        'tipo': 'comentario',
                        'subtipo': 'nota_interna',
                        'usuario': nota['usuario'],
                        'rol': nota['rol'],
                        'descripcion': f"Nota interna: {nota['texto'][:100]}..."
                    })
                except:
                    pass
            
            # Agregar historial al timeline
            for cambio in historial_cambios:
                timeline.append({
                    'fecha': cambio['fecha'],
                    'tipo': 'cambio_estado',
                    'subtipo': cambio['accion'],
                    'usuario': cambio['usuario'],
                    'descripcion': f"{cambio['accion']}: {cambio['estado_anterior']} → {cambio['estado_nuevo']}"
                })
            
            # Ordenar timeline por fecha (más reciente primero)
            timeline.sort(key=lambda x: x['fecha'], reverse=True)
            
            # Convertir fechas a strings para JSON
            for item in timeline:
                item['fecha'] = item['fecha'].strftime('%Y-%m-%d %H:%M:%S')
            
            # 6. Información de auditoría adicional
            auditoria_adicional = {
                'usuario_creacion': {
                    'username': tercero.creado_por.username if tercero.creado_por else None,
                    'nombre_completo': tercero.creado_por.get_full_name() if tercero.creado_por else None,
                    'role': getattr(tercero.creado_por, 'role', None) if tercero.creado_por else None
                },
                'usuario_ultimo_cambio': {
                    'username': tercero.usuario_ultimo_cambio.username if tercero.usuario_ultimo_cambio else None,
                    'nombre_completo': tercero.usuario_ultimo_cambio.get_full_name() if tercero.usuario_ultimo_cambio else None,
                    'role': getattr(tercero.usuario_ultimo_cambio, 'role', None) if tercero.usuario_ultimo_cambio else None
                }
            }
            
            return Response({
                'success': True,
                'tercero': tercero_info,
                'asignacion_actual': asignacion_actual,
                'comentarios_estructurados': comentarios_estructurados,
                'historial_cambios': historial_cambios,
                'timeline': timeline[:20],  # Limitar a últimos 20 eventos
                'auditoria': auditoria_adicional,
                'metadata': {
                    'total_eventos_timeline': len(timeline),
                    'total_comentarios': comentarios_estructurados['total_comentarios'],
                    'total_cambios_estado': len(historial_cambios),
                    'consultado_por': request.user.username,
                    'fecha_consulta': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al obtener auditoría completa: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def auditoria_completa_v2(self, request, pk=None):
        """
        Versión simplificada y funcional del endpoint de auditoría completa
        GET /api/terceros/{id}/auditoria_completa_v2/
        """
        try:
            tercero = self.get_object()
            
            # Verificar permisos
            if not request.user.is_authenticated:
                return Response({
                    'error': 'Autenticación requerida'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # 1. Información básica del tercero
            tercero_info = {
                'id': str(tercero.id),
                'nombres': tercero.nombres,
                'apellidos': tercero.apellidos or '',
                'razon_social': tercero.razon_social or '',
                'numero_documento': tercero.numero_documento,
                'tipo_documento': tercero.tipo_documento,
                'estado_actual': tercero.estado_aprobacion,
                'estado_display': tercero.get_estado_aprobacion_display(),
                'fecha_creacion': tercero.created_at.strftime('%Y-%m-%d %H:%M:%S') if tercero.created_at else None,
                'usuario_creacion': tercero.creado_por.get_full_name() if tercero.creado_por else 'No especificado',
                'fecha_ultimo_cambio': tercero.fecha_ultimo_cambio_estado.strftime('%Y-%m-%d %H:%M:%S') if tercero.fecha_ultimo_cambio_estado else None,
                'usuario_ultimo_cambio': tercero.usuario_ultimo_cambio.get_full_name() if tercero.usuario_ultimo_cambio else 'No especificado',
            }
            
            # 2. Asignación actual
            asignacion_actual = None
            if tercero.asignado_a:
                asignacion_actual = {
                    'usuario': tercero.asignado_a.username,
                    'nombre_completo': tercero.asignado_a.get_full_name(),
                    'email': tercero.asignado_a.email,
                    'role': getattr(tercero.asignado_a, 'role', 'No especificado'),
                    'fecha_asignacion': tercero.fecha_asignacion_actual.strftime('%Y-%m-%d %H:%M:%S') if tercero.fecha_asignacion_actual else None
                }
            
            # 3. Comentarios estructurados
            import re
            pattern = r'\[(PROCESOS|ADMINISTRADOR|OFICIAL_CUMPLIMIENTO|COMERCIAL) - ([^-]+) - ([^\]]+)\]: (.*?)(?=\n\[|$)'
            
            observaciones_parsed = []
            if tercero.observaciones:
                try:
                    matches = re.findall(pattern, tercero.observaciones, re.DOTALL)
                    for match in matches:
                        rol, usuario, fecha, texto = match
                        observaciones_parsed.append({
                            'tipo': 'observacion',
                            'rol': rol,
                            'usuario': usuario.strip(),
                            'fecha': fecha.strip(),
                            'texto': texto.strip()
                        })
                except Exception as e:
                    print(f"Error parseando observaciones: {e}")
            
            notas_parsed = []
            if tercero.notas_internas:
                try:
                    matches = re.findall(pattern, tercero.notas_internas, re.DOTALL)
                    for match in matches:
                        rol, usuario, fecha, texto = match
                        notas_parsed.append({
                            'tipo': 'nota_interna',
                            'rol': rol,
                            'usuario': usuario.strip(),
                            'fecha': fecha.strip(),
                            'texto': texto.strip()
                        })
                except Exception as e:
                    print(f"Error parseando notas internas: {e}")
            
            comentarios_estructurados = {
                'observaciones': observaciones_parsed,
                'notas_internas': notas_parsed,
                'comentarios_comercial': tercero.observaciones_comercial or '',
                'comentarios_aprobacion': tercero.comentarios_aprobacion or '',
                'total_comentarios': len(observaciones_parsed) + len(notas_parsed)
            }
            
            # 4. Historial de cambios
            historial_cambios = []
            try:
                from terceros.models import HistorialTercero
                historial = HistorialTercero.objects.filter(tercero=tercero).order_by('-fecha_accion')[:20]
                for registro in historial:
                    historial_cambios.append({
                        'fecha': registro.fecha_accion.strftime('%Y-%m-%d %H:%M:%S'),
                        'accion': registro.accion,
                        'estado_anterior': registro.estado_anterior,
                        'estado_nuevo': registro.estado_nuevo,
                        'usuario': registro.usuario.get_full_name() if registro.usuario else 'No especificado',
                        'observaciones': registro.observaciones or ''
                    })
            except Exception as e:
                print(f"Error obteniendo historial: {e}")
            
            # 5. Timeline simplificado
            timeline = []
            
            # Agregar historial al timeline
            for cambio in historial_cambios:
                timeline.append({
                    'fecha': cambio['fecha'],
                    'tipo': 'cambio_estado',
                    'usuario': cambio['usuario'],
                    'descripcion': f"Acción: {cambio['accion']} - {cambio['estado_anterior']} → {cambio['estado_nuevo']}"
                })
            
            # Agregar comentarios al timeline
            for obs in observaciones_parsed:
                timeline.append({
                    'fecha': obs['fecha'],
                    'tipo': 'comentario',
                    'usuario': obs['usuario'],
                    'descripcion': f"Observación ({obs['rol']}): {obs['texto'][:100]}..."
                })
            
            for nota in notas_parsed:
                timeline.append({
                    'fecha': nota['fecha'],
                    'tipo': 'nota_interna',
                    'usuario': nota['usuario'],
                    'descripcion': f"Nota interna ({nota['rol']}): {nota['texto'][:100]}..."
                })
            
            # Ordenar timeline por fecha (más reciente primero)
            timeline.sort(key=lambda x: x['fecha'], reverse=True)
            
            # 6. Metadata
            from django.utils import timezone
            metadata = {
                'total_eventos_timeline': len(timeline),
                'total_historial_cambios': len(historial_cambios),
                'total_comentarios': len(observaciones_parsed) + len(notas_parsed),
                'consultado_por': request.user.get_full_name(),
                'fecha_consulta': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'version_api': '2.0'
            }
            
            return Response({
                'success': True,
                'tercero': tercero_info,
                'asignacion_actual': asignacion_actual,
                'comentarios_estructurados': comentarios_estructurados,
                'historial_cambios': historial_cambios,
                'timeline': timeline,
                'metadata': metadata
            })
            
        except Exception as e:
            import traceback
            print(f"Error en auditoria_completa_v2: {str(e)}")
            traceback.print_exc()
            return Response({
                'error': f'Error al obtener auditoría completa: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentoTerceroViewSet(viewsets.ModelViewSet):
    queryset = DocumentoTercero.objects.all().order_by('-fecha_subida')  # Agregar ordenamiento
    serializer_class = DocumentoTerceroSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        tercero_id = self.request.query_params.get('tercero')
        if tercero_id:
            queryset = queryset.filter(tercero_id=tercero_id)
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Crear un documento para un tercero
        Espera 'tercero' (ID), 'tipo_documento' (ID) y 'archivo' en el FormData
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_documentos_tercero(request, tercero_id):
    """
    Listar documentos de un tercero específico
    GET /api/terceros/{tercero_id}/documentos/
    """
    try:
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Lista de tipos de documentos de Debida Diligencia (para excluir)
        tipos_dd = [
            'debida_diligencia_formulario', 'debida_diligencia_verificacion',
            'debida_diligencia_bienes', 'debida_diligencia_vinculacion',
            'perfil_riesgo_matriz', 'perfil_riesgo_evaluacion',
            'perfil_riesgo_actualizacion', 'perfil_riesgo_calificacion',
            'soporte_referencias', 'soporte_financieros', 'soporte_certificaciones',
            'soporte_licencias', 'evaluacion_informe', 'evaluacion_recomendaciones',
            'evaluacion_mitigacion', 'seguimiento_revision', 'seguimiento_actualizacion',
            'seguimiento_monitoreo', 'debida_diligencia_otro'
        ]
        
        # Obtener SOLO documentos normales del tercero (EXCLUIR Debida Diligencia)
        documentos = DocumentoTercero.objects.filter(
            tercero=tercero,
            es_vigente=True
        ).exclude(
            tipo_documento__in=tipos_dd  # EXCLUIR documentos DD
        ).order_by('-fecha_subida')
        serializer = DocumentoTerceroSerializer(documentos, many=True)
        
        return Response({
            'success': True,
            'tercero_id': str(tercero.id),
            'numero_documento': tercero.numero_documento,
            'documentos': serializer.data,
            'total_documentos': documentos.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listando documentos del tercero {tercero_id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Vista independiente para obtener comerciales disponibles (para el formulario público)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["GET"])
def comerciales_disponibles_publico(request):
    """
    Endpoint público para obtener comerciales disponibles para selección en el formulario
    GET /api/comerciales-disponibles/
    """
    try:
        from django.db.models import Count
        
        comerciales = User.objects.filter(
            role='comercial',
            is_active=True
        ).exclude(
            username__contains='test'  # Excluir usuarios de prueba
        ).annotate(
            num_terceros_asignados=Count('terceros_asignados_comercial')
        ).order_by('num_terceros_asignados')
        
        comerciales_data = []
        for comercial in comerciales:
            comerciales_data.append({
                'id': str(comercial.id),
                'nombre': comercial.get_full_name(),
                'first_name': comercial.first_name,
                'last_name': comercial.last_name,
                'email': comercial.email,
                'username': comercial.username,
                'terceros_asignados': comercial.num_terceros_asignados
            })
        
        return JsonResponse({
            'success': True,
            'comerciales': comerciales_data,
            'total': len(comerciales_data)
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo comerciales disponibles: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def transiciones_disponibles(request):
    """
    Endpoint para obtener todas las transiciones de estado disponibles
    GET /api/terceros/transiciones_disponibles/
    """
    try:
        # Definir transiciones permitidas (mismo mapa que en cambiar_estado)
        transiciones_permitidas = {
            'pendiente': ['en_revision', 'aprobado', 'rechazado'],
            'en_revision': ['aprobado', 'rechazado', 'requiere_ajustes'],
            'requiere_ajustes': ['en_revision', 'pendiente'],
            'aprobado': ['aprobado_final', 'pendiente', 'rechazado'],
            'aprobado_final': ['pendiente', 'rechazado'],
            'rechazado': ['pendiente', 'en_revision']
        }
        
        # Obtener todos los estados posibles
        estados_disponibles = [choice[0] for choice in Tercero.EstadoAprobacion.choices]
        estados_labels = {choice[0]: choice[1] for choice in Tercero.EstadoAprobacion.choices}
        
        return Response({
            'success': True,
            'transiciones': transiciones_permitidas,
            'estados_disponibles': estados_disponibles,
            'estados_labels': estados_labels
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo transiciones disponibles: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@api_view(['POST'])
def cambiar_estado_tercero(request, tercero_id):
    """
    Endpoint independiente para cambiar estado de tercero
    POST /api/terceros/{tercero_id}/cambiar_estado/
    Body: {"estado": "nuevo_estado", "observaciones": "comentarios opcionales"}
    
    Permisos:
    - Administrador: Puede cambiar a cualquier estado
    - Oficial de cumplimiento: Puede cambiar a cualquier estado
    - Procesos: Puede cambiar a cualquier estado
    - Comercial: Solo puede aprobar sus terceros asignados
    """
    try:
        # Verificar autenticación
        if not request.user.is_authenticated:
            return Response({
                'success': False,
                'error': 'Autenticación requerida'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Obtener el tercero
        tercero = Tercero.objects.get(id=tercero_id)
        
        # Verificar permisos por rol
        user_role = getattr(request.user, 'role', None)
        nuevo_estado = request.data.get('estado')
        
        # Administrador, oficial de cumplimiento y procesos: acceso total
        if user_role not in ['administrador', 'oficial_cumplimiento', 'procesos', 'comercial']:
            return Response({
                'success': False,
                'error': f'Rol {user_role} no tiene permisos para cambiar estados'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Para comerciales: solo pueden aprobar terceros asignados a ellos
        if user_role == 'comercial':
            if tercero.asignado_a != request.user:
                return Response({
                    'success': False,
                    'error': 'Solo puedes modificar terceros asignados a ti'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Comerciales solo pueden hacer ciertas transiciones
            transiciones_comercial = ['en_revision', 'aprobado_comercial']
            if nuevo_estado not in transiciones_comercial:
                return Response({
                    'success': False,
                    'error': f'Los comerciales solo pueden cambiar a: {transiciones_comercial}'
                }, status=status.HTTP_403_FORBIDDEN)
        
        observaciones = request.data.get('observaciones', '')
        
        # Mapeo de compatibilidad para frontend (mapear 'aprobado' a 'aprobado_comercial')
        estado_mapping = {
            'aprobado': 'aprobado_comercial',  # Compatibilidad con frontend
            'aprobado_final': 'aprobado_final',
            'pendiente': 'pendiente',
            'en_revision': 'en_revision',
            'rechazado': 'rechazado',
            'requiere_ajustes': 'requiere_ajustes',
            'pendiente_administrador': 'pendiente_administrador',
            'asignado_procesos': 'asignado_procesos',
            'aprobado_procesos': 'aprobado_procesos',
            'enviado_cumplimiento': 'enviado_cumplimiento',
            'aprobado_comercial': 'aprobado_comercial'
        }
        
        # Mapear el estado si es necesario
        nuevo_estado_mapeado = estado_mapping.get(nuevo_estado, nuevo_estado)
        logger.info(f"Estado recibido: {nuevo_estado} -> Estado mapeado: {nuevo_estado_mapeado}")
        
        # Validar que el estado mapeado sea válido
        estados_validos = [choice[0] for choice in Tercero.EstadoAprobacion.choices]
        if nuevo_estado_mapeado not in estados_validos:
            return Response({
                'success': False,
                'error': f'Estado inválido. Estados válidos: {estados_validos}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Usar el estado mapeado para el resto de la lógica
        nuevo_estado = nuevo_estado_mapeado
        
        # Validar transiciones lógicas (administradores pueden saltar validaciones)
        estado_actual = tercero.estado_aprobacion
        transiciones_permitidas = {
            'pendiente': ['en_revision', 'aprobado_comercial', 'rechazado', 'en_curso_comercial', 'en_curso_procesos', 'asignada_procesos', 'asignada_oficial_cumplimiento'],
            'en_revision': ['aprobado_comercial', 'rechazado', 'requiere_ajustes'],
            'en_curso_comercial': ['en_curso_procesos', 'asignada_procesos', 'devuelto_comercial', 'rechazado', 'asignada_oficial_cumplimiento'],
            'en_curso_procesos': ['asignada_oficial_cumplimiento', 'devuelto_comercial', 'aprobado', 'rechazado', 'asignada_procesos'],
            'en_curso_cumplimiento': ['aprobado', 'rechazado', 'devuelto_comercial'],
            'aprobado_comercial': ['pendiente_administrador', 'asignado_procesos', 'rechazado'],
            'pendiente_administrador': ['asignado_procesos', 'rechazado'],
            'asignado_procesos': ['aprobado_procesos', 'enviado_cumplimiento', 'rechazado'],
            'asignada_procesos': ['en_curso_procesos', 'aprobado', 'rechazado'],
            'asignada_oficial_cumplimiento': ['en_curso_cumplimiento', 'aprobado', 'rechazado'],
            'devuelto_comercial': ['en_curso_comercial', 'pendiente', 'rechazado', 'asignada_procesos', 'asignada_oficial_cumplimiento', 'en_curso_procesos'],
            'aprobado_procesos': ['enviado_cumplimiento', 'aprobado_final', 'rechazado'],
            'enviado_cumplimiento': ['aprobado_final', 'rechazado'],
            'aprobado_final': ['rechazado'],  # Solo para casos excepcionales
            'aprobado': ['rechazado', 'en_curso_procesos'],  # PROCESOS puede rechazar aprobados o reasignar para revisión
            'rechazado': ['pendiente', 'en_revision', 'en_curso_comercial', 'asignada_procesos', 'asignada_oficial_cumplimiento'],  # Permitir reactivar y asignar
            'requiere_ajustes': ['en_revision', 'pendiente']
        }
        
        # Los administradores pueden hacer cualquier transición
        if user_role != 'administrador':
            if nuevo_estado not in transiciones_permitidas.get(estado_actual, []):
                return Response({
                    'success': False,
                    'error': f'Transición no permitida de {estado_actual} a {nuevo_estado}',
                    'transiciones_permitidas': transiciones_permitidas.get(estado_actual, [])
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validaciones específicas por estado
        # Aceptar observaciones de múltiples campos para flexibilidad
        observaciones_input = (
            observaciones or 
            request.data.get('comentario', '') or 
            request.data.get('comment', '')
        ).strip()
        
        if nuevo_estado == 'rechazado' and not observaciones_input:
            return Response({
                'success': False,
                'error': 'Las observaciones son obligatorias para rechazar'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar el tercero
        estado_anterior = tercero.estado_aprobacion
        tercero.estado_aprobacion = nuevo_estado
        tercero.fecha_actualizacion = timezone.now()
        
        # Lógica especial para administradores cuando aprueban (restaurar estado comercial)
        if user_role == 'administrador' and nuevo_estado == 'aprobado_comercial':
            # Restaurar la aprobación comercial previa si existe
            if tercero.aprobado_por_comercial and tercero.fecha_aprobacion_comercial:
                # Mantener la aprobación comercial original
                logger.info(f"Administrador restaurando aprobación comercial de {tercero.aprobado_por_comercial.username}")
            else:
                # Si no hay aprobación comercial previa, usar el comercial asignado
                if tercero.asignado_a:
                    tercero.aprobado_por_comercial = tercero.asignado_a
                    tercero.fecha_aprobacion_comercial = timezone.now()
                    logger.info(f"Administrador asignando aprobación comercial a {tercero.asignado_a.username}")
        
        # Actualizar campos de aprobación según el estado y rol
        if nuevo_estado == 'aprobado_comercial' and user_role == 'comercial':
            tercero.aprobado_por_comercial = request.user
            tercero.fecha_aprobacion_comercial = timezone.now()
        elif nuevo_estado == 'aprobado_procesos' and user_role in ['procesos', 'oficial_cumplimiento']:
            tercero.aprobado_por_procesos = request.user
            tercero.fecha_aprobacion_procesos = timezone.now()
        elif nuevo_estado == 'aprobado_final' and user_role in ['procesos', 'oficial_cumplimiento', 'administrador']:
            # Aprobación final puede ser hecha por procesos, cumplimiento o administrador
            tercero.aprobado_por = request.user
        
        # Agregar observaciones con formato estructurado si las hay
        if observaciones_input:
            user_role_display = getattr(request.user, 'role', 'usuario').upper()
            username = request.user.get_full_name() or request.user.username
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Formato: [ROLE - User - Timestamp]: Comment
            comment_formatted = f"[{user_role_display} - {username} - {timestamp}]: {observaciones_input}"
            
            # Agregar al campo de observaciones existente
            if tercero.observaciones:
                tercero.observaciones += f"\n{comment_formatted}"
            else:
                tercero.observaciones = comment_formatted
        
        tercero.save()
        
        # Log del cambio de estado
        logger.info(f"Estado de tercero {tercero_id} cambiado de {estado_anterior} a {nuevo_estado}")
        
        # Serializar y retornar el tercero actualizado
        from .serializers import TerceroCompleteSerializer
        serializer = TerceroCompleteSerializer(tercero)
        
        return Response({
            'success': True,
            'message': f'Estado cambiado exitosamente de {estado_anterior} a {nuevo_estado}',
            'tercero': serializer.data,
            'estado_anterior': estado_anterior,
            'estado_nuevo': nuevo_estado
        }, status=status.HTTP_200_OK)
        
    except Tercero.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tercero no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error cambiando estado de tercero {tercero_id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransicionesDisponiblesView(APIView):
    """
    Vista basada en clase para obtener transiciones disponibles sin autenticación
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        GET /api/terceros/transiciones_disponibles/
        """
        try:
            # Definir transiciones permitidas (mismo mapa que en cambiar_estado)
            transiciones_permitidas = {
                'pendiente': ['en_revision', 'aprobado', 'rechazado'],
                'en_revision': ['aprobado', 'rechazado', 'requiere_ajustes'],
                'requiere_ajustes': ['en_revision', 'pendiente'],
                'aprobado': ['aprobado_final', 'pendiente', 'rechazado'],
                'aprobado_final': ['pendiente', 'rechazado'],
                'rechazado': ['pendiente', 'en_revision']
            }
            
            # Obtener todos los estados posibles
            estados_disponibles = [choice[0] for choice in Tercero.EstadoAprobacion.choices]
            estados_labels = {choice[0]: choice[1] for choice in Tercero.EstadoAprobacion.choices}
            
            return Response({
                'success': True,
                'transiciones': transiciones_permitidas,
                'estados_disponibles': estados_disponibles,
                'estados_labels': estados_labels
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error obteniendo transiciones disponibles: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error interno del servidor',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================
# ENDPOINTS DE SCRAPING STRADATA
# ==============================

@api_view(['POST'])
def ejecutar_scraping_tercero(request, tercero_id):
    """
    Ejecutar scraping de Stradata para un tercero específico
    POST /api/terceros/{tercero_id}/scraping/
    
    Solo usuarios con rol 'procesos' pueden ejecutar scraping
    """
    try:
        # Verificar permisos
        if not request.user.is_authenticated:
            return Response({
                'success': False,
                'error': 'Autenticación requerida'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Verificar que el usuario tenga rol de procesos
        if request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden ejecutar scraping'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Importar el servicio
        from .services import stradata_service
        
        # Ejecutar scraping
        logger.info(f"Usuario {request.user.username} inició scraping para tercero {tercero_id}")
        resultado = stradata_service.ejecutar_scraping_tercero(tercero_id)
        
        if resultado['success']:
            logger.info(f"Scraping exitoso para tercero {tercero_id}: {resultado['exitosos']}/{resultado['total_consultas']} consultas")
            return Response(resultado, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Scraping falló para tercero {tercero_id}: {resultado['error']}")
            return Response(resultado, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error en endpoint de scraping para tercero {tercero_id}: {e}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def ejecutar_scraping_masivo(request):
    """
    Ejecutar scraping masivo para múltiples terceros
    POST /api/terceros/scraping-masivo/
    
    Body: {"limite": 10} (opcional)
    Solo usuarios con rol 'procesos' pueden ejecutar scraping masivo
    """
    try:
        # Verificar permisos
        if not request.user.is_authenticated:
            return Response({
                'success': False,
                'error': 'Autenticación requerida'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Verificar que el usuario tenga rol de procesos
        if request.user.role != 'procesos':
            return Response({
                'success': False,
                'error': 'Solo usuarios de procesos pueden ejecutar scraping'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener límite opcional
        limite = request.data.get('limite')
        if limite:
            try:
                limite = int(limite)
                if limite <= 0:
                    limite = None
            except (ValueError, TypeError):
                limite = None
        
        # Importar el servicio
        from .services import stradata_service
        
        # Ejecutar scraping masivo
        logger.info(f"Usuario {request.user.username} inició scraping masivo (límite: {limite})")
        resultado = stradata_service.ejecutar_scraping_masivo(limite)
        
        if resultado['success']:
            logger.info(f"Scraping masivo exitoso: {resultado['terceros_exitosos']}/{resultado['total_terceros']} terceros")
            return Response(resultado, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Scraping masivo falló: {resultado['error']}")
            return Response(resultado, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error en endpoint de scraping masivo: {e}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def obtener_documentos_stradata(request, tercero_id):
    """
    Obtener documentos de Stradata para un tercero específico
    GET /api/terceros/{tercero_id}/documentos-stradata/
    """
    try:
        # Verificar que el tercero existe
        tercero = Tercero.objects.get(id=tercero_id)
        
        # Buscar documentos en el directorio de Stradata
        from pathlib import Path
        from django.conf import settings
        
        stradata_dir = Path(settings.MEDIA_ROOT) / "documentos" / "terceros" / str(tercero.numero_documento) / "stradata"
        
        documentos_data = []
        if stradata_dir.exists():
            # Buscar en subdirectorios organizados
            subdirs = ['tercero_principal', 'personas_pep', 'representantes_legales', 'accionistas']
            
            for subdir in subdirs:
                subdir_path = stradata_dir / subdir
                if subdir_path.exists():
                    archivos = []
                    for archivo in subdir_path.glob('*.pdf'):
                        archivos.append({
                            'nombre': archivo.name,
                            'ruta': f"/media/documentos/terceros/{tercero.numero_documento}/stradata/{subdir}/",
                            'tamaño': f"{archivo.stat().st_size / (1024*1024):.1f} MB",
                            'fecha_descarga': archivo.stat().st_mtime
                        })
                    
                    if archivos:
                        documentos_data.append({
                            'tipo_persona': subdir,
                            'archivos': archivos
                        })
        
        return Response({
            'success': True,
            'tercero_id': tercero_id,
            'numero_documento': tercero.numero_documento,
            'documentos': documentos_data,
            'total_documentos': sum(len(grupo['archivos']) for grupo in documentos_data)
        }, status=status.HTTP_200_OK)
        
    except Tercero.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tercero no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error obteniendo documentos Stradata para tercero {tercero_id}: {e}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# VIEWSET PARA NUEVA ESTRUCTURA PEP 2025
# ==========================================

class InformacionPEPViewSet(viewsets.ModelViewSet):
    """
    ViewSet CRÍTICO para gestión de Personas Expuestas Políticamente
    ESTRUCTURA ACTUALIZADA según documentación PEP 2025
    Cumplimiento SARLAFT obligatorio
    """
    queryset = InformacionPEP.objects.all()
    serializer_class = InformacionPEPSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar registros según permisos del usuario"""
        queryset = super().get_queryset()
        
        # Filtrar por tercero si se especifica
        tercero_id = self.request.query_params.get('tercero_id', None)
        if tercero_id:
            queryset = queryset.filter(tercero_id=tercero_id)
        
        # Filtrar por estructura (legacy vs nueva)
        estructura = self.request.query_params.get('estructura', None)
        if estructura == 'legacy':
            queryset = queryset.filter(
                cargo='No especificado',
                parentesco='No especificado'
            )
        elif estructura == 'nueva':
            queryset = queryset.exclude(
                cargo='No especificado',
                parentesco='No especificado'
            )
        
        return queryset.order_by('-updated_at')
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas de estructura PEP"""
        total = self.get_queryset().count()
        legacy = self.get_queryset().filter(
            cargo='No especificado',
            parentesco='No especificado'
        ).count()
        nueva = total - legacy
        
        return Response({
            'total_registros': total,
            'estructura_legacy': legacy,
            'estructura_nueva': nueva,
            'porcentaje_migrado': round((nueva / total * 100) if total > 0 else 0, 2),
            'ultimo_actualizado': timezone.now()
        })
    
    @action(detail=False, methods=['post'])
    def migrar_legacy(self, request):
        """Migrar registros legacy a nueva estructura"""
        try:
            registros_legacy = self.get_queryset().filter(
                cargo='No especificado',
                parentesco='No especificado'
            )
            
            if not registros_legacy.exists():
                return Response({
                    'message': 'No hay registros legacy para migrar',
                    'migrados': 0
                }, status=status.HTTP_200_OK)
            
            migrados = 0
            for registro in registros_legacy:
                # Mapear según tipo de documento
                if registro.tipo == 'CC':
                    registro.cargo = 'Funcionario Público Nacional'
                    registro.parentesco = 'Titular'
                elif registro.tipo == 'CE':
                    registro.cargo = 'Funcionario Internacional'
                    registro.parentesco = 'Cónyuge'
                elif registro.tipo == 'NIT':
                    registro.cargo = 'Representante Legal'
                    registro.parentesco = 'Socio'
                else:
                    registro.cargo = 'Cargo no identificado'
                    registro.parentesco = 'Relación no identificada'
                
                # Migrar campos
                registro.cuentas_financieras_exterior = registro.patrimonio_fiducia
                registro.fecha_vinculacion = timezone.now().date()
                registro.save()
                migrados += 1
            
            logger.info(f"Migrados {migrados} registros PEP por usuario {request.user.username}")
            
            return Response({
                'message': f'Se migraron {migrados} registros exitosamente',
                'migrados': migrados
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en migración PEP: {str(e)}")
            return Response({
                'error': 'Error en la migración',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def actualizar_estructura(self, request, pk=None):
        """Actualizar un registro específico a nueva estructura"""
        try:
            registro = self.get_object()
            data = request.data
            
            # Validar campos obligatorios
            campos_requeridos = ['cargo', 'parentesco', 'fecha_vinculacion', 'fecha_retiro']
            campos_faltantes = [campo for campo in campos_requeridos if not data.get(campo)]
            
            if campos_faltantes:
                return Response({
                    'error': f'Campos requeridos faltantes: {", ".join(campos_faltantes)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Actualizar campos
            registro.cargo = data['cargo']
            registro.parentesco = data['parentesco']
            registro.fecha_vinculacion = data['fecha_vinculacion']
            registro.fecha_retiro = data['fecha_retiro']
            registro.cuentas_financieras_exterior = data.get('cuentas_financieras_exterior', False)
            
            registro.save()
            
            logger.info(f"Registro PEP {registro.id} actualizado por {request.user.username}")
            
            serializer = self.get_serializer(registro)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error actualizando registro PEP {pk}: {str(e)}")
            return Response({
                'error': 'Error actualizando registro',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================
# VIEWS PARA HISTORIAL Y AUDITORÍA
# ============================================

class HistorialTerceroViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar el historial de terceros
    Solo permite operaciones de lectura (GET)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        from .serializers import HistorialTerceroSerializer
        return HistorialTerceroSerializer
    
    def get_queryset(self):
        from .models import HistorialTercero
        queryset = HistorialTercero.objects.select_related(
            'tercero', 'usuario', 'usuario_asignado_anterior', 'usuario_asignado_nuevo'
        ).all()
        
        # Filtrar por tercero si se especifica
        tercero_id = self.request.query_params.get('tercero_id', None)
        if tercero_id:
            queryset = queryset.filter(tercero_id=tercero_id)
        
        # Filtrar por usuario si se especifica
        usuario_id = self.request.query_params.get('usuario_id', None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        
        # Filtrar por tipo de acción
        accion = self.request.query_params.get('accion', None)
        if accion:
            queryset = queryset.filter(accion=accion)
        
        # Filtrar por departamento
        departamento = self.request.query_params.get('departamento', None)
        if departamento:
            queryset = queryset.filter(departamento=departamento)
        
        # Filtrar por rango de fechas
        fecha_desde = self.request.query_params.get('fecha_desde', None)
        fecha_hasta = self.request.query_params.get('fecha_hasta', None)
        
        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
                queryset = queryset.filter(fecha_accion__gte=fecha_desde)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                queryset = queryset.filter(fecha_accion__lte=fecha_hasta)
            except ValueError:
                pass
        
        return queryset.order_by('-fecha_accion')
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas generales del historial"""
        from .models import HistorialTercero
        from django.db.models import Count
        
        # Contar acciones por tipo
        acciones_por_tipo = HistorialTercero.objects.values(
            'accion'
        ).annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Usuarios más activos
        usuarios_activos = HistorialTercero.objects.filter(
            usuario__isnull=False
        ).values(
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            total_acciones=Count('id')
        ).order_by('-total_acciones')[:10]
        
        # Acciones por departamento
        acciones_por_departamento = HistorialTercero.objects.filter(
            departamento__isnull=False
        ).values('departamento').annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Actividad por días
        from django.utils import timezone
        from datetime import timedelta
        
        hace_30_dias = timezone.now() - timedelta(days=30)
        actividad_reciente = HistorialTercero.objects.filter(
            fecha_accion__gte=hace_30_dias
        ).extra(
            select={'fecha': 'DATE(fecha_accion)'}
        ).values('fecha').annotate(
            total=Count('id')
        ).order_by('fecha')
        
        return Response({
            'acciones_por_tipo': [
                {
                    'accion': item['accion'],
                    'accion_display': dict(HistorialTercero.TipoAccion.choices).get(item['accion']),
                    'total': item['total']
                }
                for item in acciones_por_tipo
            ],
            'usuarios_mas_activos': [
                {
                    'username': item['usuario__username'],
                    'nombre_completo': f"{item['usuario__first_name']} {item['usuario__last_name']}",
                    'total_acciones': item['total_acciones']
                }
                for item in usuarios_activos
            ],
            'acciones_por_departamento': list(acciones_por_departamento),
            'actividad_ultimos_30_dias': list(actividad_reciente),
            'total_registros': HistorialTercero.objects.count(),
        })


# Agregar acción al TerceroViewSet existente para obtener historial
# Nota: Esta vista se agrega como una extensión del TerceroViewSet existente

def agregar_historial_a_tercero_viewset():
    """
    Esta función agrega métodos de historial al TerceroViewSet existente
    Se debe llamar después de definir TerceroViewSet
    """
    
    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        """Obtener historial completo de un tercero específico"""
        tercero = self.get_object()
        
        # Obtener historial con paginación
        historial_queryset = tercero.historial.select_related(
            'usuario', 'usuario_asignado_anterior', 'usuario_asignado_nuevo'
        ).all()
        
        # Aplicar filtros si se especifican
        accion = request.query_params.get('accion', None)
        if accion:
            historial_queryset = historial_queryset.filter(accion=accion)
        
        departamento = request.query_params.get('departamento', None)
        if departamento:
            historial_queryset = historial_queryset.filter(departamento=departamento)
        
        # Paginación
        page = self.paginate_queryset(historial_queryset)
        if page is not None:
            from .serializers import HistorialTerceroSerializer
            serializer = HistorialTerceroSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        from .serializers import HistorialTerceroSerializer
        serializer = HistorialTerceroSerializer(historial_queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def resumen_auditoria(self, request, pk=None):
        """Resumen de auditoría de un tercero específico"""
        tercero = self.get_object()
        
        # Información básica
        resumen = {
            'tercero': {
                'id': str(tercero.id),
                'numero_documento': tercero.numero_documento,
                'nombre_completo': tercero.get_nombre_completo(),
                'estado_actual': tercero.estado_aprobacion,
                'fecha_creacion': tercero.created_at,
                'fecha_ultima_modificacion': tercero.updated_at
            },
            'asignacion_actual': tercero.obtener_asignacion_actual(),
            'ultima_accion': None,
            'historial_resumido': []
        }
        
        # Última acción
        ultima_accion = tercero.obtener_ultima_accion()
        if ultima_accion:
            from .serializers import HistorialTerceroSerializer
            resumen['ultima_accion'] = HistorialTerceroSerializer(ultima_accion).data
        
        # Historial resumido por tipo de acción
        from .models import HistorialTercero
        historial_por_tipo = tercero.historial.values(
            'accion'
        ).annotate(
            total=Count('id'),
            ultima_fecha=timezone.now()  # Agregar campo de última fecha
        ).order_by('-total')
        
        for item in historial_por_tipo:
            # Obtener la última entrada de este tipo
            ultima_entrada = tercero.historial.filter(accion=item['accion']).first()
            
            resumen['historial_resumido'].append({
                'accion': item['accion'],
                'accion_display': dict(HistorialTercero.TipoAccion.choices).get(item['accion']),
                'total_veces': item['total'],
                'ultima_fecha': ultima_entrada.fecha_accion if ultima_entrada else None,
                'ultimo_usuario': ultima_entrada.usuario.get_full_name() if ultima_entrada and ultima_entrada.usuario else None
            })
        
        return Response(resumen)
    
    @action(detail=True, methods=['post'])
    def agregar_observacion(self, request, pk=None):
        """Agregar una observación al tercero"""
        tercero = self.get_object()
        observaciones = request.data.get('observaciones', '')
        
        if not observaciones.strip():
            return Response({
                'error': 'Las observaciones no pueden estar vacías'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Registrar la observación en el historial
        tercero._registrar_historial_observacion(
            usuario=request.user,
            observaciones=observaciones,
            request=request
        )
        
        # También actualizar las observaciones según el rol del usuario
        if request.user.role == 'comercial':
            tercero.observaciones_comercial = observaciones
        elif request.user.role == 'procesos':
            tercero.observaciones_procesos = observaciones
        elif request.user.role == 'oficial_cumplimiento':
            tercero.observaciones_cumplimiento = observaciones
        elif request.user.role == 'administrador':
            tercero.observaciones_administrador = observaciones
        
        tercero.save()
        
        return Response({
            'success': True,
            'message': 'Observación agregada exitosamente',
            'observaciones': observaciones
        })
    
    # Retornar los métodos para agregarlos al viewset
    return historial, resumen_auditoria, agregar_observacion


# Registrar los métodos de historial
_historial_methods = agregar_historial_a_tercero_viewset()

# Aquí se pueden agregar los métodos al TerceroViewSet existente si está definido
# TerceroViewSet.historial = _historial_methods[0]
# TerceroViewSet.resumen_auditoria = _historial_methods[1] 
# TerceroViewSet.agregar_observacion = _historial_methods[2]


# ==========================================
# NUEVAS VISTAS PARA ENDPOINTS ADICIONALES
# ==========================================

class TerceroHistorialAPIView(APIView):
    """
    Vista para obtener el historial completo de un tercero
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, tercero_id):
        try:
            tercero = Tercero.objects.get(id=tercero_id)
            
            # Verificar permisos
            if not request.user.role in ['administrador', 'procesos', 'comercial', 'oficial_cumplimiento']:
                return Response({
                    'success': False,
                    'error': 'No tiene permisos para ver el historial'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Obtener historial completo
            historial = tercero.obtener_historial_completo()
            
            historial_data = []
            for registro in historial:
                registro_data = {
                    'id': registro.id,
                    'accion': registro.accion,
                    'fecha': registro.fecha_accion,
                    'usuario': registro.usuario.username if registro.usuario else None,
                    'usuario_nombre': f"{registro.usuario.first_name} {registro.usuario.last_name}".strip() if registro.usuario else None,
                    'estado_anterior': registro.estado_anterior,
                    'estado_nuevo': registro.estado_nuevo,
                    'observaciones': registro.observaciones,
                    'departamento': registro.departamento
                }
                historial_data.append(registro_data)
            
            return Response({
                'success': True,
                'tercero_id': str(tercero_id),
                'total_registros': len(historial_data),
                'historial': historial_data
            }, status=status.HTTP_200_OK)
            
        except Tercero.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Tercero no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Error obteniendo historial: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def tercero_estadisticas(request, tercero_id):
    """
    Obtiene estadísticas completas de un tercero específico
    """
    try:
        tercero = Tercero.objects.get(id=tercero_id)
        
        # Verificar permisos
        if not request.user.role in ['administrador', 'procesos', 'comercial', 'oficial_cumplimiento']:
            return Response({
                'success': False,
                'error': 'No tiene permisos para ver las estadísticas'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener historial para calcular estadísticas
        historial = tercero.obtener_historial_completo()
        
        # Calcular estadísticas
        total_acciones = historial.count()
        aprobaciones = historial.filter(accion__icontains='aprobacion').count()
        rechazos = historial.filter(accion__icontains='rechazo').count()
        asignaciones = historial.filter(accion__icontains='asignacion').count()
        
        # Información de responsables actuales
        responsables_actuales = {
            'comercial': {
                'usuario': tercero.asignado_a.username if tercero.asignado_a else None,
                'nombre_completo': f"{tercero.asignado_a.first_name} {tercero.asignado_a.last_name}".strip() if tercero.asignado_a else None,
                'email': tercero.asignado_a.email if tercero.asignado_a else None,
                'fecha_asignacion': tercero.fecha_asignacion_comercial
            },
            'procesos': {
                'usuario': tercero.asignado_a_procesos.username if tercero.asignado_a_procesos else None,
                'nombre_completo': f"{tercero.asignado_a_procesos.first_name} {tercero.asignado_a_procesos.last_name}".strip() if tercero.asignado_a_procesos else None,
                'email': tercero.asignado_a_procesos.email if tercero.asignado_a_procesos else None,
                'fecha_asignacion': tercero.fecha_asignacion_procesos
            },
            'cumplimiento': {
                'usuario': tercero.asignado_cumplimiento.username if tercero.asignado_cumplimiento else None,
                'nombre_completo': f"{tercero.asignado_cumplimiento.first_name} {tercero.asignado_cumplimiento.last_name}".strip() if tercero.asignado_cumplimiento else None,
                'email': tercero.asignado_cumplimiento.email if tercero.asignado_cumplimiento else None,
                'fecha_asignacion': tercero.fecha_asignacion_cumplimiento
            }
        }
        
        # Estadísticas generales
        estadisticas = {
            'total_acciones': total_acciones,
            'aprobaciones': aprobaciones,
            'rechazos': rechazos,
            'asignaciones': asignaciones,
            'estado_actual': tercero.estado_aprobacion,
            'fecha_creacion': tercero.created_at,
            'ultima_actualizacion': tercero.updated_at
        }
        
        return Response({
            'success': True,
            'tercero_id': str(tercero_id),
            'estadisticas': estadisticas,
            'responsables_actuales': responsables_actuales,
            'ultima_actualizacion': timezone.now()
        }, status=status.HTTP_200_OK)
        
    except Tercero.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tercero no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def tercero_historial_detallado(request, tercero_id):
    """
    Obtiene historial detallado con análisis adicional
    """
    try:
        tercero = Tercero.objects.get(id=tercero_id)
        
        # Verificar permisos
        if not request.user.role in ['administrador', 'procesos']:
            return Response({
                'success': False,
                'error': 'No tiene permisos para ver el historial detallado'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener historial completo
        historial = tercero.obtener_historial_completo()
        
        # Análisis detallado
        historial_detallado = []
        for registro in historial:
            detalle = {
                'id': registro.id,
                'accion': registro.accion,
                'fecha': registro.fecha_accion,
                'usuario': {
                    'id': registro.usuario.id if registro.usuario else None,
                    'username': registro.usuario.username if registro.usuario else None,
                    'nombre_completo': f"{registro.usuario.first_name} {registro.usuario.last_name}".strip() if registro.usuario else None,
                    'role': registro.usuario.role if registro.usuario else None
                },
                'cambios': {
                    'estado_anterior': registro.estado_anterior,
                    'estado_nuevo': registro.estado_nuevo
                },
                'contexto': {
                    'departamento': registro.departamento,
                    'observaciones': registro.observaciones,
                    'ip_address': registro.ip_address,
                    'metadatos': registro.metadatos if hasattr(registro, 'metadatos') else None
                }
            }
            historial_detallado.append(detalle)
        
        return Response({
            'success': True,
            'tercero_id': str(tercero_id),
            'total_registros': len(historial_detallado),
            'historial': historial_detallado,
            'resumen': {
                'fecha_primer_registro': historial.last().fecha_accion if historial.exists() else None,
                'fecha_ultimo_registro': historial.first().fecha_accion if historial.exists() else None,
                'usuarios_involucrados': historial.values('usuario__username').distinct().count(),
                'departamentos_involucrados': historial.values('departamento').distinct().count()
            }
        }, status=status.HTTP_200_OK)
        
    except Tercero.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tercero no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error obteniendo historial detallado: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# ENDPOINTS ESPECÍFICOS PARA DEBIDA DILIGENCIA
# =============================================================================

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def listar_documentos_debida_diligencia(request, tercero_id):
    """
    Endpoint para listar documentos de Debida Diligencia
    GET /api/terceros/{tercero_id}/debida-diligencia/
    """
    try:
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Tipos de documentos de debida diligencia
        tipos_dd = [
            'debida_diligencia_formulario', 'debida_diligencia_verificacion',
            'debida_diligencia_bienes', 'debida_diligencia_vinculacion',
            'perfil_riesgo_matriz', 'perfil_riesgo_evaluacion',
            'perfil_riesgo_actualizacion', 'perfil_riesgo_calificacion',
            'soporte_referencias', 'soporte_financieros', 'soporte_certificaciones',
            'soporte_licencias', 'evaluacion_informe', 'evaluacion_recomendaciones',
            'evaluacion_mitigacion', 'seguimiento_revision', 'seguimiento_actualizacion',
            'seguimiento_monitoreo', 'debida_diligencia_otro'
        ]
        
        # Obtener parámetros de filtro
        tipo_documento = request.GET.get('tipo', None)
        
        # Construir queryset con filtros
        documentos = DocumentoTercero.objects.filter(
            tercero=tercero, 
            es_vigente=True,
            tipo_documento__in=tipos_dd
        )
        
        if tipo_documento and tipo_documento in tipos_dd:
            documentos = documentos.filter(tipo_documento=tipo_documento)
        
        # Ordenar por fecha de subida descendente
        documentos = documentos.order_by('-fecha_subida')
        
        # Preparar respuesta con estructura similar a debida diligencia
        documentos_data = []
        for doc in documentos:
            documento_data = {
                'id': doc.id,
                'uuid': str(doc.id),  # Usar mismo ID como UUID para compatibilidad
                'nombre': doc.nombre_original,
                'descripcion': f'Documento de debida diligencia: {doc.get_tipo_documento_display()}',
                'categoria': 'debida_diligencia',
                'categoria_display': 'Debida Diligencia',
                'tipo_documento': doc.tipo_documento,
                'tipo_documento_display': doc.get_tipo_documento_display(),
                'estado': 'pendiente',
                'estado_display': 'Pendiente de Revisión',
                'fecha_subida': doc.fecha_subida.isoformat(),
                'fecha_vencimiento': doc.fecha_vencimiento.isoformat() if doc.fecha_vencimiento else None,
                'esta_vencido': False,  # Implementar lógica si es necesario
                'dias_para_vencer': None,  # Implementar lógica si es necesario
                'tamaño_archivo': doc.tamano_archivo,
                'tercero_uuid': str(tercero.id),
                'tercero_numero_documento': tercero.numero_documento,
                'tercero_nombre': tercero.get_nombre_completo(),
                'subido_por_nombre': 'Sistema',  # DocumentoTercero no tiene este campo
            }
            documentos_data.append(documento_data)
        
        return Response({
            'success': True,
            'tercero_id': str(tercero.id),
            'numero_documento': tercero.numero_documento,
            'nombre_tercero': tercero.get_nombre_completo(),
            'documentos': documentos_data,
            'total_documentos': len(documentos_data),
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listando documentos DD: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])  # Añadir parsers explícitos
def subir_documento_debida_diligencia(request, tercero_id):
    """
    Endpoint para subir documentos de Debida Diligencia
    POST /api/terceros/{tercero_id}/debida-diligencia/upload/
    """
    try:
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        # Logging detallado para debug
        logger.info(f"=== SUBIDA DD DEBUG ===")
        logger.info(f"Tercero ID: {tercero_id}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"FILES keys: {list(request.FILES.keys())}")
        logger.info(f"DATA keys: {list(request.data.keys())}")
        logger.info(f"POST keys: {list(request.POST.keys())}")
        logger.info(f"Raw FILES: {request.FILES}")
        logger.info(f"Raw DATA: {request.data}")
        
        # Validar que hay un archivo en la petición
        if 'archivo' not in request.FILES:
            logger.error(f"ERROR: No hay 'archivo' en FILES. FILES disponibles: {list(request.FILES.keys())}")
            return Response({
                'success': False,
                'error': 'No se proporcionó ningún archivo',
                'debug_info': {
                    'files_keys': list(request.FILES.keys()),
                    'data_keys': list(request.data.keys()),
                    'content_type': request.content_type
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener datos de la petición
        archivo = request.FILES['archivo']
        tipo_documento = request.data.get('tipo_documento', 'debida_diligencia_otro')
        # Aceptar tanto 'nombre' como 'nombre_documento' para compatibilidad
        nombre_documento = request.data.get('nombre') or request.data.get('nombre_documento') or archivo.name
        
        # Logging detallado para debug
        logger.info(f"Datos recibidos - archivo: {archivo.name}, tipo: {tipo_documento}, nombre: {nombre_documento}")
        logger.info(f"request.data keys: {list(request.data.keys())}")
        
        # Validar tipo de documento
        tipos_dd = [
            'debida_diligencia_formulario', 'debida_diligencia_verificacion',
            'debida_diligencia_bienes', 'debida_diligencia_vinculacion',
            'perfil_riesgo_matriz', 'perfil_riesgo_evaluacion',
            'perfil_riesgo_actualizacion', 'perfil_riesgo_calificacion',
            'soporte_referencias', 'soporte_financieros', 'soporte_certificaciones',
            'soporte_licencias', 'evaluacion_informe', 'evaluacion_recomendaciones',
            'evaluacion_mitigacion', 'seguimiento_revision', 'seguimiento_actualizacion',
            'seguimiento_monitoreo', 'debida_diligencia_otro'
        ]
        
        if tipo_documento not in tipos_dd:
            tipo_documento = 'debida_diligencia_otro'
        
        # Crear el documento
        documento = DocumentoTercero.objects.create(
            tercero=tercero,
            tipo_documento=tipo_documento,
            archivo=archivo,
            nombre_original=nombre_documento,
            tamano_archivo=archivo.size,
            es_vigente=True
        )
        
        logger.info(
            f"Documento DD subido: {documento.nombre_original} "
            f"para tercero {tercero.numero_documento} por {request.user}"
        )
        
        # Preparar respuesta
        documento_data = {
            'id': documento.id,
            'uuid': str(documento.id),
            'nombre': documento.nombre_original,
            'descripcion': f'Documento de debida diligencia: {documento.get_tipo_documento_display()}',
            'categoria': 'debida_diligencia',
            'categoria_display': 'Debida Diligencia',
            'tipo_documento': documento.tipo_documento,
            'tipo_documento_display': documento.get_tipo_documento_display(),
            'estado': 'pendiente',
            'estado_display': 'Pendiente de Revisión',
            'fecha_subida': documento.fecha_subida.isoformat(),
            'fecha_vencimiento': documento.fecha_vencimiento.isoformat() if documento.fecha_vencimiento else None,
            'esta_vencido': False,
            'dias_para_vencer': None,
            'tamaño_archivo': documento.tamano_archivo,
            'tercero_uuid': str(tercero.id),
            'tercero_numero_documento': tercero.numero_documento,
            'tercero_nombre': tercero.get_nombre_completo(),
            'subido_por_nombre': f'{request.user.first_name} {request.user.last_name}',
        }
        
        return Response({
            'success': True,
            'message': 'Documento subido exitosamente',
            'documento': documento_data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error subiendo documento DD: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def eliminar_documento_debida_diligencia(request, documento_id):
    """
    Endpoint para eliminar un documento de Debida Diligencia
    DELETE /api/terceros/debida-diligencia/{documento_id}/
    """
    try:
        # Validar que el documento_id no sea None o 'undefined'
        if not documento_id or str(documento_id) in ['undefined', 'null', '']:
            logger.warning(f"Intento de eliminar documento con ID inválido: {documento_id}")
            return Response({
                'success': False,
                'error': 'ID de documento inválido',
                'received_id': str(documento_id)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar el documento
        documento = get_object_or_404(DocumentoTercero, id=documento_id)
        
        # Verificar que es un documento de debida diligencia
        tipos_dd = [
            'debida_diligencia_formulario', 'debida_diligencia_verificacion',
            'debida_diligencia_bienes', 'debida_diligencia_vinculacion',
            'perfil_riesgo_matriz', 'perfil_riesgo_evaluacion',
            'perfil_riesgo_actualizacion', 'perfil_riesgo_calificacion',
            'soporte_referencias', 'soporte_financieros', 'soporte_certificaciones',
            'soporte_licencias', 'evaluacion_informe', 'evaluacion_recomendaciones',
            'evaluacion_mitigacion', 'seguimiento_revision', 'seguimiento_actualizacion',
            'seguimiento_monitoreo', 'debida_diligencia_otro'
        ]
        
        if documento.tipo_documento not in tipos_dd:
            return Response({
                'success': False,
                'error': 'El documento no es de debida diligencia'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Guardar información del documento antes de eliminarlo
        documento_info = {
            'id': documento.id,
            'nombre': documento.nombre_original,
            'tercero_id': str(documento.tercero.id),
            'tipo_documento': documento.get_tipo_documento_display()
        }
        
        # Marcar como no vigente (soft delete)
        documento.es_vigente = False
        documento.save(update_fields=['es_vigente'])
        
        logger.info(f"Documento DD eliminado: {documento_info['nombre']} por {request.user}")
        
        return Response({
            'success': True,
            'message': 'Documento eliminado exitosamente',
            'documento': documento_info
        }, status=status.HTTP_200_OK)
        
    except DocumentoTercero.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Documento no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error eliminando documento DD: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def descargar_documento_debida_diligencia(request, documento_id):
    """
    Endpoint para descargar un documento de Debida Diligencia
    GET /api/terceros/debida-diligencia/{documento_id}/download/
    """
    try:
        # Logging para debug de autenticación
        auth_header = request.META.get('HTTP_AUTHORIZATION', 'No Authorization header')
        logger.info(f"Descarga DD solicitada - Documento ID: {documento_id}, Auth: {auth_header[:50]}..." if len(auth_header) > 50 else f"Descarga DD solicitada - Documento ID: {documento_id}, Auth: {auth_header}")
        logger.info(f"Usuario autenticado: {request.user} (is_authenticated: {request.user.is_authenticated})")
        
        # Validar que el documento_id no sea None o 'undefined'
        if not documento_id or str(documento_id) in ['undefined', 'null', '']:
            logger.warning(f"Intento de descargar documento con ID inválido: {documento_id}")
            return Response({
                'success': False,
                'error': 'ID de documento inválido',
                'received_id': str(documento_id)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar el documento
        documento = get_object_or_404(DocumentoTercero, id=documento_id, es_vigente=True)
        
        # Verificar que es un documento de debida diligencia
        tipos_dd = [
            'debida_diligencia_formulario', 'debida_diligencia_verificacion',
            'debida_diligencia_bienes', 'debida_diligencia_vinculacion',
            'perfil_riesgo_matriz', 'perfil_riesgo_evaluacion',
            'perfil_riesgo_actualizacion', 'perfil_riesgo_calificacion',
            'soporte_referencias', 'soporte_financieros', 'soporte_certificaciones',
            'soporte_licencias', 'evaluacion_informe', 'evaluacion_recomendaciones',
            'evaluacion_mitigacion', 'seguimiento_revision', 'seguimiento_actualizacion',
            'seguimiento_monitoreo', 'debida_diligencia_otro'
        ]
        
        if documento.tipo_documento not in tipos_dd:
            return Response({
                'success': False,
                'error': 'El documento no es de debida diligencia'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que el archivo existe
        if not documento.archivo:
            return Response({
                'success': False,
                'error': 'Archivo no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Obtener el archivo
        try:
            from django.http import HttpResponse
            import mimetypes
            import os
            
            archivo_path = documento.archivo.path
            
            # Determinar el tipo MIME
            content_type, _ = mimetypes.guess_type(archivo_path)
            if content_type is None:
                content_type = 'application/octet-stream'
            
            # Leer el archivo
            with open(archivo_path, 'rb') as archivo:
                response = HttpResponse(archivo.read(), content_type=content_type)
                
                # Configurar headers para descarga
                filename = documento.nombre_original or os.path.basename(archivo_path)
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = os.path.getsize(archivo_path)
                
                # Headers adicionales
                response['Cache-Control'] = 'no-cache'
                response['X-Documento-ID'] = str(documento.id)
                response['X-Tipo-Documento'] = documento.tipo_documento
                
                logger.info(f"Documento DD descargado: {documento.nombre_original} por {request.user}")
                
                return response
                
        except FileNotFoundError:
            return Response({
                'success': False,
                'error': 'Archivo no encontrado en el servidor'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except PermissionError:
            return Response({
                'success': False,
                'error': 'Sin permisos para acceder al archivo'
            }, status=status.HTTP_403_FORBIDDEN)
    
    except DocumentoTercero.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Documento no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error descargando documento DD: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def opciones_debida_diligencia(request):
    """
    Endpoint para obtener opciones de tipos de documentos de Debida Diligencia
    GET /api/terceros/debida-diligencia/opciones/
    """
    try:
        # Obtener tipos de documento de debida diligencia del modelo
        tipos_dd_choices = [
            ('debida_diligencia_formulario', 'Formulario de Debida Diligencia'),
            ('debida_diligencia_verificacion', 'Lista de Verificación DD'),
            ('debida_diligencia_bienes', 'Declaración de Bienes'),
            ('debida_diligencia_vinculacion', 'Carta de No Vinculación'),
            ('perfil_riesgo_matriz', 'Matriz de Riesgo'),
            ('perfil_riesgo_evaluacion', 'Evaluación Inicial de Riesgo'),
            ('perfil_riesgo_actualizacion', 'Actualización de Perfil'),
            ('perfil_riesgo_calificacion', 'Calificación de Riesgo'),
            ('soporte_referencias', 'Referencias Comerciales'),
            ('soporte_financieros', 'Estados Financieros'),
            ('soporte_certificaciones', 'Certificaciones'),
            ('soporte_licencias', 'Licencias y Permisos'),
            ('evaluacion_informe', 'Informe de Evaluación'),
            ('evaluacion_recomendaciones', 'Recomendaciones'),
            ('evaluacion_mitigacion', 'Plan de Mitigación'),
            ('seguimiento_revision', 'Revisión Periódica'),
            ('seguimiento_actualizacion', 'Actualización de Datos'),
            ('seguimiento_monitoreo', 'Monitoreo Continuo'),
            ('debida_diligencia_otro', 'Otro Documento DD'),
        ]
        
        return Response({
            'success': True,
            'opciones': {
                'tipos_documento': [
                    {'value': key, 'label': value} 
                    for key, value in tipos_dd_choices
                ],
                'categorias': [
                    {'value': 'debida_diligencia', 'label': 'Debida Diligencia'},
                    {'value': 'perfil_riesgo', 'label': 'Perfil de Riesgo'},
                    {'value': 'documentos_soporte', 'label': 'Documentos de Soporte'},
                    {'value': 'evaluacion_riesgo', 'label': 'Evaluación de Riesgo'},
                    {'value': 'seguimiento', 'label': 'Seguimiento y Monitoreo'},
                ],
                'estados': [
                    {'value': 'pendiente', 'label': 'Pendiente de Revisión'},
                    {'value': 'en_revision', 'label': 'En Revisión'},
                    {'value': 'aprobado', 'label': 'Aprobado'},
                    {'value': 'rechazado', 'label': 'Rechazado'},
                    {'value': 'vencido', 'label': 'Vencido'},
                ]
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo opciones DD: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def exportar_tercero_excel(request, tercero_id):
    """
    Endpoint para exportar información completa de un tercero a Excel
    GET /api/terceros/{tercero_id}/exportar/
    """
    try:
        # Verificar que el tercero existe
        tercero = get_object_or_404(Tercero, id=tercero_id)
        
        logger.info(f"Exportando tercero {tercero.numero_documento} a Excel por usuario {request.user}")
        
        # Crear un libro de Excel
        wb = Workbook()
        
        # ===== HOJA 1: INFORMACIÓN BÁSICA =====
        ws_basica = wb.active
        ws_basica.title = "Información Básica"
        
        # Datos básicos del tercero
        datos_basicos = {
            'Campo': [
                'Número de Documento', 'Tipo de Documento', 'Nombre/Razón Social',
                'Nombres', 'Apellidos', 'Dígito Verificación',
                'Email', 'Teléfono', 'Celular', 'Dirección', 'Ciudad', 'País',
                'Tipo de Persona', 'Estado', 'Fecha de Creación', 'Fecha de Actualización',
                'Usuario Asignado', 'Estado del Formulario'
            ],
            'Valor': [
                tercero.numero_documento,
                tercero.get_tipo_documento_display(),
                tercero.razon_social or f"{tercero.nombres} {tercero.apellidos or ''}".strip(),
                tercero.nombres or '',
                tercero.apellidos or '',
                tercero.digito_verificacion or '',
                tercero.email or '',
                tercero.telefono or '',
                tercero.celular or '',
                tercero.direccion or '',
                tercero.ciudad or '',
                tercero.pais or '',
                tercero.get_tipo_persona_display(),
                tercero.get_estado_aprobacion_display(),
                tercero.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                tercero.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                f"{tercero.usuario_asignado.first_name} {tercero.usuario_asignado.last_name}" if tercero.usuario_asignado else 'No asignado',
                tercero.get_tipo_formulario_display()
            ]
        }
        
        df_basicos = pd.DataFrame(datos_basicos)
        
        # Escribir datos básicos
        for r in dataframe_to_rows(df_basicos, index=False, header=True):
            ws_basica.append(r)
        
        # Aplicar estilos a la hoja básica
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for cell in ws_basica[1]:  # Primera fila (headers)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # Ajustar ancho de columnas
        ws_basica.column_dimensions['A'].width = 30
        ws_basica.column_dimensions['B'].width = 50
        
        # ===== HOJA 2: INFORMACIÓN FINANCIERA =====
        ws_financiera = wb.create_sheet(title="Información Financiera")
        
        datos_financieros = {
            'Campo': [
                'Ingresos Mensuales', 'Costos y Gastos Mensuales', 'Otros Ingresos', 'Total Ingresos',
                'Activos', 'Pasivos', 'Patrimonio', 'Actividad Económica Principal',
                'Código CIIU', 'Detalle Otros Ingresos'
            ],
            'Valor': [
                tercero.ingreso_mensual or '',
                tercero.costos_gastos_mensuales or '',
                tercero.otros_ingresos or '',
                tercero.total_ingresos or '',
                tercero.activos or '',
                tercero.pasivos or '',
                tercero.patrimonio or '',
                tercero.actividad_economica_principal or '',
                tercero.codigo_ciiu or '',
                tercero.detalle_otros_ingresos or ''
            ]
        }
        
        df_financieros = pd.DataFrame(datos_financieros)
        
        for r in dataframe_to_rows(df_financieros, index=False, header=True):
            ws_financiera.append(r)
        
        # Aplicar estilos
        for cell in ws_financiera[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        ws_financiera.column_dimensions['A'].width = 30
        ws_financiera.column_dimensions['B'].width = 30
        
        # ===== HOJA 3: INFORMACIÓN PEP =====
        ws_pep = wb.create_sheet(title="Información PEP")
        
        try:
            info_pep = tercero.informacion_pep
            datos_pep = {
                'Campo': [
                    'Es PEP', 'Cargo/Función', 'Entidad', 'Período', 'Observaciones'
                ],
                'Valor': [
                    'Sí' if info_pep.es_pep else 'No',
                    info_pep.cargo_funcion or '',
                    info_pep.entidad or '',
                    info_pep.periodo or '',
                    info_pep.observaciones or ''
                ]
            }
        except:
            datos_pep = {
                'Campo': ['Es PEP'],
                'Valor': ['No registrado']
            }
        
        df_pep = pd.DataFrame(datos_pep)
        
        for r in dataframe_to_rows(df_pep, index=False, header=True):
            ws_pep.append(r)
        
        # Aplicar estilos
        for cell in ws_pep[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        ws_pep.column_dimensions['A'].width = 30
        ws_pep.column_dimensions['B'].width = 50
        
        # ===== HOJA 4: REPRESENTANTES LEGALES =====
        ws_representantes = wb.create_sheet(title="Representantes Legales")
        
        representantes = tercero.representantes_legales.all()
        
        if representantes.exists():
            datos_repr = []
            for repr_legal in representantes:
                datos_repr.append({
                    'Documento': repr_legal.numero_documento,
                    'Tipo Documento': repr_legal.get_tipo_documento_display(),
                    'Nombres': repr_legal.nombres,
                    'Apellidos': repr_legal.apellidos,
                    'Email': repr_legal.email or '',
                    'Teléfono': repr_legal.telefono or '',
                    'Cargo': repr_legal.cargo or '',
                    'Fecha Inicio': repr_legal.fecha_inicio_cargo.strftime('%Y-%m-%d') if repr_legal.fecha_inicio_cargo else '',
                    'Fecha Fin': repr_legal.fecha_fin_cargo.strftime('%Y-%m-%d') if repr_legal.fecha_fin_cargo else ''
                })
            
            df_repr = pd.DataFrame(datos_repr)
        else:
            df_repr = pd.DataFrame({'Información': ['No hay representantes legales registrados']})
        
        for r in dataframe_to_rows(df_repr, index=False, header=True):
            ws_representantes.append(r)
        
        # Aplicar estilos
        for cell in ws_representantes[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # Ajustar anchos de columnas
        for column in ws_representantes.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws_representantes.column_dimensions[column_letter].width = adjusted_width
        
        # ===== HOJA 5: ACCIONISTAS =====
        ws_accionistas = wb.create_sheet(title="Accionistas")
        
        accionistas = tercero.accionistas.all()
        
        if accionistas.exists():
            datos_acc = []
            for accionista in accionistas:
                datos_acc.append({
                    'Documento': accionista.numero_documento,
                    'Tipo Documento': accionista.get_tipo_documento_display(),
                    'Nombres': accionista.nombres,
                    'Apellidos': accionista.apellidos,
                    'Email': accionista.email or '',
                    'Teléfono': accionista.telefono or '',
                    'Porcentaje Participación': f"{accionista.porcentaje_participacion}%" if accionista.porcentaje_participacion else ''
                })
            
            df_acc = pd.DataFrame(datos_acc)
        else:
            df_acc = pd.DataFrame({'Información': ['No hay accionistas registrados']})
        
        for r in dataframe_to_rows(df_acc, index=False, header=True):
            ws_accionistas.append(r)
        
        # Aplicar estilos
        for cell in ws_accionistas[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # Ajustar anchos de columnas
        for column in ws_accionistas.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws_accionistas.column_dimensions[column_letter].width = adjusted_width
        
        # ===== HOJA 6: RESUMEN DOCUMENTOS =====
        ws_docs = wb.create_sheet(title="Resumen Documentos")
        
        documentos = tercero.documentos.all()
        
        if documentos.exists():
            datos_docs = []
            for doc in documentos:
                datos_docs.append({
                    'Nombre': doc.nombre_original,
                    'Tipo': doc.get_tipo_documento_display(),
                    'Tamaño (KB)': round(doc.tamano_archivo / 1024, 2) if doc.tamano_archivo else 0,
                    'Fecha Subida': doc.fecha_subida.strftime('%Y-%m-%d %H:%M:%S'),
                    'Vigente': 'Sí' if doc.es_vigente else 'No',
                    'Fecha Vencimiento': doc.fecha_vencimiento.strftime('%Y-%m-%d') if doc.fecha_vencimiento else 'No aplica'
                })
            
            df_docs = pd.DataFrame(datos_docs)
        else:
            df_docs = pd.DataFrame({'Información': ['No hay documentos registrados']})
        
        for r in dataframe_to_rows(df_docs, index=False, header=True):
            ws_docs.append(r)
        
        # Aplicar estilos
        for cell in ws_docs[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # Ajustar anchos de columnas
        for column in ws_docs.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws_docs.column_dimensions[column_letter].width = adjusted_width
        
        # Preparar respuesta con el archivo Excel
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        nombre_archivo = f"tercero_{tercero.numero_documento}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        
        # Guardar el archivo en memoria y escribirlo a la respuesta
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        response.write(excel_file.getvalue())
        
        logger.info(f"Archivo Excel generado exitosamente: {nombre_archivo}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error exportando tercero a Excel: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
