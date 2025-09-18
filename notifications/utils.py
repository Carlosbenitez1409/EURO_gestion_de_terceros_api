from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from .models import Notificacion, PreferenciasNotificacion

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """
    Servicio para crear y gestionar notificaciones automáticamente
    """
    
    @staticmethod
    def crear_notificacion_tercero_asignado(tercero, comercial):
        """
        Crear notificación cuando se asigne un tercero a un comercial
        """
        try:
            nombre_tercero = (
                f"{tercero.nombres} {tercero.apellidos}" 
                if tercero.tipo_persona == 'natural' 
                else tercero.razon_social
            )
            
            titulo = f"Nuevo tercero asignado: {nombre_tercero}"
            mensaje = (
                f"Se te ha asignado el tercero {nombre_tercero} "
                f"(Doc: {tercero.numero_documento}) para su gestión."
            )
            
            Notificacion.crear_notificacion(
                usuario=comercial,
                titulo=titulo,
                mensaje=mensaje,
                tipo='tercero_asignado',
                prioridad='media',
                tercero_relacionado=tercero,
                url_accion=f"/terceros/{tercero.id}",
                datos_extra={
                    'tercero_id': str(tercero.id),
                    'numero_documento': tercero.numero_documento,
                    'tipo_persona': tercero.tipo_persona
                }
            )
            
            logger.info(f"Notificación de tercero asignado creada para {comercial.username}")
            
        except Exception as e:
            logger.error(f"Error creando notificación de tercero asignado: {e}")
    
    @staticmethod
    def crear_notificacion_cambio_estado(tercero):
        """
        Crear notificación cuando cambie el estado de un tercero
        """
        try:
            # Notificar al comercial asignado si existe
            if tercero.asignado_a:
                nombre_tercero = (
                    f"{tercero.nombres} {tercero.apellidos}" 
                    if tercero.tipo_persona == 'natural' 
                    else tercero.razon_social
                )
                
                estado_display = tercero.get_estado_aprobacion_display()
                
                titulo = f"Estado actualizado: {nombre_tercero}"
                mensaje = (
                    f"El tercero {nombre_tercero} (Doc: {tercero.numero_documento}) "
                    f"ha cambiado su estado a: {estado_display}"
                )
                
                # Determinar tipo y prioridad según el nuevo estado
                tipo = 'estado_cambiado'
                prioridad = 'media'
                
                if tercero.estado_aprobacion == 'aprobado':
                    tipo = 'tercero_aprobado'
                    prioridad = 'alta'
                elif tercero.estado_aprobacion == 'rechazado':
                    tipo = 'tercero_rechazado'
                    prioridad = 'alta'
                elif tercero.estado_aprobacion == 'requiere_ajustes':
                    tipo = 'revision_requerida'
                    prioridad = 'alta'
                
                Notificacion.crear_notificacion(
                    usuario=tercero.asignado_a,
                    titulo=titulo,
                    mensaje=mensaje,
                    tipo=tipo,
                    prioridad=prioridad,
                    tercero_relacionado=tercero,
                    url_accion=f"/terceros/{tercero.id}",
                    datos_extra={
                        'tercero_id': str(tercero.id),
                        'estado_anterior': getattr(tercero, '_estado_anterior', ''),
                        'estado_nuevo': tercero.estado_aprobacion,
                        'observaciones': tercero.observaciones
                    }
                )
            
            # Notificar también al usuario de procesos si está asignado
            if tercero.asignado_a_procesos and tercero.asignado_a_procesos != tercero.asignado_a:
                NotificationService._crear_notificacion_para_procesos(tercero)
            
            logger.info(f"Notificación de cambio de estado creada para tercero {tercero.id}")
            
        except Exception as e:
            logger.error(f"Error creando notificación de cambio de estado: {e}")
    
    @staticmethod
    def _crear_notificacion_para_procesos(tercero):
        """
        Crear notificación específica para usuario de procesos
        """
        if not tercero.asignado_a_procesos:
            return
        
        nombre_tercero = (
            f"{tercero.nombres} {tercero.apellidos}" 
            if tercero.tipo_persona == 'natural' 
            else tercero.razon_social
        )
        
        titulo = f"Tercero actualizado: {nombre_tercero}"
        mensaje = (
            f"El tercero {nombre_tercero} ha sido actualizado. "
            f"Estado actual: {tercero.get_estado_aprobacion_display()}"
        )
        
        Notificacion.crear_notificacion(
            usuario=tercero.asignado_a_procesos,
            titulo=titulo,
            mensaje=mensaje,
            tipo='estado_cambiado',
            prioridad='media',
            tercero_relacionado=tercero,
            url_accion=f"/terceros/{tercero.id}"
        )
    
    @staticmethod
    def crear_notificacion_documento_subido(documento):
        """
        Crear notificación cuando se suba un documento
        """
        try:
            tercero = documento.tercero
            
            # Notificar al comercial asignado
            if tercero.asignado_a:
                nombre_tercero = (
                    f"{tercero.nombres} {tercero.apellidos}" 
                    if tercero.tipo_persona == 'natural' 
                    else tercero.razon_social
                )
                
                titulo = f"Nuevo documento: {nombre_tercero}"
                mensaje = (
                    f"Se ha subido un nuevo documento ({documento.tipo_documento}) "
                    f"para el tercero {nombre_tercero} (Doc: {tercero.numero_documento})"
                )
                
                Notificacion.crear_notificacion(
                    usuario=tercero.asignado_a,
                    titulo=titulo,
                    mensaje=mensaje,
                    tipo='documento_subido',
                    prioridad='media',
                    tercero_relacionado=tercero,
                    url_accion=f"/terceros/{tercero.id}/documentos",
                    datos_extra={
                        'documento_id': str(documento.id),
                        'tipo_documento': documento.tipo_documento,
                        'nombre_archivo': documento.nombre_original
                    }
                )
            
            # Notificar también a procesos si está asignado
            if tercero.asignado_a_procesos:
                NotificationService._crear_notificacion_documento_procesos(documento)
            
            logger.info(f"Notificación de documento subido creada para tercero {tercero.id}")
            
        except Exception as e:
            logger.error(f"Error creando notificación de documento subido: {e}")
    
    @staticmethod
    def _crear_notificacion_documento_procesos(documento):
        """
        Crear notificación de documento para usuario de procesos
        """
        tercero = documento.tercero
        
        if not tercero.asignado_a_procesos:
            return
        
        nombre_tercero = (
            f"{tercero.nombres} {tercero.apellidos}" 
            if tercero.tipo_persona == 'natural' 
            else tercero.razon_social
        )
        
        titulo = f"Documento para revisión: {nombre_tercero}"
        mensaje = (
            f"Nuevo documento ({documento.tipo_documento}) disponible "
            f"para revisión del tercero {nombre_tercero}"
        )
        
        Notificacion.crear_notificacion(
            usuario=tercero.asignado_a_procesos,
            titulo=titulo,
            mensaje=mensaje,
            tipo='documento_subido',
            prioridad='media',
            tercero_relacionado=tercero,
            url_accion=f"/terceros/{tercero.id}/documentos"
        )
    
    @staticmethod
    def crear_notificacion_usuario_creado(usuario):
        """
        Crear notificación cuando se cree un nuevo usuario
        """
        try:
            # Notificar a administradores y gestión humana
            usuarios_a_notificar = User.objects.filter(
                role__in=['administrador', 'gestion_humana'],
                is_active=True
            ).exclude(id=usuario.id)
            
            titulo = f"Nuevo usuario creado: {usuario.get_full_name()}"
            mensaje = (
                f"Se ha creado un nuevo usuario: {usuario.get_full_name()} "
                f"({usuario.email}) con el rol de {usuario.get_role_display()}"
            )
            
            for usuario_notificar in usuarios_a_notificar:
                # Verificar preferencias antes de crear
                preferencias, _ = PreferenciasNotificacion.get_or_create_for_user(usuario_notificar)
                
                if preferencias.acepta_notificacion('usuario_creado'):
                    Notificacion.crear_notificacion(
                        usuario=usuario_notificar,
                        titulo=titulo,
                        mensaje=mensaje,
                        tipo='usuario_creado',
                        prioridad='baja',
                        usuario_relacionado=usuario,
                        url_accion=f"/admin/accounts/user/{usuario.id}",
                        datos_extra={
                            'nuevo_usuario_id': str(usuario.id),
                            'role': usuario.role,
                            'email': usuario.email
                        }
                    )
            
            logger.info(f"Notificaciones de usuario creado enviadas para {usuario.username}")
            
        except Exception as e:
            logger.error(f"Error creando notificación de usuario creado: {e}")
    
    @staticmethod
    def crear_notificacion_rol_cambiado(usuario):
        """
        Crear notificación cuando cambie el rol de un usuario
        """
        try:
            # Notificar al propio usuario
            titulo = "Tu rol ha sido actualizado"
            mensaje = (
                f"Tu rol en el sistema ha sido actualizado a: {usuario.get_role_display()}. "
                "Algunos permisos y funcionalidades pueden haber cambiado."
            )
            
            Notificacion.crear_notificacion(
                usuario=usuario,
                titulo=titulo,
                mensaje=mensaje,
                tipo='rol_cambiado',
                prioridad='alta',
                datos_extra={
                    'role_anterior': getattr(usuario, '_role_anterior', ''),
                    'role_nuevo': usuario.role
                }
            )
            
            # Notificar también a administradores
            administradores = User.objects.filter(
                role='administrador',
                is_active=True
            ).exclude(id=usuario.id)
            
            titulo_admin = f"Rol actualizado: {usuario.get_full_name()}"
            mensaje_admin = (
                f"El rol del usuario {usuario.get_full_name()} ({usuario.email}) "
                f"ha sido actualizado a: {usuario.get_role_display()}"
            )
            
            for admin in administradores:
                Notificacion.crear_notificacion(
                    usuario=admin,
                    titulo=titulo_admin,
                    mensaje=mensaje_admin,
                    tipo='rol_cambiado',
                    prioridad='media',
                    usuario_relacionado=usuario,
                    url_accion=f"/admin/accounts/user/{usuario.id}"
                )
            
            logger.info(f"Notificaciones de rol cambiado enviadas para {usuario.username}")
            
        except Exception as e:
            logger.error(f"Error creando notificación de rol cambiado: {e}")
    
    @staticmethod
    def crear_notificacion_revision_cumplimiento(revision):
        """
        Crear notificación cuando se realice una revisión de cumplimiento
        """
        try:
            tercero = revision.tercero
            
            # Notificar al comercial asignado
            if tercero.asignado_a:
                nombre_tercero = (
                    f"{tercero.nombres} {tercero.apellidos}" 
                    if tercero.tipo_persona == 'natural' 
                    else tercero.razon_social
                )
                
                estado_revision = "aprobado" if revision.aprobado else "requiere ajustes"
                
                titulo = f"Revisión de cumplimiento: {nombre_tercero}"
                mensaje = (
                    f"La revisión de cumplimiento para {nombre_tercero} "
                    f"ha sido completada. Estado: {estado_revision}. "
                    f"Nivel de riesgo: {revision.get_nivel_riesgo_display()}"
                )
                
                if revision.observaciones:
                    mensaje += f"\n\nObservaciones: {revision.observaciones}"
                
                prioridad = 'alta' if not revision.aprobado else 'media'
                tipo = 'revision_requerida' if not revision.aprobado else 'tercero_aprobado'
                
                Notificacion.crear_notificacion(
                    usuario=tercero.asignado_a,
                    titulo=titulo,
                    mensaje=mensaje,
                    tipo=tipo,
                    prioridad=prioridad,
                    tercero_relacionado=tercero,
                    usuario_relacionado=revision.usuario,
                    url_accion=f"/terceros/{tercero.id}",
                    datos_extra={
                        'revision_id': str(revision.id),
                        'aprobado': revision.aprobado,
                        'nivel_riesgo': revision.nivel_riesgo,
                        'requiere_monitoreo': revision.requiere_monitoreo
                    }
                )
            
            logger.info(f"Notificación de revisión de cumplimiento creada para tercero {tercero.id}")
            
        except Exception as e:
            logger.error(f"Error creando notificación de revisión de cumplimiento: {e}")
    
    @staticmethod
    def crear_notificacion_alerta_cumplimiento(tercero, tipo_alerta, mensaje_alerta):
        """
        Crear notificación de alerta de cumplimiento
        """
        try:
            # Notificar a oficiales de cumplimiento y administradores
            usuarios_cumplimiento = User.objects.filter(
                role__in=['oficial_cumplimiento', 'administrador'],
                is_active=True
            )
            
            nombre_tercero = (
                f"{tercero.nombres} {tercero.apellidos}" 
                if tercero.tipo_persona == 'natural' 
                else tercero.razon_social
            )
            
            titulo = f"Alerta de cumplimiento: {nombre_tercero}"
            mensaje = f"Alerta de {tipo_alerta} para el tercero {nombre_tercero}: {mensaje_alerta}"
            
            for usuario in usuarios_cumplimiento:
                Notificacion.crear_notificacion(
                    usuario=usuario,
                    titulo=titulo,
                    mensaje=mensaje,
                    tipo='alerta_cumplimiento',
                    prioridad='alta',
                    tercero_relacionado=tercero,
                    url_accion=f"/terceros/{tercero.id}/analisis_sarlaft",
                    datos_extra={
                        'tipo_alerta': tipo_alerta,
                        'es_pep': tercero.personaExpuestaPolitica,
                        'manejo_alto_efectivo': tercero.manejoAltoEfectivo
                    }
                )
            
            logger.info(f"Alerta de cumplimiento creada para tercero {tercero.id}: {tipo_alerta}")
            
        except Exception as e:
            logger.error(f"Error creando alerta de cumplimiento: {e}")
    
    @staticmethod
    def crear_notificacion_masiva_por_roles(titulo, mensaje, roles, tipo='sistema', 
                                          prioridad='media', datos_extra=None, url_accion=None,
                                          usuario_creador=None):
        """
        Crear notificaciones masivas para usuarios con roles específicos
        """
        try:
            usuarios_destino = User.objects.filter(
                role__in=roles,
                is_active=True
            )
            
            notificaciones_creadas = 0
            
            for usuario in usuarios_destino:
                # Verificar preferencias
                preferencias, _ = PreferenciasNotificacion.get_or_create_for_user(usuario)
                
                if preferencias.acepta_notificacion(tipo):
                    Notificacion.crear_notificacion(
                        usuario=usuario,
                        titulo=titulo,
                        mensaje=mensaje,
                        tipo=tipo,
                        prioridad=prioridad,
                        usuario_relacionado=usuario_creador,
                        datos_extra=datos_extra,
                        url_accion=url_accion
                    )
                    notificaciones_creadas += 1
            
            logger.info(
                f"Notificación masiva creada: {notificaciones_creadas} notificaciones "
                f"para roles {roles}"
            )
            
            return notificaciones_creadas
            
        except Exception as e:
            logger.error(f"Error creando notificación masiva: {e}")
            return 0
