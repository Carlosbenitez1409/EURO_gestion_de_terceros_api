from django.shortcuts import render

# usuarios_consultas/views.py
"""
Views para el Sistema de Usuarios GH (Consultas de Personal)
Implementación según API_SPECIFICATION_USUARIOS_GH.md
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

from .models import Solicitud, Persona, HistorialCambio, EstadoSolicitud
from .serializers import (
    SolicitudListSerializer, SolicitudDetalleSerializer, SolicitudCreacionSerializer,
    SolicitudEdicionSerializer, PersonaSerializer, PersonaCreacionSerializer,
    HistorialCambioSerializer, CambioEstadoSerializer, EstadisticasSerializer
)
from .permissions import UsuariosGHPermission
from stradata_consulta.service import StrataDataService


class SolicitudFilter(django_filters.FilterSet):
    """Filtro personalizado para solicitudes que maneja múltiples estados como OR"""
    
    class Meta:
        model = Solicitud
        fields = ['creada_por', 'asignada_a']
    
    @property
    def qs(self):
        """Override qs property to handle multiple estado parameters"""
        # Get the base filtered queryset
        queryset = super().qs
        
        # Handle multiple estado parameters manually
        request = getattr(self, 'request', None)
        data = getattr(self, 'data', None)
        
        if request and hasattr(request, 'query_params'):
            # DRF Request object
            estados = request.query_params.getlist('estado')
        elif request and hasattr(request, 'GET'):
            # Django Request object  
            estados = request.GET.getlist('estado')
        elif data and hasattr(data, 'getlist'):
            # QueryDict object
            estados = data.getlist('estado')
        elif data and 'estado' in data:
            # Regular dict
            estado_value = data.get('estado')
            estados = [estado_value] if estado_value else []
        else:
            estados = []
        
        # Apply estado filter if we have estado parameters
        if estados:
            from django.db.models import Q
            q_objects = Q()
            for estado in estados:
                if estado:  # Skip empty values
                    q_objects |= Q(estado=estado)
            
            if q_objects:
                queryset = queryset.filter(q_objects)
        
        return queryset


class SolicitudViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de solicitudes con endpoints personalizados
    """
    permission_classes = [IsAuthenticated, UsuariosGHPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SolicitudFilter
    search_fields = ['observaciones_generales', 'personas__nombres_apellidos', 'personas__numero_documento']
    ordering_fields = ['fecha_creacion', 'fecha_ultima_actualizacion', 'estado']
    ordering = ['-fecha_creacion']
    
    def get_queryset(self):
        """Filtrar solicitudes según rol del usuario"""
        user = self.request.user
        queryset = Solicitud.objects.select_related('creada_por', 'asignada_a').prefetch_related(
            'personas', 'historial_cambios__usuario'
        )
        
        if not hasattr(user, 'role'):
            return queryset.none()
        
        role = user.role
        
        if role == 'gestion_humana':
            # GH ve sus propias solicitudes
            return queryset.filter(creada_por=user)
        elif role == 'administrador':
            # Admin ve solicitudes asignadas a administradores y las suyas asignadas
            return queryset.filter(
                Q(estado__in=[EstadoSolicitud.ASIGNADA_ADMINISTRADOR, EstadoSolicitud.EN_REVISION_ADMINISTRADOR]) |
                Q(asignada_a=user)
            )
        elif role == 'procesos':
            # Procesos ve solicitudes asignadas a procesos y las suyas asignadas
            return queryset.filter(
                Q(estado__in=[EstadoSolicitud.ASIGNADA_PROCESOS, EstadoSolicitud.EN_REVISION_PROCESOS]) |
                Q(asignada_a=user)
            )
        
        return queryset.none()
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'list':
            return SolicitudListSerializer
        elif self.action == 'create':
            return SolicitudCreacionSerializer
        elif self.action in ['update', 'partial_update']:
            return SolicitudEdicionSerializer
        else:
            return SolicitudDetalleSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear nueva solicitud (solo GH)"""
        if not hasattr(request.user, 'role') or request.user.role != 'gestion_humana':
            return Response(
                {'error': 'Solo Gestión Humana puede crear solicitudes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        solicitud = serializer.save()
        
        # Registrar en historial
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=request.user,
            accion='Solicitud creada',
            descripcion=f'Nueva solicitud con {solicitud.total_personas} persona(s)'
        )
        
        # Retornar detalle completo
        response_serializer = SolicitudDetalleSerializer(solicitud, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Endpoint para cambiar estado de solicitud"""
        solicitud = self.get_object()
        serializer = CambioEstadoSerializer(
            data=request.data,
            context={'request': request, 'solicitud': solicitud}
        )
        serializer.is_valid(raise_exception=True)
        
        # Aplicar cambio
        estado_anterior = solicitud.estado
        nuevo_estado = serializer.validated_data['nuevo_estado']
        comentario = serializer.validated_data.get('comentario', '')
        asignar_a = serializer.validated_data.get('asignar_a')
        
        solicitud.estado = nuevo_estado
        
        # Asignar usuario si se proporciona
        if asignar_a:
            solicitud.asignada_a = asignar_a
        elif nuevo_estado in [EstadoSolicitud.EN_REVISION_ADMINISTRADOR, EstadoSolicitud.EN_REVISION_PROCESOS]:
            # Auto-asignar al usuario actual cuando toma para revisión
            solicitud.asignada_a = request.user
        
        solicitud.save()
        
        # Registrar cambio en historial
        accion = f'Cambio de estado: {estado_anterior} → {nuevo_estado}'
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=request.user,
            accion=accion,
            descripcion=comentario,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado
        )
        
        # Retornar solicitud actualizada
        response_serializer = SolicitudDetalleSerializer(solicitud, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def tomar_revision(self, request, pk=None):
        """Endpoint para que Admin/Procesos tomen solicitud para revisión"""
        solicitud = self.get_object()
        
        if not solicitud.puede_tomar_revision(request.user):
            return Response(
                {'error': 'No puede tomar esta solicitud para revisión'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cambiar estado según el rol y asignar
        estado_anterior = solicitud.estado
        user_role = getattr(request.user, 'role', None)
        
        if user_role == 'administrador':
            solicitud.estado = EstadoSolicitud.EN_REVISION_ADMINISTRADOR
        elif user_role == 'procesos':
            solicitud.estado = EstadoSolicitud.EN_REVISION_PROCESOS
        else:
            return Response(
                {'error': 'Solo administradores y procesos pueden tomar solicitudes'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        solicitud.asignada_a = request.user
        solicitud.save()
        
        # Registrar en historial
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=request.user,
            accion='Solicitud tomada para revisión',
            descripcion=f'Asignada a {request.user.get_full_name() or request.user.username}',
            estado_anterior=estado_anterior,
            estado_nuevo=solicitud.estado
        )
        
        response_serializer = SolicitudDetalleSerializer(solicitud, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[])
    def asignar(self, request, pk=None):
        """Endpoint para asignar solicitud a un usuario específico"""
        from accounts.models import User
        import logging
        
        # Verificación manual de autenticación
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Usuario no autenticado'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        logger = logging.getLogger(__name__)
        logger.info(f"ASIGNAR - Request data: {request.data}")
        logger.info(f"ASIGNAR - User: {request.user.username}")
        
        # Obtener la solicitud directamente sin filtros de permisos
        try:
            solicitud = Solicitud.objects.get(id=pk)
        except Solicitud.DoesNotExist:
            return Response(
                {'error': 'Solicitud no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        usuario_id = request.data.get('usuario_id')
        
        # Intentar diferentes formas de obtener el usuario_id (incluyendo el formato del frontend)
        if not usuario_id:
            usuario_id = request.data.get('asignada_a')  # El frontend envía asignada_a
        if not usuario_id:
            usuario_id = request.data.get('usuarioId')  # camelCase
        if not usuario_id:
            usuario_id = request.data.get('id')  # simple id
        
        logger.info(f"ASIGNAR - usuario_id encontrado: {usuario_id}")
        
        if not usuario_id:
            return Response(
                {'error': 'Se requiere usuario_id o asignada_a', 'debug_data': dict(request.data)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            usuario_asignado = User.objects.get(id=usuario_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar permisos - solo GH puede asignar inicialmente, Admin/Procesos pueden reasignar
        user_role = getattr(request.user, 'role', None)
        target_role = getattr(usuario_asignado, 'role', None)
        
        if user_role == 'gestion_humana':
            # GH puede asignar a admin o procesos
            if target_role not in ['administrador', 'procesos']:
                return Response(
                    {'error': 'GH solo puede asignar a administradores o procesos'},
                    status=status.HTTP_403_FORBIDDEN
                )
            if solicitud.estado != EstadoSolicitud.CREADA:
                return Response(
                    {'error': 'Solo se pueden asignar solicitudes en estado CREADA'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user_role in ['administrador', 'procesos']:
            # Admin/Procesos pueden reasignar dentro de su flujo
            if not solicitud.puede_tomar_revision(request.user):
                return Response(
                    {'error': 'No puede asignar esta solicitud'},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {'error': 'No tiene permisos para asignar solicitudes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cambiar estado según el usuario asignado
        estado_anterior = solicitud.estado
        
        if target_role == 'administrador':
            if solicitud.estado == EstadoSolicitud.CREADA:
                solicitud.estado = EstadoSolicitud.ASIGNADA_ADMINISTRADOR
            else:
                solicitud.estado = EstadoSolicitud.EN_REVISION_ADMINISTRADOR
        elif target_role == 'procesos':
            if solicitud.estado in [EstadoSolicitud.CREADA, EstadoSolicitud.EN_REVISION_ADMINISTRADOR]:
                solicitud.estado = EstadoSolicitud.ASIGNADA_PROCESOS
            else:
                solicitud.estado = EstadoSolicitud.EN_REVISION_PROCESOS
        
        solicitud.asignada_a = usuario_asignado
        solicitud.save()
        
        # Registrar en historial
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=request.user,
            accion='Solicitud asignada',
            descripcion=f'Asignada a {usuario_asignado.get_full_name() or usuario_asignado.username}',
            estado_anterior=estado_anterior,
            estado_nuevo=solicitud.estado
        )
        
        response_serializer = SolicitudDetalleSerializer(solicitud, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def consultar_stradata(self, request, pk=None):
        """Endpoint para que Admin/Procesos consulten personas en Stradata"""
        solicitud = self.get_object()
        
        # Verificar permisos: solo Admin y Procesos pueden consultar Stradata
        user_role = getattr(request.user, 'role', None)
        if user_role not in ['administrador', 'procesos']:
            return Response(
                {'error': 'Solo administradores y procesos pueden consultar Stradata'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar que la solicitud esté asignada al usuario
        if solicitud.asignada_a != request.user:
            return Response(
                {'error': 'Solo puede consultar Stradata para solicitudes asignadas a usted'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Obtener personas a consultar
        persona_id = request.data.get('persona_id')
        consultar_solo_una = request.data.get('consultar_solo_una', False)
        
        if persona_id and consultar_solo_una:
            # Consultar una persona específica (solo si se indica explícitamente)
            try:
                personas_consultar = [Persona.objects.get(id=persona_id, solicitud=solicitud)]
                logger.info(f"CONSULTAR_STRADATA - Modo: consulta individual de persona {persona_id}")
            except Persona.DoesNotExist:
                return Response(
                    {'error': 'Persona no encontrada en esta solicitud'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Por defecto: Consultar todas las personas de la solicitud
            personas_consultar = list(solicitud.personas.all())
            logger.info(f"CONSULTAR_STRADATA - Modo: consulta masiva de todas las personas")
            
            if not personas_consultar:
                return Response(
                    {'error': 'No hay personas en esta solicitud para consultar'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            logger.info(f"CONSULTAR_STRADATA - Iniciando consulta para {len(personas_consultar)} persona(s) de la solicitud {solicitud.id}")
            
            # Obtener credenciales de Stradata desde request
            username_stradata = request.data.get('username')
            password_stradata = request.data.get('password')
            
            logger.info(f"CONSULTAR_STRADATA - Credenciales recibidas: username={username_stradata}, password={'***' if password_stradata else 'None'}")
            
            if not username_stradata or not password_stradata:
                return Response(
                    {'error': 'Se requieren credenciales de Stradata (username y password)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Inicializar servicio de Stradata
            stradata_service = StrataDataService()
            
            # Autenticar en Stradata
            logger.info("CONSULTAR_STRADATA - Iniciando autenticación en Stradata")
            login_success = stradata_service.login(username_stradata, password_stradata)
            
            if not login_success:
                logger.error("CONSULTAR_STRADATA - Error de autenticación en Stradata")
                return Response(
                    {'error': 'Error de autenticación en Stradata. Verifique las credenciales.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            logger.info("CONSULTAR_STRADATA - Autenticación exitosa")
            
            # Preparar lista de personas para consulta - formato directo para Stradata
            # Mapear tipo de documento al formato esperado por Stradata CSV
            tipo_doc_mapping = {
                'CC': 'C',  # Cédula
                'CE': 'E',  # Cédula Extranjería 
                'PP': 'P',  # Pasaporte
                'TI': 'C'   # TI se mapea como Cédula
            }
            
            personas_consulta = []
            for persona in personas_consultar:
                personas_consulta.append({
                    'nombre': persona.nombres_apellidos,
                    'identificacion': persona.numero_documento,
                    'tipo': tipo_doc_mapping.get(persona.tipo_documento, 'C')  # Por defecto Cédula
                })
                logger.info(f"CONSULTAR_STRADATA - Agregada persona: {persona.nombres_apellidos} - {persona.numero_documento}")
            
            # Realizar consulta real en Stradata usando el método directo
            logger.info(f"CONSULTAR_STRADATA - Ejecutando consulta con {len(personas_consulta)} persona(s): {personas_consulta}")
            resultado_stradata = stradata_service.ejecutar_consulta_personas(
                personas_consulta, 
                username_stradata
            )
            
            logger.info(f"CONSULTAR_STRADATA - Resultado de consulta: {resultado_stradata}")
            
            # Cerrar sesión
            stradata_service.close_session()
            
            # Formatear respuesta para el frontend
            if resultado_stradata.get('success'):
                resultado_consulta = {
                    'solicitud_id': str(solicitud.id),
                    'personas_consultadas': [
                        {
                            'nombres_apellidos': p.nombres_apellidos,
                            'numero_documento': p.numero_documento,
                            'tipo_documento': p.tipo_documento
                        } for p in personas_consultar
                    ],
                    'consulta_realizada': True,
                    'fecha_consulta': timezone.now().isoformat(),
                    'usuario_consulta': request.user.username,
                    'resultados': {
                        'consulta_exitosa': True,
                        'total_personas': len(personas_consultar),
                        'detalles': resultado_stradata.get('message', 'Consulta ejecutada exitosamente'),
                        'datos_stradata': resultado_stradata.get('data', {}),
                        'personas_consultadas_count': resultado_stradata.get('data', {}).get('personas_consultadas', 0),
                        'id_busqueda': resultado_stradata.get('data', {}).get('id_busqueda'),
                        'codigo_busqueda': resultado_stradata.get('data', {}).get('codigo_busqueda'),
                        'servicios_consultados': resultado_stradata.get('data', {}).get('servicios', {}),
                        'resumen_servicios': resultado_stradata.get('data', {}).get('resumen_servicios', {})
                    }
                }
            else:
                resultado_consulta = {
                    'solicitud_id': str(solicitud.id),
                    'personas_consultadas': [
                        {
                            'nombres_apellidos': p.nombres_apellidos,
                            'numero_documento': p.numero_documento,
                            'tipo_documento': p.tipo_documento
                        } for p in personas_consultar
                    ],
                    'consulta_realizada': False,
                    'fecha_consulta': timezone.now().isoformat(),
                    'usuario_consulta': request.user.username,
                    'resultados': {
                        'consulta_exitosa': False,
                        'total_personas': len(personas_consultar),
                        'error': resultado_stradata.get('error', 'Error desconocido en consulta Stradata'),
                        'detalles': 'La consulta no pudo completarse exitosamente'
                    }
                }
            
            # Registrar la consulta en el historial
            if len(personas_consultar) == 1:
                descripcion = f'Consultada persona: {personas_consultar[0].nombres_apellidos} - {personas_consultar[0].numero_documento}'
            else:
                nombres_personas = [f"{p.nombres_apellidos} ({p.numero_documento})" for p in personas_consultar]
                descripcion = f'Consultadas {len(personas_consultar)} personas: {", ".join(nombres_personas)}'
            
            HistorialCambio.registrar_cambio(
                solicitud=solicitud,
                usuario=request.user,
                accion='Consulta Stradata realizada',
                descripcion=descripcion,
                estado_anterior=solicitud.estado,
                estado_nuevo=solicitud.estado
            )
            
            return Response(resultado_consulta)
            
        except Exception as e:
            logger.error(f"Error en consulta Stradata: {str(e)}")
            return Response(
                {'error': f'Error al consultar Stradata: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def get_persona(self, request, pk=None, persona_id=None):
        """Obtener detalle de una persona específica dentro de una solicitud"""
        solicitud = self.get_object()
        
        try:
            persona = Persona.objects.get(id=persona_id, solicitud=solicitud)
        except Persona.DoesNotExist:
            return Response(
                {'error': 'Persona no encontrada en esta solicitud'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PersonaSerializer(persona, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch', 'put'])
    def update_persona(self, request, pk=None, persona_id=None):
        """Actualizar una persona específica dentro de una solicitud"""
        try:
            logger.info(f"UPDATE_PERSONA - PK: {pk}, persona_id: {persona_id}")
            logger.info(f"UPDATE_PERSONA - Request data: {request.data}")
            logger.info(f"UPDATE_PERSONA - User: {request.user.username}")
            
            solicitud = self.get_object()
            logger.info(f"UPDATE_PERSONA - Solicitud encontrada: {solicitud.id}")
            
            try:
                persona = Persona.objects.get(id=persona_id, solicitud=solicitud)
                logger.info(f"UPDATE_PERSONA - Persona encontrada: {persona.nombres_apellidos}")
            except Persona.DoesNotExist:
                logger.error(f"UPDATE_PERSONA - Persona no encontrada: {persona_id}")
                return Response(
                    {'error': 'Persona no encontrada en esta solicitud'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            logger.error(f"UPDATE_PERSONA - Error inicial: {str(e)}")
            return Response(
                {'error': f'Error al procesar solicitud: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Verificar permisos de edición
        user_role = getattr(request.user, 'role', None)
        
        # Solo usuarios autorizados pueden editar personas
        if user_role not in ['gestion_humana', 'administrador', 'procesos']:
            return Response(
                {'error': 'No tiene permisos para editar esta persona'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Para editar antecedentes y riesgo, debe ser Admin o Procesos
        if ('antecedentes' in request.data or 'riesgo' in request.data) and user_role not in ['administrador', 'procesos']:
            return Response(
                {'error': 'Solo administradores y procesos pueden editar antecedentes y riesgo'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Serializar y validar
            logger.info(f"UPDATE_PERSONA - Creando serializer")
            serializer = PersonaSerializer(
                persona, 
                data=request.data, 
                partial=True,  # Permitir actualizaciones parciales
                context={'request': request}
            )
            
            logger.info(f"UPDATE_PERSONA - Validando serializer")
            if serializer.is_valid():
                logger.info(f"UPDATE_PERSONA - Serializer válido, guardando")
                persona_actualizada = serializer.save()
                
                # Registrar cambio en historial
                try:
                    campos_editados = list(request.data.keys())
                    logger.info(f"UPDATE_PERSONA - Registrando en historial: {campos_editados}")
                    HistorialCambio.registrar_cambio(
                        solicitud=solicitud,
                        usuario=request.user,
                        accion='Persona actualizada',
                        descripcion=f'Campos editados: {", ".join(campos_editados)} para {persona.nombres_apellidos}',
                        estado_anterior=solicitud.estado,
                        estado_nuevo=solicitud.estado
                    )
                    logger.info(f"UPDATE_PERSONA - Historial registrado exitosamente")
                except Exception as hist_error:
                    logger.error(f"UPDATE_PERSONA - Error en historial: {str(hist_error)}")
                    # Continuar aunque falle el historial
                
                logger.info(f"UPDATE_PERSONA - Retornando respuesta exitosa")
                return Response(serializer.data)
            else:
                logger.error(f"UPDATE_PERSONA - Errores de validación: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"UPDATE_PERSONA - Error en serialización: {str(e)}")
            return Response(
                {'error': f'Error al actualizar persona: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def mis_solicitudes(self, request):
        """Endpoint para obtener solicitudes del usuario actual"""
        user = request.user
        if hasattr(user, 'role') and user.role == 'gestion_humana':
            queryset = self.get_queryset().filter(creada_por=user)
        else:
            queryset = self.get_queryset().filter(asignada_a=user)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SolicitudListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = SolicitudListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Endpoint para estadísticas del dashboard"""
        user = request.user
        queryset = self.get_queryset()
        
        # Estadísticas básicas
        total_solicitudes = queryset.count()
        
        # Solicitudes por estado
        solicitudes_por_estado = dict(
            queryset.values('estado').annotate(count=Count('id')).values_list('estado', 'count')
        )
        
        # Solicitudes asignadas al usuario actual
        solicitudes_asignadas = queryset.filter(asignada_a=user).count()
        
        # Solicitudes creadas por el usuario (solo para GH)
        solicitudes_creadas = 0
        if hasattr(user, 'role') and user.role == 'gestion_humana':
            solicitudes_creadas = queryset.filter(creada_por=user).count()
        
        # Promedio de tiempo de procesamiento (solicitudes finalizadas)
        solicitudes_finalizadas = queryset.filter(estado=EstadoSolicitud.FINALIZADA)
        promedio_tiempo = 0
        if solicitudes_finalizadas.exists():
            tiempos = []
            for sol in solicitudes_finalizadas:
                tiempo = (sol.fecha_ultima_actualizacion - sol.fecha_creacion).total_seconds() / 86400  # días
                tiempos.append(tiempo)
            promedio_tiempo = sum(tiempos) / len(tiempos) if tiempos else 0
        
        data = {
            'total_solicitudes': total_solicitudes,
            'solicitudes_por_estado': solicitudes_por_estado,
            'solicitudes_asignadas_a_mi': solicitudes_asignadas,
            'solicitudes_creadas_por_mi': solicitudes_creadas,
            'promedio_tiempo_procesamiento': round(promedio_tiempo, 2)
        }
        
        serializer = EstadisticasSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Finalizar una solicitud - cambiar estado a FINALIZADA"""
        solicitud = self.get_object()
        
        # Verificar permisos: solo Admin y Procesos pueden finalizar
        user_role = getattr(request.user, 'role', None)
        if user_role not in ['administrador', 'procesos']:
            return Response(
                {'error': 'Solo administradores y procesos pueden finalizar solicitudes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar que la solicitud esté asignada al usuario
        if solicitud.asignada_a != request.user:
            return Response(
                {'error': 'Solo puede finalizar solicitudes asignadas a usted'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar estados válidos para finalización
        estados_validos = [
            EstadoSolicitud.EN_REVISION_ADMINISTRADOR,
            EstadoSolicitud.EN_REVISION_PROCESOS
        ]
        
        if solicitud.estado not in estados_validos:
            return Response(
                {'error': f'No se puede finalizar una solicitud en estado {solicitud.get_estado_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado
        estado_anterior = solicitud.estado
        solicitud.estado = EstadoSolicitud.FINALIZADA
        solicitud.save()
        
        # Registrar en historial
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=request.user,
            accion='Solicitud finalizada',
            descripcion=f'Solicitud finalizada por {request.user.get_full_name() or request.user.username}',
            estado_anterior=estado_anterior,
            estado_nuevo=solicitud.estado
        )
        
        response_serializer = SolicitudDetalleSerializer(solicitud, context={'request': request})
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def devolver_gh(self, request, pk=None):
        """Devolver una solicitud a Gestión Humana - cambiar estado a DEVUELTA_GH"""
        solicitud = self.get_object()
        
        # Verificar permisos: solo Admin y Procesos pueden devolver a GH
        user_role = getattr(request.user, 'role', None)
        if user_role not in ['administrador', 'procesos']:
            return Response(
                {'error': 'Solo administradores y procesos pueden devolver solicitudes a GH'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar que la solicitud esté asignada al usuario
        if solicitud.asignada_a != request.user:
            return Response(
                {'error': 'Solo puede devolver solicitudes asignadas a usted'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar estados válidos para devolución
        estados_validos = [
            EstadoSolicitud.EN_REVISION_ADMINISTRADOR,
            EstadoSolicitud.EN_REVISION_PROCESOS
        ]
        
        if solicitud.estado not in estados_validos:
            return Response(
                {'error': f'No se puede devolver una solicitud en estado {solicitud.get_estado_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener observaciones/motivo de la devolución
        observaciones = request.data.get('observaciones', '')
        
        # Cambiar estado y limpiar asignación
        estado_anterior = solicitud.estado
        solicitud.estado = EstadoSolicitud.DEVUELTA_GH
        solicitud.asignada_a = None  # Se desasigna para que GH pueda tomar la solicitud
        
        # Si hay observaciones, agregarlas a las observaciones generales
        if observaciones:
            if solicitud.observaciones_generales:
                solicitud.observaciones_generales += f"\n\nDevuelta por {request.user.get_full_name() or request.user.username}: {observaciones}"
            else:
                solicitud.observaciones_generales = f"Devuelta por {request.user.get_full_name() or request.user.username}: {observaciones}"
        
        solicitud.save()
        
        # Registrar en historial
        descripcion = f'Solicitud devuelta a GH por {request.user.get_full_name() or request.user.username}'
        if observaciones:
            descripcion += f'. Motivo: {observaciones}'
            
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=request.user,
            accion='Solicitud devuelta a GH',
            descripcion=descripcion,
            estado_anterior=estado_anterior,
            estado_nuevo=solicitud.estado
        )
        
        response_serializer = SolicitudDetalleSerializer(solicitud, context={'request': request})
        return Response(response_serializer.data)


class PersonaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de personas dentro de solicitudes
    """
    serializer_class = PersonaSerializer
    permission_classes = [IsAuthenticated, UsuariosGHPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombres_apellidos', 'numero_documento']
    ordering_fields = ['orden', 'nombres_apellidos', 'fecha_creacion']
    ordering = ['orden']
    
    def get_queryset(self):
        """Filtrar personas según acceso a solicitudes"""
        user = self.request.user
        if not hasattr(user, 'role'):
            return Persona.objects.none()
        
        # Filtrar por solicitudes a las que el usuario tiene acceso
        solicitudes_accesibles = Solicitud.objects.filter(
            id__in=SolicitudViewSet().get_queryset().values_list('id', flat=True)
        )
        
        return Persona.objects.filter(
            solicitud__in=solicitudes_accesibles
        ).select_related('solicitud')
    
    def get_serializer_class(self):
        """Usar serializer de creación si es necesario"""
        if self.action == 'create':
            return PersonaCreacionSerializer
        return PersonaSerializer
    
    def perform_create(self, serializer):
        """Registrar cambio al agregar persona"""
        persona = serializer.save()
        
        # Registrar en historial de la solicitud
        HistorialCambio.registrar_cambio(
            solicitud=persona.solicitud,
            usuario=self.request.user,
            accion='Persona agregada',
            descripcion=f'Agregada persona: {persona.nombres_apellidos} ({persona.tipo_documento} {persona.numero_documento})'
        )
    
    def perform_update(self, serializer):
        """Registrar cambio al modificar persona"""
        persona_anterior = self.get_object()
        persona = serializer.save()
        
        # Comparar cambios significativos
        cambios = []
        if persona_anterior.nombres_apellidos != persona.nombres_apellidos:
            cambios.append(f'Nombre: {persona_anterior.nombres_apellidos} → {persona.nombres_apellidos}')
        if persona_anterior.antecedentes != persona.antecedentes:
            cambios.append('Antecedentes actualizados')
        if persona_anterior.riesgo != persona.riesgo:
            cambios.append(f'Riesgo: {persona_anterior.riesgo or "Sin asignar"} → {persona.riesgo or "Sin asignar"}')
        
        if cambios:
            HistorialCambio.registrar_cambio(
                solicitud=persona.solicitud,
                usuario=self.request.user,
                accion='Persona modificada',
                descripcion=f'Persona {persona.nombres_apellidos}: {", ".join(cambios)}'
            )
    
    def perform_destroy(self, instance):
        """Registrar cambio al eliminar persona"""
        solicitud = instance.solicitud
        nombre = instance.nombres_apellidos
        documento = f"{instance.tipo_documento} {instance.numero_documento}"
        
        # Eliminar persona
        instance.delete()
        
        # Registrar en historial
        HistorialCambio.registrar_cambio(
            solicitud=solicitud,
            usuario=self.request.user,
            accion='Persona eliminada',
            descripcion=f'Eliminada persona: {nombre} ({documento})'
        )


class HistorialCambioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para historial de cambios
    """
    serializer_class = HistorialCambioSerializer
    permission_classes = [IsAuthenticated, UsuariosGHPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['solicitud', 'usuario', 'accion']
    ordering_fields = ['fecha_cambio']
    ordering = ['-fecha_cambio']
    
    def get_queryset(self):
        """Filtrar historial según acceso a solicitudes"""
        user = self.request.user
        if not hasattr(user, 'role'):
            return HistorialCambio.objects.none()
        
        # Filtrar por solicitudes a las que el usuario tiene acceso
        solicitudes_accesibles = Solicitud.objects.filter(
            id__in=SolicitudViewSet().get_queryset().values_list('id', flat=True)
        )
        
        return HistorialCambio.objects.filter(
            solicitud__in=solicitudes_accesibles
        ).select_related('solicitud', 'usuario')


# Views adicionales para endpoints específicos

from rest_framework.views import APIView
from django.contrib.auth import get_user_model

User = get_user_model()


class DescargarReporteView(APIView):
    """
    Vista para descarga de reportes en diferentes formatos
    """
    permission_classes = [IsAuthenticated, UsuariosGHPermission]
    
    def get(self, request, *args, **kwargs):
        """Generar y descargar reporte"""
        formato = request.query_params.get('formato', 'excel')  # excel, pdf, csv
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        estado = request.query_params.get('estado')
        
        # Filtrar solicitudes
        queryset = SolicitudViewSet().get_queryset()
        
        if fecha_inicio:
            try:
                fecha_inicio = timezone.datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                queryset = queryset.filter(fecha_creacion__gte=fecha_inicio)
            except ValueError:
                pass
        
        if fecha_fin:
            try:
                fecha_fin = timezone.datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                queryset = queryset.filter(fecha_creacion__lte=fecha_fin)
            except ValueError:
                pass
        
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Por ahora, retornar datos JSON (implementar generación de archivos después)
        solicitudes = SolicitudListSerializer(queryset, many=True, context={'request': request})
        
        return Response({
            'mensaje': f'Reporte en formato {formato} generado',
            'total_registros': queryset.count(),
            'datos': solicitudes.data
        })


class ValidarPersonaView(APIView):
    """
    Vista para validar datos de persona antes de crear
    """
    permission_classes = [IsAuthenticated, UsuariosGHPermission]
    
    def post(self, request, *args, **kwargs):
        """Validar datos de persona"""
        tipo_documento = request.data.get('tipo_documento')
        numero_documento = request.data.get('numero_documento')
        solicitud_id = request.data.get('solicitud_id')
        
        if not all([tipo_documento, numero_documento]):
            return Response(
                {'error': 'Tipo y número de documento son obligatorios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar si ya existe en la solicitud
        duplicado_en_solicitud = False
        if solicitud_id:
            try:
                solicitud = Solicitud.objects.get(id=solicitud_id)
                duplicado_en_solicitud = solicitud.personas.filter(
                    tipo_documento=tipo_documento,
                    numero_documento=numero_documento
                ).exists()
            except Solicitud.DoesNotExist:
                pass
        
        # Verificar si existe en otras solicitudes (para información)
        existe_en_sistema = Persona.objects.filter(
            tipo_documento=tipo_documento,
            numero_documento=numero_documento
        ).exists()
        
        return Response({
            'valido': not duplicado_en_solicitud,
            'duplicado_en_solicitud': duplicado_en_solicitud,
            'existe_en_sistema': existe_en_sistema,
            'mensaje': 'Datos válidos' if not duplicado_en_solicitud else 'Documento duplicado en la solicitud'
        })


from rest_framework.views import APIView

class RootRedirectView(APIView):
    """
    Vista personalizada para manejar peticiones a la raíz /usuarios-consultas/
    y redirigirlas al ViewSet de solicitudes para compatibilidad con frontend
    """
    permission_classes = [IsAuthenticated, UsuariosGHPermission]

    def get(self, request):
        """Delegar GET requests al ViewSet de solicitudes"""
        # Crear una instancia del ViewSet y ejecutar la acción list
        solicitud_viewset = SolicitudViewSet()
        solicitud_viewset.request = request
        solicitud_viewset.format_kwarg = None
        solicitud_viewset.args = ()
        solicitud_viewset.kwargs = {}
        
        # Ejecutar la acción list del ViewSet
        return solicitud_viewset.list(request)


class PersonaUpdateView(APIView):
    """
    Vista para actualizar personas específicas dentro de solicitudes
    """
    permission_classes = [IsAuthenticated, UsuariosGHPermission]
    
    def get(self, request, pk, persona_id):
        """Obtener detalle de una persona específica"""
        try:
            logger.info(f"GET_PERSONA - PK: {pk}, persona_id: {persona_id}")
            solicitud = Solicitud.objects.get(id=pk)
            persona = Persona.objects.get(id=persona_id, solicitud=solicitud)
            serializer = PersonaSerializer(persona, context={'request': request})
            return Response(serializer.data)
        except (Solicitud.DoesNotExist, Persona.DoesNotExist):
            return Response(
                {'error': 'Solicitud o persona no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def patch(self, request, pk, persona_id):
        """Actualizar una persona específica dentro de una solicitud"""
        try:
            logger.info(f"PATCH_PERSONA - PK: {pk}, persona_id: {persona_id}")
            logger.info(f"PATCH_PERSONA - Request data: {request.data}")
            logger.info(f"PATCH_PERSONA - User: {request.user.username}")
            
            # Obtener solicitud y persona
            solicitud = Solicitud.objects.get(id=pk)
            persona = Persona.objects.get(id=persona_id, solicitud=solicitud)
            
            logger.info(f"PATCH_PERSONA - Solicitud: {solicitud.id}, Persona: {persona.nombres_apellidos}")
            
            # Verificar permisos de edición
            user_role = getattr(request.user, 'role', None)
            
            # Solo usuarios autorizados pueden editar personas
            if user_role not in ['gestion_humana', 'administrador', 'procesos']:
                return Response(
                    {'error': 'No tiene permisos para editar esta persona'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Para editar antecedentes y riesgo, debe ser Admin o Procesos
            if ('antecedentes' in request.data or 'riesgo' in request.data) and user_role not in ['administrador', 'procesos']:
                return Response(
                    {'error': 'Solo administradores y procesos pueden editar antecedentes y riesgo'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Serializar y validar
            logger.info(f"PATCH_PERSONA - Creando serializer")
            serializer = PersonaSerializer(
                persona, 
                data=request.data, 
                partial=True,  # Permitir actualizaciones parciales
                context={'request': request}
            )
            
            logger.info(f"PATCH_PERSONA - Validando serializer")
            if serializer.is_valid():
                logger.info(f"PATCH_PERSONA - Serializer válido, guardando")
                persona_actualizada = serializer.save()
                
                # Registrar cambio en historial
                try:
                    campos_editados = list(request.data.keys())
                    logger.info(f"PATCH_PERSONA - Registrando en historial: {campos_editados}")
                    HistorialCambio.registrar_cambio(
                        solicitud=solicitud,
                        usuario=request.user,
                        accion='Persona actualizada',
                        descripcion=f'Campos editados: {", ".join(campos_editados)} para {persona.nombres_apellidos}',
                        estado_anterior=solicitud.estado,
                        estado_nuevo=solicitud.estado
                    )
                    logger.info(f"PATCH_PERSONA - Historial registrado exitosamente")
                except Exception as hist_error:
                    logger.error(f"PATCH_PERSONA - Error en historial: {str(hist_error)}")
                    # Continuar aunque falle el historial
                
                logger.info(f"PATCH_PERSONA - Retornando respuesta exitosa")
                return Response(serializer.data)
            else:
                logger.error(f"PATCH_PERSONA - Errores de validación: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Solicitud.DoesNotExist:
            logger.error(f"PATCH_PERSONA - Solicitud no encontrada: {pk}")
            return Response(
                {'error': 'Solicitud no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Persona.DoesNotExist:
            logger.error(f"PATCH_PERSONA - Persona no encontrada: {persona_id}")
            return Response(
                {'error': 'Persona no encontrada en esta solicitud'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"PATCH_PERSONA - Error general: {str(e)}")
            return Response(
                {'error': f'Error al actualizar persona: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, pk, persona_id):
        """Actualizar completamente una persona (delegamos al PATCH)"""
        return self.patch(request, pk, persona_id)
