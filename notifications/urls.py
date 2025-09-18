from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificacionViewSet, PreferenciasNotificacionViewSet, NotificacionAdminViewSet,
    delete_notification, clear_all_notifications, delete_multiple_notifications
)
from .api_views import (
    notificaciones_tiempo_real, crear_notificacion_test, contador_notificaciones,
    notificaciones_recientes, simular_eventos
)

router = DefaultRouter()
router.register(r'notificaciones', NotificacionViewSet, basename='notificacion')
router.register(r'preferencias', PreferenciasNotificacionViewSet, basename='preferencias')
router.register(r'admin', NotificacionAdminViewSet, basename='admin')

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints especiales para el frontend
    path('tiempo-real/', notificaciones_tiempo_real, name='tiempo-real'),
    path('contador/', contador_notificaciones, name='contador'),
    path('recientes/', notificaciones_recientes, name='recientes'),
    
    # Endpoints de eliminación de notificaciones (deben ir antes del router para evitar conflictos)
    path('delete/<str:notification_id>/', delete_notification, name='delete-notification'),
    path('clear-all/', clear_all_notifications, name='clear-all-notifications'),
    path('delete-multiple/', delete_multiple_notifications, name='delete-multiple-notifications'),
    
    # Endpoints de testing/desarrollo
    path('test/', crear_notificacion_test, name='test'),
    path('simular-eventos/', simular_eventos, name='simular-eventos'),
]
