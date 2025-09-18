from rest_framework import permissions


class IsProcesos(permissions.BasePermission):
    """
    Permiso que solo permite acceso a usuarios con rol 'procesos'
    Procesos es el único que puede gestionar usuarios del sistema (login)
    """
    
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Solo procesos puede gestionar usuarios del sistema
        if hasattr(request.user, 'role'):
            return request.user.role == 'procesos'
        
        return False


class IsAdministrador(permissions.BasePermission):
    """
    Permiso que permite acceso total solo a administradores
    """
    
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Solo administradores tienen acceso total
        if hasattr(request.user, 'role'):
            return request.user.role == 'administrador'
        
        return False


class IsOficialCumplimiento(permissions.BasePermission):
    """
    Permiso que permite acceso a oficiales de cumplimiento para tareas SARLAFT/PEP
    """
    
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Oficial de cumplimiento y administrador tienen acceso
        if hasattr(request.user, 'role'):
            return request.user.role in ['oficial_cumplimiento', 'administrador']
        
        return False


class IsProcesosOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite a procesos hacer todo, pero otros roles solo pueden ver
    """
    
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Administradores tienen acceso total
        if hasattr(request.user, 'role') and request.user.role == 'administrador':
            return True
        
        # Si es una operación de lectura, permitir a roles autorizados
        if request.method in permissions.SAFE_METHODS:
            if hasattr(request.user, 'role'):
                allowed_roles = ['procesos', 'gestion_humana', 'oficial_cumplimiento']
                return request.user.role in allowed_roles
        
        # Para operaciones de escritura (POST, PUT, PATCH, DELETE), solo procesos y administrador
        if hasattr(request.user, 'role'):
            return request.user.role in ['procesos', 'administrador']
        
        return False


class IsAdminOrOficialCumplimiento(permissions.BasePermission):
    """
    Permiso para acciones que requieren administrador u oficial de cumplimiento
    """
    
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Administrador y oficial de cumplimiento tienen acceso
        if hasattr(request.user, 'role'):
            return request.user.role in ['administrador', 'oficial_cumplimiento']
        
        return False
