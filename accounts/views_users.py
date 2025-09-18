from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class UserManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión completa de usuarios (solo para administradores)
    """
    queryset = User.objects.all().order_by('-date_joined')
    
    def get_permissions(self):
        """Solo administradores pueden gestionar usuarios"""
        if self.action in ['list', 'retrieve']:
            # Para listar y ver detalles, también procesos puede ver
            return [permissions.IsAuthenticated()]
        else:
            # Para crear, editar, eliminar solo administradores
            return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        from .serializers import UserManagementSerializer, UserCreateSerializer
        
        if self.action == 'create':
            return UserCreateSerializer
        return UserManagementSerializer
    
    def get_queryset(self):
        """Filtrar usuarios según el rol del solicitante"""
        user = self.request.user
        queryset = User.objects.all().order_by('-date_joined')
        
        # Filtrar por rol si se especifica
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        # Filtrar por estado activo
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Excluir usuarios de prueba
        queryset = queryset.exclude(username__contains='test')
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        Listar usuarios con información adicional para el frontend
        GET /api/users/?role=procesos&is_active=true
        """
        queryset = self.get_queryset()
        
        # Anotar con información adicional
        queryset = queryset.annotate(
            terceros_asignados_count=Count('terceros_asignados_comercial'),
            terceros_procesos_count=Count('terceros_asignados_procesos'),
            terceros_cumplimiento_count=Count('terceros_asignados_cumplimiento')
        )
        
        users_data = []
        for user in queryset:
            # Calcular último acceso (aproximado por última actualización)
            last_access = user.last_login or user.date_joined
            
            users_data.append({
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.get_full_name(),
                'role': user.role,
                'role_display': user.get_role_display(),
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
                'last_access': last_access,
                'terceros_asignados': user.terceros_asignados_count,
                'terceros_procesos': user.terceros_procesos_count,
                'terceros_cumplimiento': user.terceros_cumplimiento_count,
                'total_assignments': (
                    user.terceros_asignados_count + 
                    user.terceros_procesos_count + 
                    user.terceros_cumplimiento_count
                )
            })
        
        return Response({
            'success': True,
            'users': users_data,
            'total': len(users_data),
            'filters_applied': {
                'role': request.query_params.get('role'),
                'is_active': request.query_params.get('is_active')
            }
        })
    
    def create(self, request, *args, **kwargs):
        """
        Crear nuevo usuario (solo administradores)
        POST /api/users/
        """
        # Verificar que sea administrador
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden crear usuarios'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        
        # Validar campos requeridos
        required_fields = ['username', 'email', 'first_name', 'last_name', 'role', 'password']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'error': f'El campo {field} es requerido'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verificar que username y email sean únicos
            if User.objects.filter(username=data['username']).exists():
                return Response({
                    'success': False,
                    'error': 'El nombre de usuario ya existe'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if User.objects.filter(email=data['email']).exists():
                return Response({
                    'success': False,
                    'error': 'El email ya está registrado'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Crear usuario
            user = User.objects.create(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role=data['role'],
                is_active=data.get('is_active', True),
                is_staff=data.get('is_staff', False)
            )
            
            # Establecer contraseña
            user.set_password(data['password'])
            user.save()
            
            logger.info(f"Usuario creado: {user.username} por {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Usuario creado exitosamente',
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.get_full_name(),
                    'role': user.role,
                    'is_active': user.is_active
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creando usuario: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error interno del servidor',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """
        Cambiar contraseña de usuario
        POST /api/users/{id}/change_password/
        Body: {"new_password": "nueva_contraseña"}
        """
        # Solo administradores o el mismo usuario
        if not (hasattr(request.user, 'role') and request.user.role == 'administrador') and str(request.user.id) != pk:
            return Response({
                'success': False,
                'error': 'No tienes permisos para cambiar esta contraseña'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk)
            new_password = request.data.get('new_password')
            
            if not new_password:
                return Response({
                    'success': False,
                    'error': 'La nueva contraseña es requerida'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if len(new_password) < 6:
                return Response({
                    'success': False,
                    'error': 'La contraseña debe tener al menos 6 caracteres'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.save()
            
            logger.info(f"Contraseña cambiada para usuario: {user.username} por {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Contraseña actualizada exitosamente'
            })
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Usuario no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error cambiando contraseña: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """
        Activar/desactivar usuario (toggle automático)
        POST /api/user-management/{id}/toggle_status/
        """
        # Solo administradores
        if not hasattr(request.user, 'role') or request.user.role != 'administrador':
            return Response({
                'success': False,
                'error': 'Solo administradores pueden cambiar el estado de usuarios'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk)
            
            # Toggle automático del estado
            user.is_active = not user.is_active
            
            # Actualizar estado_empleado según is_active
            if user.is_active:
                user.estado_empleado = 'activo'
            else:
                user.estado_empleado = 'inactivo'
            
            user.save()
            
            status_text = 'activado' if user.is_active else 'desactivado'
            logger.info(f"Usuario {status_text}: {user.username} por {request.user.username}")
            
            return Response({
                'success': True,
                'message': f'Estado del usuario actualizado correctamente',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.get_full_name(),
                    'is_active': user.is_active,
                    'estado_empleado': user.estado_empleado
                }
            })
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Usuario no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error cambiando estado de usuario: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def by_role(self, request):
        """
        Obtener usuarios agrupados por rol
        GET /api/users/by_role/
        """
        roles = [
            'comercial',
            'procesos', 
            'administrador',
            'oficial_cumplimiento',
            'gestion_humana'
        ]
        
        result = {}
        for role in roles:
            users = User.objects.filter(
                role=role,
                is_active=True
            ).exclude(
                username__contains='test'
            ).annotate(
                total_assignments=Count('terceros_asignados_comercial') + 
                                Count('terceros_asignados_procesos') + 
                                Count('terceros_asignados_cumplimiento')
            ).order_by('total_assignments')
            
            result[role] = [{
                'id': str(user.id),
                'username': user.username,
                'full_name': user.get_full_name(),
                'email': user.email,
                'is_active': user.is_active,
                'last_login': user.last_login,
                'total_assignments': user.total_assignments
            } for user in users]
        
        return Response({
            'success': True,
            'users_by_role': result,
            'total_by_role': {role: len(users) for role, users in result.items()}
        })
    
    @action(detail=False, methods=['get'], url_path='empleados')
    def empleados(self, request):
        """
        Obtener lista de empleados con formato específico para el frontend
        GET /api/accounts/user-management/empleados/
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
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error obteniendo lista de empleados: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error interno del servidor',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
