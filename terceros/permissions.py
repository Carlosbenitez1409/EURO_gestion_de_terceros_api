from rest_framework import permissions

class TerceroPermissions(permissions.BasePermission):
    """
    Permisos personalizados para terceros:
    - POST (create): Permitir acceso público para registro de proveedores
    - Administrador: Acceso total (crear, editar, eliminar, aprobar, rechazar)
    - Oficial de cumplimiento: Acceso a revisión y validación SARLAFT/PEP
    - Procesos: Gestión normal de terceros + APROBAR/RECHAZAR + COMENTARIOS + WORKFLOW (AMPLIADO)
    - Comercial: Solo ver sus terceros asignados
    - Otras operaciones: Requieren autenticación
    
    ACCIONES PERMITIDAS POR ROL (ACTUALIZADO SEPT 2025):
    
    🔵 ADMINISTRADOR: ALL (acceso completo a todas las acciones)
    
    🟡 OFICIAL_CUMPLIMIENTO: 
    - list, retrieve, update, partial_update
    - validar_sarlaft, validar_pep (acciones específicas)
    
    🟢 PROCESOS (AMPLIADO):
    - list, retrieve, update, partial_update (gestión básica)
    - aprobar, rechazar (NUEVO - decisiones finales)
    - cambiar_estado (NUEVO - workflow completo)
    - add_comment, get_comments (NUEVO - sistema de comentarios)
    - historial_completo (NUEVO - auditoría completa)
    
    🔴 COMERCIAL (limitado a terceros asignados):
    - list (filtrado), retrieve, update, partial_update
    - aprobar_comercial (acción específica)
    - add_comment (solo en terceros asignados)
    - stats, mis_terceros
    """
    
    def has_permission(self, request, view):
        # Permitir creación sin autenticación (registro público)
        if view.action == 'create':
            return True
        
        # Para todas las demás operaciones, requiere autenticación
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Verificar roles específicos
        if hasattr(request.user, 'role'):
            user_role = request.user.role
            
            # Administrador: Acceso total a todo
            if user_role == 'administrador':
                return True
            
            # Oficial de cumplimiento: Acceso completo para tareas SARLAFT
            if user_role == 'oficial_cumplimiento':
                return True
            
            # Procesos: Acceso normal de gestión + aprobar/rechazar
            if user_role == 'procesos':
                # Acciones permitidas para procesos
                allowed_actions = [
                    'list', 'retrieve', 'update', 'partial_update',
                    'aprobar', 'rechazar',  # NUEVAS ACCIONES AGREGADAS
                    'cambiar_estado',  # REQUERIDO PARA CAMBIOS DE ESTADO DEL WORKFLOW
                    'add_comment',  # REQUERIDO PARA AGREGAR COMENTARIOS
                    'get_comments',  # REQUERIDO PARA VER COMENTARIOS
                    'historial_completo'  # REQUERIDO PARA VER HISTORIAL COMPLETO
                ]
                return view.action in allowed_actions
            
            # Comercial: Acceso limitado a sus terceros
            if user_role == 'comercial':
                # Los comerciales pueden ver sus terceros, stats y aprobar
                allowed_actions = ['list', 'retrieve', 'stats', 'mis_terceros', 'aprobar_comercial', 'partial_update', 'update']
                return view.action in allowed_actions
            
            # Gestión humana: Solo lectura
            if user_role == 'gestion_humana':
                return request.method in permissions.SAFE_METHODS
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Para operaciones en objetos específicos, requiere autenticación
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Verificar roles específicos para permisos de objeto
        if hasattr(request.user, 'role'):
            user_role = request.user.role
            
            # Administrador: Puede hacer cualquier cosa con cualquier tercero
            if user_role == 'administrador':
                return True
            
            # Oficial de cumplimiento: Puede modificar cualquier tercero
            if user_role == 'oficial_cumplimiento':
                return True
            
            # Procesos: Puede gestionar terceros
            if user_role == 'procesos':
                return True
            
            # Comercial: Solo puede ver y actualizar sus terceros asignados
            if user_role == 'comercial':
                # Verificar si el tercero está asignado a este comercial
                if hasattr(obj, 'asignado_a') and obj.asignado_a == request.user:
                    # Permitir operaciones de lectura y actualización limitada
                    if request.method in permissions.SAFE_METHODS:
                        return True
                    elif request.method in ['PATCH', 'PUT']:
                        # Permitir actualización solo de ciertos campos
                        return True
                return False
            
            # Gestión humana: Solo lectura
            if user_role == 'gestion_humana':
                return request.method in permissions.SAFE_METHODS
        
        return False
