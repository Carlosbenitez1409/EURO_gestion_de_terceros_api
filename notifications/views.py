from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Notificacion, PreferenciasNotificacion
from .serializers import (
    NotificacionSerializer, NotificacionCreateSerializer,
    PreferenciasNotificacionSerializer, NotificacionResumenSerializer,
    MarcarLeidaSerializer, CrearNotificacionMasivaSerializer
)
from accounts.permissions import IsAdministrador

logger = logging.getLogger(__name__)


class NotificacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de notificaciones
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificacionSerializer
    
    def get_queryset(self):
        """Filtrar notificaciones del usuario autenticado"""
        user = self.request.user
        queryset = Notificacion.objects.filter(usuario=user)
        
        # Filtros opcionales
        leida = self.request.query_params.get('leida')
        if leida is not None:
            leida = leida.lower() == 'true'
            queryset = queryset.filter(leida=leida)
        
        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        prioridad = self.request.query_params.get('prioridad')
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        
        # Filtro por fecha
        desde = self.request.query_params.get('desde')
        if desde:
            try:
                fecha_desde = timezone.datetime.fromisoformat(desde)
                queryset = queryset.filter(fecha_creacion__gte=fecha_desde)
            except ValueError:
                pass
        
        return queryset.order_by('-fecha_creacion')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificacionCreateSerializer
        return NotificacionSerializer
    
    def perform_create(self, serializer):
        """Al crear, asignar el usuario autenticado si no se especifica"""
        if not serializer.validated_data.get('usuario'):
            serializer.save(usuario=self.request.user)
        else:
            serializer.save()
    
    @action(detail=False, methods=['get'])
    def resumen(self, request):
        """
        Obtener resumen de notificaciones del usuario
        GET /api/notifications/notificaciones/resumen/
        """
        user = request.user
        
        # Estadísticas básicas
        total_notificaciones = Notificacion.objects.filter(usuario=user).count()
        no_leidas = Notificacion.objects.filter(usuario=user, leida=False).count()
        
        # Estadísticas por tipo
        por_tipo = dict(
            Notificacion.objects.filter(usuario=user)
            .values('tipo')
            .annotate(count=Count('id'))
            .values_list('tipo', 'count')
        )
        
        # Estadísticas por prioridad
        por_prioridad = dict(
            Notificacion.objects.filter(usuario=user)
            .values('prioridad')
            .annotate(count=Count('id'))
            .values_list('prioridad', 'count')
        )
        
        # Últimas 5 notificaciones
        ultimas_5 = Notificacion.objects.filter(usuario=user)[:5]
        
        data = {
            'total_notificaciones': total_notificaciones,
            'no_leidas': no_leidas,
            'por_tipo': por_tipo,
            'por_prioridad': por_prioridad,
            'ultimas_5': ultimas_5
        }
        
        serializer = NotificacionResumenSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def marcar_leidas(self, request):
        """
        Marcar múltiples notificaciones como leídas
        POST /api/notifications/notificaciones/marcar_leidas/
        Body: {"notificacion_ids": ["uuid1", "uuid2", ...]}
        """
        serializer = MarcarLeidaSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        notificacion_ids = serializer.validated_data['notificacion_ids']
        
        # Marcar como leídas
        notificaciones = Notificacion.objects.filter(
            id__in=notificacion_ids,
            usuario=request.user,
            leida=False
        )
        
        for notificacion in notificaciones:
            notificacion.marcar_como_leida()
        
        count = notificaciones.count()
        
        logger.info(f"Usuario {request.user.username} marcó {count} notificaciones como leídas")
        
        return Response({
            'success': True,
            'message': f'{count} notificaciones marcadas como leídas',
            'notificaciones_actualizadas': count
        })
    
    @action(detail=False, methods=['post'])
    def marcar_todas_leidas(self, request):
        """
        Marcar todas las notificaciones no leídas como leídas
        POST /api/notifications/notificaciones/marcar_todas_leidas/
        """
        notificaciones_no_leidas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        )
        
        count = 0
        for notificacion in notificaciones_no_leidas:
            notificacion.marcar_como_leida()
            count += 1
        
        logger.info(f"Usuario {request.user.username} marcó todas sus notificaciones como leídas ({count})")
        
        return Response({
            'success': True,
            'message': f'Todas las notificaciones marcadas como leídas',
            'notificaciones_actualizadas': count
        })
    
    @action(detail=True, methods=['post'])
    def marcar_leida(self, request, pk=None):
        """
        Marcar una notificación específica como leída
        POST /api/notifications/notificaciones/{id}/marcar_leida/
        """
        notificacion = self.get_object()
        
        if notificacion.usuario != request.user:
            return Response(
                {'error': 'No tienes permisos para modificar esta notificación'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        notificacion.marcar_como_leida()
        
        return Response({
            'success': True,
            'message': 'Notificación marcada como leída',
            'fecha_leida': notificacion.fecha_leida
        })
    
    @action(detail=False, methods=['get'])
    def no_leidas(self, request):
        """
        Obtener solo notificaciones no leídas
        GET /api/notifications/notificaciones/no_leidas/
        """
        notificaciones = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).order_by('-fecha_creacion')
        
        serializer = self.get_serializer(notificaciones, many=True)
        
        return Response({
            'count': notificaciones.count(),
            'notificaciones': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def por_tipo(self, request):
        """
        Obtener notificaciones agrupadas por tipo
        GET /api/notifications/notificaciones/por_tipo/
        """
        tipos_disponibles = [choice[0] for choice in Notificacion.TIPOS_NOTIFICACION]
        resultado = {}
        
        for tipo in tipos_disponibles:
            notificaciones = Notificacion.objects.filter(
                usuario=request.user,
                tipo=tipo
            ).order_by('-fecha_creacion')[:10]  # Últimas 10 por tipo
            
            if notificaciones.exists():
                serializer = self.get_serializer(notificaciones, many=True)
                resultado[tipo] = {
                    'count': notificaciones.count(),
                    'notificaciones': serializer.data
                }
        
        return Response(resultado)
    
    @action(detail=False, methods=['delete'])
    def limpiar_antiguas(self, request):
        """
        Eliminar notificaciones antiguas (más de 30 días y leídas)
        DELETE /api/notifications/notificaciones/limpiar_antiguas/
        """
        fecha_limite = timezone.now() - timedelta(days=30)
        
        notificaciones_antiguas = Notificacion.objects.filter(
            usuario=request.user,
            leida=True,
            fecha_creacion__lt=fecha_limite
        )
        
        count = notificaciones_antiguas.count()
        notificaciones_antiguas.delete()
        
        logger.info(f"Usuario {request.user.username} eliminó {count} notificaciones antiguas")
        
        return Response({
            'success': True,
            'message': f'{count} notificaciones antiguas eliminadas',
            'notificaciones_eliminadas': count
        })


class PreferenciasNotificacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de preferencias de notificación
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PreferenciasNotificacionSerializer
    
    def get_queryset(self):
        """Solo las preferencias del usuario autenticado"""
        return PreferenciasNotificacion.objects.filter(usuario=self.request.user)
    
    def get_object(self):
        """Obtener o crear preferencias del usuario"""
        preferencias, created = PreferenciasNotificacion.get_or_create_for_user(
            self.request.user
        )
        return preferencias
    
    @action(detail=False, methods=['get'])
    def mis_preferencias(self, request):
        """
        Obtener las preferencias del usuario autenticado
        GET /api/notifications/preferencias/mis_preferencias/
        """
        preferencias = self.get_object()
        serializer = self.get_serializer(preferencias)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def actualizar_preferencias(self, request):
        """
        Actualizar las preferencias del usuario
        PUT/PATCH /api/notifications/preferencias/actualizar_preferencias/
        """
        preferencias = self.get_object()
        serializer = self.get_serializer(
            preferencias, 
            data=request.data, 
            partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(f"Usuario {request.user.username} actualizó sus preferencias de notificación")
        
        return Response({
            'success': True,
            'message': 'Preferencias actualizadas exitosamente',
            'preferencias': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def restaurar_por_defecto(self, request):
        """
        Restaurar preferencias por defecto
        POST /api/notifications/preferencias/restaurar_por_defecto/
        """
        preferencias = self.get_object()
        
        # Restaurar valores por defecto basados en el rol
        user_role = request.user.role
        
        # Valores por defecto generales
        defaults = {
            'tercero_asignado': True,
            'tercero_aprobado': True,
            'tercero_rechazado': True,
            'documento_subido': True,
            'revision_requerida': True,
            'estado_cambiado': True,
            'alerta_cumplimiento': True,
            'sistema': True,
            'recordatorio': True,
            'rol_cambiado': True,
            'notificaciones_email': True,
            'notificaciones_push': True,
            'notificaciones_en_app': True,
            'resumen_diario': False,
            'resumen_semanal': False,
        }
        
        # Ajustes específicos por rol
        if user_role in ['administrador', 'gestion_humana']:
            defaults['usuario_creado'] = True
        
        # Aplicar valores
        for campo, valor in defaults.items():
            setattr(preferencias, campo, valor)
        
        preferencias.save()
        
        serializer = self.get_serializer(preferencias)
        
        logger.info(f"Usuario {request.user.username} restauró sus preferencias por defecto")
        
        return Response({
            'success': True,
            'message': 'Preferencias restauradas por defecto',
            'preferencias': serializer.data
        })


class NotificacionAdminViewSet(viewsets.ModelViewSet):
    """
    ViewSet para administración de notificaciones (solo administradores)
    """
    permission_classes = [IsAdministrador]
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer
    
    @action(detail=False, methods=['post'])
    def crear_masiva(self, request):
        """
        Crear notificaciones masivas para múltiples usuarios
        POST /api/notifications/admin/crear_masiva/
        """
        serializer = CrearNotificacionMasivaSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        resultado = serializer.save()
        
        logger.info(
            f"Administrador {request.user.username} creó {resultado['notificaciones_creadas']} "
            f"notificaciones masivas para {resultado['usuarios_notificados']} usuarios"
        )
        
        return Response({
            'success': True,
            'message': 'Notificaciones masivas creadas exitosamente',
            **resultado
        })
    
    @action(detail=False, methods=['get'])
    def estadisticas_generales(self, request):
        """
        Estadísticas generales de notificaciones del sistema
        GET /api/notifications/admin/estadisticas_generales/
        """
        # Estadísticas básicas
        total_notificaciones = Notificacion.objects.count()
        notificaciones_no_leidas = Notificacion.objects.filter(leida=False).count()
        
        # Por tipo
        por_tipo = dict(
            Notificacion.objects.values('tipo')
            .annotate(count=Count('id'))
            .values_list('tipo', 'count')
        )
        
        # Por prioridad
        por_prioridad = dict(
            Notificacion.objects.values('prioridad')
            .annotate(count=Count('id'))
            .values_list('prioridad', 'count')
        )
        
        # Notificaciones del último mes
        ultimo_mes = timezone.now() - timedelta(days=30)
        notificaciones_mes = Notificacion.objects.filter(
            fecha_creacion__gte=ultimo_mes
        ).count()
        
        # Usuarios más activos (que más notificaciones reciben)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        usuarios_activos = User.objects.annotate(
            num_notificaciones=Count('notificaciones')
        ).order_by('-num_notificaciones')[:10]
        
        usuarios_stats = []
        for usuario in usuarios_activos:
            usuarios_stats.append({
                'id': str(usuario.id),
                'nombre': usuario.get_full_name(),
                'email': usuario.email,
                'role': usuario.role,
                'total_notificaciones': usuario.num_notificaciones,
                'no_leidas': usuario.notificaciones.filter(leida=False).count()
            })
        
        return Response({
            'total_notificaciones': total_notificaciones,
            'notificaciones_no_leidas': notificaciones_no_leidas,
            'notificaciones_ultimo_mes': notificaciones_mes,
            'por_tipo': por_tipo,
            'por_prioridad': por_prioridad,
            'usuarios_mas_activos': usuarios_stats
        })
    
    @action(detail=False, methods=['delete'])
    def limpiar_sistema(self, request):
        """
        Limpiar notificaciones antiguas del sistema
        DELETE /api/notifications/admin/limpiar_sistema/
        """
        dias = int(request.query_params.get('dias', 60))
        fecha_limite = timezone.now() - timedelta(days=dias)
        
        # Solo eliminar notificaciones leídas y antiguas
        notificaciones_antiguas = Notificacion.objects.filter(
            leida=True,
            fecha_creacion__lt=fecha_limite
        )
        
        count = notificaciones_antiguas.count()
        notificaciones_antiguas.delete()
        
        logger.info(
            f"Administrador {request.user.username} limpió {count} "
            f"notificaciones del sistema (más de {dias} días)"
        )
        
        return Response({
            'success': True,
            'message': f'{count} notificaciones antiguas eliminadas del sistema',
            'notificaciones_eliminadas': count,
            'dias_limite': dias
        })


# Nuevas funciones independientes para eliminación de notificaciones
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """
    Eliminar una notificación específica del usuario autenticado
    DELETE /api/notifications/notificaciones/{notification_id}/
    """
    try:
        # Verificar que la notificación existe y pertenece al usuario
        notificacion = Notificacion.objects.get(
            id=notification_id,
            usuario=request.user
        )
        
        # Guardar información para log
        titulo = notificacion.titulo
        tipo = notificacion.tipo
        
        # Eliminar la notificación
        notificacion.delete()
        
        logger.info(
            f"Usuario {request.user.username} eliminó notificación: "
            f"{titulo} (tipo: {tipo}, id: {notification_id})"
        )
        
        return Response({
            'success': True,
            'message': 'Notificación eliminada correctamente',
            'notification_id': notification_id
        }, status=status.HTTP_200_OK)
        
    except Notificacion.DoesNotExist:
        logger.warning(
            f"Usuario {request.user.username} intentó eliminar "
            f"notificación inexistente o no autorizada: {notification_id}"
        )
        return Response({
            'success': False,
            'error': 'Notificación no encontrada o no tienes permisos para eliminarla'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(
            f"Error eliminando notificación {notification_id} "
            f"para usuario {request.user.username}: {str(e)}"
        )
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    """
    Eliminar todas las notificaciones del usuario autenticado
    DELETE /api/notifications/notificaciones/limpiar_todas/
    
    Query params opcionales:
    - solo_leidas: true/false (por defecto: false)
    - tipo: filtrar por tipo específico
    - mas_antiguos_que: dias (ej: 30 para eliminar las de más de 30 días)
    """
    try:
        # Construir queryset base
        queryset = Notificacion.objects.filter(usuario=request.user)
        
        # Filtros opcionales
        solo_leidas = request.query_params.get('solo_leidas', 'false').lower() == 'true'
        if solo_leidas:
            queryset = queryset.filter(leida=True)
        
        tipo = request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        mas_antiguos_que = request.query_params.get('mas_antiguos_que')
        if mas_antiguos_que:
            try:
                dias = int(mas_antiguos_que)
                fecha_limite = timezone.now() - timedelta(days=dias)
                queryset = queryset.filter(fecha_creacion__lt=fecha_limite)
            except ValueError:
                return Response({
                    'success': False,
                    'error': 'El parámetro mas_antiguos_que debe ser un número entero'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Contar antes de eliminar
        count = queryset.count()
        
        # Obtener información para el log
        tipos_eliminados = list(queryset.values_list('tipo', flat=True).distinct())
        
        # Eliminar notificaciones
        queryset.delete()
        
        # Log de la operación
        filtros_aplicados = []
        if solo_leidas:
            filtros_aplicados.append("solo leídas")
        if tipo:
            filtros_aplicados.append(f"tipo: {tipo}")
        if mas_antiguos_que:
            filtros_aplicados.append(f"más antiguos que {mas_antiguos_que} días")
        
        filtros_str = f" ({', '.join(filtros_aplicados)})" if filtros_aplicados else ""
        
        logger.info(
            f"Usuario {request.user.username} eliminó {count} notificaciones{filtros_str}. "
            f"Tipos eliminados: {tipos_eliminados}"
        )
        
        # Preparar mensaje de respuesta
        if count == 0:
            message = "No se encontraron notificaciones para eliminar"
        elif count == 1:
            message = "Se eliminó 1 notificación"
        else:
            message = f"Se eliminaron {count} notificaciones"
        
        if filtros_aplicados:
            message += f" ({', '.join(filtros_aplicados)})"
        
        return Response({
            'success': True,
            'message': message,
            'count': count,
            'tipos_eliminados': tipos_eliminados,
            'filtros_aplicados': {
                'solo_leidas': solo_leidas,
                'tipo': tipo,
                'mas_antiguos_que': mas_antiguos_que
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(
            f"Error eliminando notificaciones para usuario {request.user.username}: {str(e)}"
        )
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_multiple_notifications(request):
    """
    Eliminar múltiples notificaciones específicas del usuario autenticado
    DELETE /api/notifications/notificaciones/eliminar_multiples/
    Body: {"notification_ids": ["uuid1", "uuid2", "uuid3"]}
    """
    try:
        notification_ids = request.data.get('notification_ids', [])
        
        if not notification_ids:
            return Response({
                'success': False,
                'error': 'Se requiere una lista de IDs de notificaciones'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(notification_ids, list):
            return Response({
                'success': False,
                'error': 'notification_ids debe ser una lista'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que todas las notificaciones existen y pertenecen al usuario
        notificaciones = Notificacion.objects.filter(
            id__in=notification_ids,
            usuario=request.user
        )
        
        found_ids = list(notificaciones.values_list('id', flat=True))
        not_found_ids = [nid for nid in notification_ids if nid not in [str(fid) for fid in found_ids]]
        
        # Eliminar las notificaciones encontradas
        count = notificaciones.count()
        tipos_eliminados = list(notificaciones.values_list('tipo', flat=True).distinct())
        notificaciones.delete()
        
        logger.info(
            f"Usuario {request.user.username} eliminó {count} notificaciones específicas. "
            f"IDs: {found_ids}, Tipos: {tipos_eliminados}"
        )
        
        response_data = {
            'success': True,
            'message': f'Se eliminaron {count} notificaciones',
            'count': count,
            'eliminated_ids': [str(nid) for nid in found_ids],
            'tipos_eliminados': tipos_eliminados
        }
        
        if not_found_ids:
            response_data['warnings'] = f'No se encontraron {len(not_found_ids)} notificaciones'
            response_data['not_found_ids'] = not_found_ids
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(
            f"Error eliminando notificaciones múltiples para usuario {request.user.username}: {str(e)}"
        )
        return Response({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
