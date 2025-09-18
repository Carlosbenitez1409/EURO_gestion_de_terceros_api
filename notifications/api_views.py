from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from notifications.models import Notificacion
from notifications.serializers import NotificacionSerializer
import json


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notificaciones_tiempo_real(request):
    """
    Endpoint para obtener notificaciones en tiempo real
    Usado por el frontend para polling o WebSocket
    
    GET /api/notifications/tiempo-real/
    """
    usuario = request.user
    
    # Obtener timestamp de la última consulta
    ultimo_check = request.query_params.get('ultimo_check')
    if ultimo_check:
        try:
            ultimo_check = timezone.datetime.fromisoformat(ultimo_check.replace('Z', '+00:00'))
        except ValueError:
            ultimo_check = None
    
    # Filtrar notificaciones nuevas
    queryset = Notificacion.objects.filter(usuario=usuario)
    
    if ultimo_check:
        # Solo notificaciones posteriores al último check
        queryset = queryset.filter(fecha_creacion__gt=ultimo_check)
    else:
        # Últimas 10 notificaciones si no hay timestamp
        queryset = queryset[:10]
    
    # Ordenar por fecha de creación descendente
    notificaciones = queryset.order_by('-fecha_creacion')
    
    # Serializar
    serializer = NotificacionSerializer(notificaciones, many=True)
    
    # Estadísticas rápidas
    total_no_leidas = Notificacion.objects.filter(
        usuario=usuario, 
        leida=False
    ).count()
    
    return Response({
        'notificaciones': serializer.data,
        'total_no_leidas': total_no_leidas,
        'timestamp': timezone.now().isoformat(),
        'nuevas_notificaciones': notificaciones.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def crear_notificacion_test(request):
    """
    Endpoint para crear notificaciones de prueba (solo para desarrollo)
    
    POST /api/notifications/test/
    Body: {
        "titulo": "string",
        "mensaje": "string", 
        "tipo": "sistema",
        "prioridad": "media"
    }
    """
    from notifications.utils import NotificationService
    
    titulo = request.data.get('titulo', 'Notificación de prueba')
    mensaje = request.data.get('mensaje', 'Esta es una notificación de prueba del sistema')
    tipo = request.data.get('tipo', 'sistema')
    prioridad = request.data.get('prioridad', 'media')
    
    notificacion = Notificacion.crear_notificacion(
        usuario=request.user,
        titulo=titulo,
        mensaje=mensaje,
        tipo=tipo,
        prioridad=prioridad,
        datos_extra={'test': True, 'created_by': 'api_test'}
    )
    
    serializer = NotificacionSerializer(notificacion)
    
    return Response({
        'success': True,
        'message': 'Notificación de prueba creada',
        'notificacion': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contador_notificaciones(request):
    """
    Endpoint ligero para obtener solo el contador de notificaciones no leídas
    Ideal para mostrar el badge en el header
    
    GET /api/notifications/contador/
    """
    usuario = request.user
    
    no_leidas = Notificacion.objects.filter(
        usuario=usuario,
        leida=False
    ).count()
    
    # Contar por prioridad
    criticas = Notificacion.objects.filter(
        usuario=usuario,
        leida=False,
        prioridad='critica'
    ).count()
    
    altas = Notificacion.objects.filter(
        usuario=usuario,
        leida=False,
        prioridad='alta'
    ).count()
    
    return Response({
        'total_no_leidas': no_leidas,
        'criticas': criticas,
        'altas': altas,
        'timestamp': timezone.now().isoformat()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notificaciones_recientes(request):
    """
    Endpoint para obtener las notificaciones más recientes
    Para mostrar en dropdown o panel de notificaciones
    
    GET /api/notifications/recientes/?limit=5
    """
    usuario = request.user
    limite = int(request.query_params.get('limit', 5))
    
    notificaciones = Notificacion.objects.filter(
        usuario=usuario
    ).order_by('-fecha_creacion')[:limite]
    
    serializer = NotificacionSerializer(notificaciones, many=True)
    
    return Response({
        'notificaciones': serializer.data,
        'total_sistema': Notificacion.objects.filter(usuario=usuario).count(),
        'timestamp': timezone.now().isoformat()
    })


@api_view(['POST']) 
@permission_classes([IsAuthenticated])
def simular_eventos(request):
    """
    Endpoint para simular eventos y generar notificaciones
    Solo para testing y desarrollo
    
    POST /api/notifications/simular-eventos/
    Body: {"evento": "tercero_asignado|documento_subido|estado_cambiado"}
    """
    from notifications.utils import NotificationService
    from terceros.models import Tercero
    import random
    
    evento = request.data.get('evento', 'sistema')
    usuario = request.user
    
    if evento == 'tercero_asignado':
        # Simular asignación de tercero
        notificacion = Notificacion.crear_notificacion(
            usuario=usuario,
            titulo="Tercero asignado (SIMULACIÓN)",
            mensaje="Se te ha asignado un nuevo tercero para gestión",
            tipo='tercero_asignado',
            prioridad='media',
            datos_extra={'simulacion': True}
        )
        
    elif evento == 'documento_subido':
        # Simular subida de documento
        notificacion = Notificacion.crear_notificacion(
            usuario=usuario,
            titulo="Documento subido (SIMULACIÓN)",
            mensaje="Se ha subido un nuevo documento que requiere revisión",
            tipo='documento_subido',
            prioridad='alta',
            datos_extra={'simulacion': True}
        )
        
    elif evento == 'estado_cambiado':
        # Simular cambio de estado
        estados = ['aprobado', 'rechazado', 'requiere_ajustes']
        estado = random.choice(estados)
        
        notificacion = Notificacion.crear_notificacion(
            usuario=usuario,
            titulo=f"Tercero {estado} (SIMULACIÓN)",
            mensaje=f"Un tercero ha cambiado su estado a: {estado}",
            tipo='tercero_aprobado' if estado == 'aprobado' else 'tercero_rechazado',
            prioridad='alta',
            datos_extra={'simulacion': True, 'estado': estado}
        )
        
    elif evento == 'alerta_cumplimiento':
        # Simular alerta de cumplimiento
        notificacion = Notificacion.crear_notificacion(
            usuario=usuario,
            titulo="Alerta de cumplimiento (SIMULACIÓN)",
            mensaje="Se ha detectado un tercero que requiere revisión SARLAFT",
            tipo='alerta_cumplimiento',
            prioridad='critica',
            datos_extra={'simulacion': True}
        )
        
    else:
        # Notificación del sistema por defecto
        notificacion = Notificacion.crear_notificacion(
            usuario=usuario,
            titulo="Notificación del sistema (SIMULACIÓN)",
            mensaje="Esta es una notificación de prueba del sistema",
            tipo='sistema',
            prioridad='baja',
            datos_extra={'simulacion': True}
        )
    
    serializer = NotificacionSerializer(notificacion)
    
    return Response({
        'success': True,
        'message': f'Evento "{evento}" simulado exitosamente',
        'notificacion': serializer.data
    })
