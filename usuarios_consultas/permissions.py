# usuarios_consultas/permissions.py
"""
Permisos personalizados para el Sistema de Usuarios GH
Implementación según API_SPECIFICATION_USUARIOS_GH.md
"""

from rest_framework import permissions
from .models import EstadoSolicitud


class UsuariosGHPermission(permissions.BasePermission):
    """
    Permiso personalizado para el sistema de Usuarios GH
    Implementa la matriz de permisos según roles
    """
    
    def has_permission(self, request, view):
        """
        Verificar permisos a nivel de vista
        """
        # Usuario debe estar autenticado
        if not request.user.is_authenticated:
            return False
        
        # Usuario debe tener rol asignado
        if not hasattr(request.user, 'role'):
            return False
        
        # Todos los roles tienen acceso básico a las vistas
        # Los permisos específicos se validan en has_object_permission
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Verificar permisos a nivel de objeto específico
        """
        user = request.user
        
        if not hasattr(user, 'role'):
            return False
        
        role = user.role
        
        # Identificar el tipo de objeto
        from .models import Solicitud, Persona, HistorialCambio
        
        if isinstance(obj, Solicitud):
            return self._tiene_permiso_solicitud(user, role, obj, view.action, request.method)
        elif isinstance(obj, Persona):
            return self._tiene_permiso_persona(user, role, obj, view.action, request.method)
        elif isinstance(obj, HistorialCambio):
            return self._tiene_permiso_historial(user, role, obj, view.action, request.method)
        
        return False
    
    def _tiene_permiso_solicitud(self, user, role, solicitud, action, method):
        """
        Verificar permisos específicos para solicitudes
        """
        estado = solicitud.estado
        
        if role == 'gestion_humana':
            # GH puede ver sus propias solicitudes
            if action in ['retrieve', 'list']:
                return solicitud.creada_por == user
            
            # GH puede crear solicitudes
            if action == 'create':
                return True
            
            # GH puede editar solicitudes devueltas
            if action in ['update', 'partial_update']:
                return (solicitud.creada_por == user and 
                       estado == EstadoSolicitud.DEVUELTA_GH)
            
            # GH puede cambiar estado desde DEVUELTA_GH
            if action == 'cambiar_estado':
                return (solicitud.creada_por == user and 
                       estado == EstadoSolicitud.DEVUELTA_GH)
            
            # GH puede asignar sus propias solicitudes
            if action == 'asignar':
                return (solicitud.creada_por == user and 
                       estado == EstadoSolicitud.CREADA)
            
            # GH no puede eliminar solicitudes
            return False
        
        elif role == 'administrador':
            # Admin puede ver solicitudes asignadas a administradores o suyas
            if action in ['retrieve', 'list']:
                return (estado in [EstadoSolicitud.ASIGNADA_ADMINISTRADOR, EstadoSolicitud.EN_REVISION_ADMINISTRADOR] or
                       solicitud.asignada_a == user)
            
            # Admin puede tomar solicitudes asignadas a administradores
            if action == 'tomar_revision':
                return estado == EstadoSolicitud.ASIGNADA_ADMINISTRADOR
            
            # Admin puede cambiar estado si está asignada a él
            if action == 'cambiar_estado':
                return (estado == EstadoSolicitud.EN_REVISION_ADMINISTRADOR and 
                       solicitud.asignada_a == user)
            
            # Admin no puede crear, editar ni eliminar solicitudes
            return action not in ['create', 'update', 'partial_update', 'destroy']
        
        elif role == 'procesos':
            # Procesos puede ver solicitudes asignadas a procesos o suyas
            if action in ['retrieve', 'list']:
                return (estado in [EstadoSolicitud.ASIGNADA_PROCESOS, EstadoSolicitud.EN_REVISION_PROCESOS] or
                       solicitud.asignada_a == user)
            
            # Procesos puede tomar solicitudes asignadas a procesos
            if action == 'tomar_revision':
                return estado == EstadoSolicitud.ASIGNADA_PROCESOS
            
            # Procesos puede cambiar estado si está asignada a él
            if action == 'cambiar_estado':
                return (estado == EstadoSolicitud.EN_REVISION_PROCESOS and 
                       solicitud.asignada_a == user)
            
            # Procesos no puede crear, editar ni eliminar solicitudes
            return action not in ['create', 'update', 'partial_update', 'destroy']
        
        return False
    
    def _tiene_permiso_persona(self, user, role, persona, action, method):
        """
        Verificar permisos específicos para personas
        """
        solicitud = persona.solicitud
        estado_solicitud = solicitud.estado
        
        if role == 'gestion_humana':
            # GH puede gestionar personas de sus solicitudes
            if solicitud.creada_por == user:
                # Solo puede editar si la solicitud está en estado editable
                if action in ['create', 'update', 'partial_update', 'destroy']:
                    return estado_solicitud in [EstadoSolicitud.CREADA, EstadoSolicitud.DEVUELTA_GH]
                
                # Puede ver siempre sus personas
                if action in ['retrieve', 'list']:
                    return True
            
            return False
        
        elif role in ['administrador', 'procesos']:
            # Admin y Procesos pueden ver personas de solicitudes que pueden ver
            if action in ['retrieve', 'list']:
                return self._puede_ver_solicitud(user, role, solicitud)
            
            # Admin y Procesos pueden actualizar antecedentes y riesgo si tienen la solicitud asignada
            if action in ['update', 'partial_update']:
                return (solicitud.asignada_a == user and 
                       estado_solicitud == EstadoSolicitud.EN_REVISION)
            
            # No pueden crear ni eliminar personas
            return False
        
        return False
    
    def _tiene_permiso_historial(self, user, role, historial, action, method):
        """
        Verificar permisos específicos para historial
        """
        solicitud = historial.solicitud
        
        # Historial es solo lectura para todos
        if action not in ['retrieve', 'list']:
            return False
        
        # Verificar si puede ver la solicitud asociada
        return self._puede_ver_solicitud(user, role, solicitud)
    
    def _puede_ver_solicitud(self, user, role, solicitud):
        """
        Verificar si un usuario puede ver una solicitud específica
        """
        estado = solicitud.estado
        
        if role == 'gestion_humana':
            return solicitud.creada_por == user
        
        elif role == 'administrador':
            return (estado in [EstadoSolicitud.ASIGNADA_ADMINISTRADOR, EstadoSolicitud.EN_REVISION] or
                   solicitud.asignada_a == user)
        
        elif role == 'procesos':
            return (estado in [EstadoSolicitud.ASIGNADA_PROCESOS, EstadoSolicitud.EN_REVISION] or
                   solicitud.asignada_a == user)
        
        return False


class EsGestionHumana(permissions.BasePermission):
    """
    Permiso que requiere rol de Gestión Humana
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return hasattr(request.user, 'role') and request.user.role == 'gestion_humana'


class EsAdministrador(permissions.BasePermission):
    """
    Permiso que requiere rol de Administrador
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return hasattr(request.user, 'role') and request.user.role == 'administrador'


class EsProcesos(permissions.BasePermission):
    """
    Permiso que requiere rol de Procesos
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return hasattr(request.user, 'role') and request.user.role == 'procesos'


class PuedeEditarSolicitud(permissions.BasePermission):
    """
    Permiso específico para editar solicitudes
    """
    
    def has_object_permission(self, request, view, obj):
        """Solo permitir edición si la solicitud puede ser editada por el usuario"""
        from .models import Solicitud
        
        if not isinstance(obj, Solicitud):
            return False
        
        return obj.puede_ser_editada_por(request.user)


class PuedeTomarRevision(permissions.BasePermission):
    """
    Permiso específico para tomar solicitudes en revisión
    """
    
    def has_object_permission(self, request, view, obj):
        """Solo permitir tomar revisión si el usuario puede hacerlo"""
        from .models import Solicitud
        
        if not isinstance(obj, Solicitud):
            return False
        
        return obj.puede_tomar_revision(request.user)