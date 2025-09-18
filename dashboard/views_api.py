from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from terceros.models import Tercero
from accounts.models import User
from .serializers import DashboardMetricsSerializer, DashboardMainSerializer
import logging

logger = logging.getLogger(__name__)


class DashboardMetricsView(APIView):
    """
    Vista para métricas del dashboard
    GET /api/dashboard/metricas/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        logger.info(f"Getting dashboard metrics for user: {request.user.username}")
        
        # Métricas básicas de terceros
        total_terceros = Tercero.objects.count()
        pendientes = Tercero.objects.filter(estado_aprobacion='pendiente').count()
        aprobados = Tercero.objects.filter(estado_aprobacion='aprobado').count()
        rechazados = Tercero.objects.filter(estado_aprobacion='rechazado').count()
        
        # Métricas de tiempo
        hoy = timezone.now()
        inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        inicio_mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
        
        terceros_este_mes = Tercero.objects.filter(created_at__gte=inicio_mes).count()
        terceros_mes_anterior = Tercero.objects.filter(
            created_at__gte=inicio_mes_anterior,
            created_at__lt=inicio_mes
        ).count()
        
        # Calcular crecimiento mensual
        crecimiento_mensual = 0
        if terceros_mes_anterior > 0:
            crecimiento_mensual = ((terceros_este_mes - terceros_mes_anterior) / terceros_mes_anterior) * 100
        
        # Métricas por tipo de persona
        personas_naturales = Tercero.objects.filter(tipo_persona='natural').count()
        personas_juridicas = Tercero.objects.filter(tipo_persona='juridica').count()
        
        # Actividad reciente (últimos 10 terceros)
        terceros_recientes = Tercero.objects.order_by('-created_at')[:10]
        actividad_reciente = []
        for tercero in terceros_recientes:
            nombre = tercero.nombres
            if tercero.tipo_persona == 'natural' and tercero.apellidos:
                nombre = f"{tercero.nombres} {tercero.apellidos}"
            elif tercero.tipo_persona == 'juridica' and tercero.razon_social:
                nombre = tercero.razon_social
            
            actividad_reciente.append({
                'id': str(tercero.id),
                'nombre': nombre,
                'tipo': tercero.get_tipo_persona_display(),
                'estado': tercero.get_estado_aprobacion_display(),
                'fecha': tercero.created_at.isoformat(),
                'created_by': tercero.creado_por.get_full_name() if tercero.creado_por else 'Sistema'
            })
        
        # Top usuarios creadores (últimos 30 días)
        inicio_periodo = hoy - timedelta(days=30)
        top_usuarios = (
            Tercero.objects
            .filter(created_at__gte=inicio_periodo)
            .values('creado_por__username', 'creado_por__first_name', 'creado_por__last_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        
        top_usuarios_creadores = []
        for usuario in top_usuarios:
            nombre = f"{usuario['creado_por__first_name']} {usuario['creado_por__last_name']}".strip()
            if not nombre:
                nombre = usuario['creado_por__username']
            
            top_usuarios_creadores.append({
                'username': usuario['creado_por__username'],
                'nombre': nombre,
                'terceros_creados': usuario['count']
            })
        
        metrics_data = {
            'total_terceros': total_terceros,
            'pendientes_aprobacion': pendientes,
            'aprobados': aprobados,
            'rechazados': rechazados,
            'terceros_este_mes': terceros_este_mes,
            'terceros_mes_anterior': terceros_mes_anterior,
            'crecimiento_mensual': round(crecimiento_mensual, 2),
            'personas_naturales': personas_naturales,
            'personas_juridicas': personas_juridicas,
            'actividad_reciente': actividad_reciente,
            'top_usuarios_creadores': top_usuarios_creadores,
        }
        
        serializer = DashboardMetricsSerializer(metrics_data)
        return Response(serializer.data)


class DashboardMainView(APIView):
    """
    Vista principal del dashboard
    GET /api/dashboard/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        logger.info(f"Getting dashboard main view for user: {request.user.username}")
        
        user = request.user
        
        # Mensaje de bienvenida personalizado
        hora = timezone.now().hour
        if hora < 12:
            saludo = "Buenos días"
        elif hora < 18:
            saludo = "Buenas tardes"
        else:
            saludo = "Buenas noches"
        
        bienvenida = f"{saludo}, {user.get_full_name() or user.username}"
        
        # Resumen de actividad para el usuario
        terceros_creados = Tercero.objects.filter(creado_por=user).count()
        terceros_pendientes = Tercero.objects.filter(
            creado_por=user,
            estado_aprobacion='pendiente'
        ).count()
        
        resumen_actividad = {
            'terceros_creados': terceros_creados,
            'terceros_pendientes': terceros_pendientes,
            'rol': user.get_role_display(),
            'ultimo_acceso': user.last_login.isoformat() if user.last_login else None
        }
        
        # Accesos rápidos según el rol del usuario
        accesos_rapidos = []
        
        if user.role == 'comercial':
            accesos_rapidos = [
                {'titulo': 'Crear Tercero', 'icono': 'plus', 'url': '/terceros/crear'},
                {'titulo': 'Mis Terceros', 'icono': 'list', 'url': '/terceros?created_by=me'},
                {'titulo': 'Pendientes', 'icono': 'clock', 'url': '/terceros?estado=pendiente'},
            ]
        elif user.role in ['procesos', 'gestion_humana']:
            accesos_rapidos = [
                {'titulo': 'Aprobar Terceros', 'icono': 'check', 'url': '/terceros?estado=pendiente'},
                {'titulo': 'Ver Dashboard', 'icono': 'chart', 'url': '/dashboard'},
                {'titulo': 'Reportes', 'icono': 'report', 'url': '/reportes'},
                {'titulo': 'Todos los Terceros', 'icono': 'users', 'url': '/terceros'},
            ]
        
        # Notificaciones para el usuario
        notificaciones = []
        
        # Notificación para usuarios con permisos de aprobación
        if user.role in ['procesos', 'gestion_humana']:
            pendientes_count = Tercero.objects.filter(estado_aprobacion='pendiente').count()
            if pendientes_count > 0:
                notificaciones.append({
                    'tipo': 'info',
                    'titulo': 'Terceros pendientes de aprobación',
                    'mensaje': f'Hay {pendientes_count} terceros esperando aprobación',
                    'url': '/terceros?estado=pendiente'
                })
        
        # Notificación para usuarios comerciales
        if user.role == 'comercial':
            mis_rechazados = Tercero.objects.filter(
                creado_por=user,
                estado_aprobacion='rechazado'
            ).count()
            if mis_rechazados > 0:
                notificaciones.append({
                    'tipo': 'warning',
                    'titulo': 'Terceros rechazados',
                    'mensaje': f'Tienes {mis_rechazados} terceros rechazados que requieren atención',
                    'url': '/terceros?estado=rechazado&created_by=me'
                })
        
        dashboard_data = {
            'bienvenida': bienvenida,
            'resumen_actividad': resumen_actividad,
            'accesos_rapidos': accesos_rapidos,
            'notificaciones': notificaciones,
        }
        
        serializer = DashboardMainSerializer(dashboard_data)
        return Response(serializer.data)
