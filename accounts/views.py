from rest_framework import generics, status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from .serializers import CustomTokenObtainPairSerializer, UserSerializer, UserCreateSerializer
from .permissions import IsProcesos, IsProcesosOrReadOnly, IsAdministrador, IsOficialCumplimiento
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet para CRUD completo de usuarios del sistema
    - Administrador: Acceso total para gestionar cualquier usuario
    - Procesos: Puede gestionar usuarios normales (no administradores)
    - Otros roles: Solo lectura
    """
    queryset = User.objects.all().order_by('-date_joined')
    
    def get_permissions(self):
        """
        Permisos específicos por acción y rol
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Solo administrador y procesos pueden gestionar usuarios
            permission_classes = [IsProcesosOrReadOnly]
        else:
            # Todos pueden ver usuarios (lista básica)
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar usuarios según el rol del solicitante
        """
        user = self.request.user
        queryset = User.objects.all().order_by('-date_joined')
        
        if hasattr(user, 'role'):
            # Administrador ve todos los usuarios
            if user.role == 'administrador':
                return queryset
            
            # Procesos ve usuarios excepto administradores
            elif user.role == 'procesos':
                return queryset.exclude(role='administrador')
            
            # Oficial de cumplimiento ve usuarios relacionados con cumplimiento
            elif user.role == 'oficial_cumplimiento':
                return queryset.filter(role__in=['comercial', 'procesos', 'oficial_cumplimiento'])
            
            # Otros roles solo ven usuarios básicos
            else:
                return queryset.filter(role__in=['comercial', 'procesos'])
        
        return queryset
    
    def get_serializer_class(self):
        """Usar serializer apropiado según la acción"""
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def perform_create(self, serializer):
        """Crear usuario con validaciones de rol"""
        user = self.request.user
        new_user_role = serializer.validated_data.get('role')
        
        # Solo administradores pueden crear otros administradores
        if new_user_role == 'administrador' and user.role != 'administrador':
            logger.warning(f"Usuario {user.username} intentó crear administrador sin permisos")
            raise permissions.PermissionDenied("Solo administradores pueden crear otros administradores")
        
        # Solo administradores y procesos pueden crear oficiales de cumplimiento
        if new_user_role == 'oficial_cumplimiento' and user.role not in ['administrador', 'procesos']:
            logger.warning(f"Usuario {user.username} intentó crear oficial de cumplimiento sin permisos")
            raise permissions.PermissionDenied("Solo administradores y procesos pueden crear oficiales de cumplimiento")
        
        new_user = serializer.save()
        logger.info(f"Usuario creado: {new_user.username} (rol: {new_user_role}) por {user.username}")
    
    def perform_update(self, serializer):
        """Log de actualización con validaciones"""
        user = self.request.user
        target_user = serializer.instance
        
        # Validar que no se esté intentando modificar un administrador sin permisos
        if target_user.role == 'administrador' and user.role != 'administrador':
            logger.warning(f"Usuario {user.username} intentó modificar administrador {target_user.username}")
            raise permissions.PermissionDenied("Solo administradores pueden modificar otros administradores")
        
        logger.info(f"Usuario {target_user.username} actualizado por {user.username}")
        serializer.save()
    
    def perform_destroy(self, instance):
        """Log de eliminación - soft delete con validaciones"""
        user = self.request.user
        
        # Validar que no se esté intentando eliminar un administrador sin permisos
        if instance.role == 'administrador' and user.role != 'administrador':
            logger.warning(f"Usuario {user.username} intentó eliminar administrador {instance.username}")
            raise permissions.PermissionDenied("Solo administradores pueden eliminar otros administradores")
        
        logger.info(f"Usuario {instance.username} desactivado por {user.username}")
        instance.is_active = False
        instance.save()
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdministrador])
    def usuarios_administradores(self, request):
        """
        Endpoint exclusivo para administradores - ver todos los administradores
        """
        admins = User.objects.filter(role='administrador', is_active=True)
        serializer = UserSerializer(admins, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdministrador])
    def logs_usuarios(self, request):
        """
        Endpoint para ver logs de actividad de usuarios (solo administradores)
        """
        # En producción, esto se conectaría a un sistema de logs real
        logs_data = [
            {
                'timestamp': '2025-08-26T17:00:00Z',
                'usuario': 'admin',
                'accion': 'creacion_usuario',
                'detalles': 'Creado usuario oficial_cumplimiento_1'
            },
            {
                'timestamp': '2025-08-26T16:30:00Z',
                'usuario': 'procesos_1',
                'accion': 'actualizacion_tercero',
                'detalles': 'Actualizado tercero ID: 123'
            }
        ]
        return Response(logs_data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdministrador])
    def cambiar_rol(self, request, pk=None):
        """
        Cambiar el rol de un usuario (solo administradores)
        """
        target_user = self.get_object()
        nuevo_rol = request.data.get('role')
        
        if nuevo_rol not in [choice[0] for choice in User.RoleChoices.choices]:
            return Response(
                {'error': 'Rol inválido'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        target_user.role = nuevo_rol
        target_user.save()
        
        logger.info(f"Rol de {target_user.username} cambiado a {nuevo_rol} por {request.user.username}")
        
        return Response({
            'message': f'Rol actualizado a {nuevo_rol}',
            'usuario': target_user.username,
            'nuevo_rol': nuevo_rol
        })


class CustomTokenObtainPairView(APIView):
    """
    Vista personalizada para autenticación JWT con verificación de rol
    """
    permission_classes = []
    authentication_classes = []
    
    def post(self, request, *args, **kwargs):
        # Log para debugging
        username = request.data.get('username')
        role = request.data.get('role')
        logger.info(f"Login attempt for: {username} with role: {role}")
        
        serializer = CustomTokenObtainPairSerializer(data=request.data, context={'request': request})
        
        try:
            serializer.is_valid(raise_exception=True)
            logger.info(f"Login successful for: {username}")
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Login failed for {username}: {str(e)}")
            return Response(
                {'error': 'Credenciales inválidas o datos incorrectos'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """
    Obtener información del usuario actual
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Vista para obtener y actualizar el perfil del usuario actual
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def get(self, request, *args, **kwargs):
        user = self.get_object()
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'phone': user.phone,
            'is_active': user.is_active,
            'created_at': user.created_at,
        }
        return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def empleados_list(request):
    """
    Vista específica para obtener lista de empleados
    GET /api/empleados/
    Muestra todos los usuarios (activos e inactivos) para permitir gestión completa
    """
    try:
        # Obtener todos los usuarios (activos e inactivos)
        users = User.objects.all().order_by('first_name', 'last_name')
        
        # Formatear datos para el frontend
        empleados_data = []
        for user in users:
            empleado = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.get_full_name(),
                'role': user.role,
                'role_display': user.get_role_display(),
                'telefono': getattr(user, 'telefono', ''),
                'tipo_documento': getattr(user, 'tipo_documento', ''),
                'numero_documento': getattr(user, 'numero_documento', ''),
                'estado_empleado': getattr(user, 'estado_empleado', 'activo'),
                'direccion': getattr(user, 'direccion', ''),
                'is_active': user.is_active,
                'last_login': user.last_login,
                'date_joined': user.date_joined,
                'created_at': getattr(user, 'created_at', user.date_joined),
                'updated_at': getattr(user, 'updated_at', user.date_joined)
            }
            empleados_data.append(empleado)
        
        # Separar activos e inactivos para estadísticas
        activos = [emp for emp in empleados_data if emp['is_active']]
        inactivos = [emp for emp in empleados_data if not emp['is_active']]
        
        logger.info(f"Lista de empleados solicitada por usuario: {request.user.username} - Total: {len(empleados_data)} (Activos: {len(activos)}, Inactivos: {len(inactivos)})")
        
        return Response({
            'success': True,
            'empleados': empleados_data,
            'total': len(empleados_data),
            'estadisticas': {
                'total': len(empleados_data),
                'activos': len(activos),
                'inactivos': len(inactivos)
            },
            'results': empleados_data  # Para compatibilidad con paginación
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo lista de empleados: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def usuarios_por_rol(request, rol):
    """
    Obtiene usuarios filtrados por rol específico
    """
    try:
        # Validar que el rol existe
        roles_validos = [choice[0] for choice in User._meta.get_field('role').choices]
        if rol not in roles_validos:
            return Response({
                'success': False,
                'error': 'Rol no válido',
                'roles_disponibles': roles_validos
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener usuarios del rol
        usuarios = User.objects.filter(
            role=rol,
            is_active=True
        ).order_by('first_name', 'last_name')
        
        usuarios_data = []
        for usuario in usuarios:
            usuario_data = {
                'id': usuario.id,
                'username': usuario.username,
                'email': usuario.email,
                'first_name': usuario.first_name,
                'last_name': usuario.last_name,
                'nombre_completo': f"{usuario.first_name} {usuario.last_name}".strip(),
                'role': usuario.role,
                'role_display': usuario.get_role_display(),
                'is_active': usuario.is_active,
                'date_joined': usuario.date_joined,
                'cargo': getattr(usuario, 'cargo', None)
            }
            usuarios_data.append(usuario_data)
        
        return Response({
            'success': True,
            'rol': rol,
            'rol_display': dict(User._meta.get_field('role').choices).get(rol, rol),
            'total': len(usuarios_data),
            'usuarios': usuarios_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo usuarios por rol {rol}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def usuarios_disponibles_asignacion(request):
    """
    Obtiene usuarios disponibles para asignación organizados por departamento
    """
    try:
        # Obtener todos los usuarios activos excepto administradores
        usuarios = User.objects.filter(
            is_active=True
        ).exclude(role='administrador').order_by('role', 'first_name', 'last_name')
        
        # Organizar por departamento/rol
        usuarios_por_departamento = {}
        
        for usuario in usuarios:
            role_display = usuario.get_role_display()
            
            if role_display not in usuarios_por_departamento:
                usuarios_por_departamento[role_display] = []
            
            usuario_data = {
                'id': usuario.id,
                'username': usuario.username,
                'email': usuario.email,
                'first_name': usuario.first_name,
                'last_name': usuario.last_name,
                'nombre_completo': f"{usuario.first_name} {usuario.last_name}".strip(),
                'role': usuario.role,
                'cargo': getattr(usuario, 'cargo', None)
            }
            usuarios_por_departamento[role_display].append(usuario_data)
        
        total_usuarios = sum(len(usuarios) for usuarios in usuarios_por_departamento.values())
        
        return Response({
            'success': True,
            'total_usuarios': total_usuarios,
            'usuarios_por_departamento': usuarios_por_departamento,
            'departamentos_disponibles': list(usuarios_por_departamento.keys())
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo usuarios disponibles: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
