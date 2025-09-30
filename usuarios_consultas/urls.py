# usuarios_consultas/urls.py
"""
URLs para el Sistema de Usuarios GH (Consultas de Personal)
Implementación según API_SPECIFICATION_USUARIOS_GH.md
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SolicitudViewSet, PersonaViewSet, HistorialCambioViewSet,
    DescargarReporteView, ValidarPersonaView, RootRedirectView, PersonaUpdateView
)

app_name = 'usuarios_consultas'

# Configurar router estándar
router = DefaultRouter()
router.register(r'solicitudes', SolicitudViewSet, basename='solicitud')
router.register(r'personas', PersonaViewSet, basename='persona')
router.register(r'historial', HistorialCambioViewSet, basename='historial')

urlpatterns = [
    # Mapeo directo para compatibilidad con frontend - La raíz mapea a solicitudes
    path('', SolicitudViewSet.as_view({'get': 'list', 'post': 'create'}), name='solicitudes-root'),
    
    # Endpoints específicos
    path('estadisticas/', SolicitudViewSet.as_view({'get': 'estadisticas'}), name='estadisticas-directas'),
    
    # Detalle de solicitud por ID (debe ir antes de otras rutas genéricas)
    path('<uuid:pk>/', SolicitudViewSet.as_view({
        'get': 'retrieve', 
        'put': 'update', 
        'patch': 'partial_update', 
        'delete': 'destroy'
    }), name='solicitud-detalle'),
    
    # Acciones específicas de solicitud
    path('<uuid:pk>/cambiar_estado/', SolicitudViewSet.as_view({'post': 'cambiar_estado'}), name='solicitud-cambiar-estado'),
    path('<uuid:pk>/tomar_revision/', SolicitudViewSet.as_view({'post': 'tomar_revision'}), name='solicitud-tomar-revision'),
    path('<uuid:pk>/tomar-revision/', SolicitudViewSet.as_view({'post': 'tomar_revision'}), name='solicitud-tomar-revision-dash'),  # Compatibilidad frontend
    path('<uuid:pk>/asignar/', SolicitudViewSet.as_view({'post': 'asignar'}), name='solicitud-asignar'),
    path('<uuid:pk>/consultar-stradata/', SolicitudViewSet.as_view({'post': 'consultar_stradata'}), name='solicitud-consultar-stradata'),
    path('<uuid:pk>/finalizar/', SolicitudViewSet.as_view({'post': 'finalizar'}), name='solicitud-finalizar'),
    path('<uuid:pk>/devolver-gh/', SolicitudViewSet.as_view({'post': 'devolver_gh'}), name='solicitud-devolver-gh'),
    
    # Endpoints para personas dentro de solicitudes
    path('<uuid:pk>/persona/<uuid:persona_id>/', PersonaUpdateView.as_view(), name='solicitud-persona-detalle'),
    
    # Endpoints adicionales
    path('reportes/descargar/', DescargarReporteView.as_view(), name='descargar-reporte'),
    path('personas/validar/', ValidarPersonaView.as_view(), name='validar-persona'),
    
    # Rutas del router (se ejecutarán después de las específicas)
    path('api/', include(router.urls)),  # Prefix para evitar conflictos
]

# Las rutas generadas automáticamente por el router incluyen:
#
# SOLICITUDES:
# GET /solicitudes/                    - Listar solicitudes
# POST /solicitudes/                   - Crear solicitud
# GET /solicitudes/{id}/               - Detalle de solicitud
# PUT /solicitudes/{id}/               - Actualizar solicitud completa
# PATCH /solicitudes/{id}/             - Actualizar solicitud parcial
# DELETE /solicitudes/{id}/            - Eliminar solicitud
# POST /solicitudes/{id}/cambiar_estado/       - Cambiar estado
# POST /solicitudes/{id}/tomar_revision/       - Tomar para revisión
# GET /solicitudes/mis_solicitudes/            - Mis solicitudes
# GET /solicitudes/estadisticas/               - Estadísticas dashboard
#
# PERSONAS:
# GET /personas/                       - Listar personas
# POST /personas/                      - Crear persona
# GET /personas/{id}/                  - Detalle de persona
# PUT /personas/{id}/                  - Actualizar persona completa
# PATCH /personas/{id}/                - Actualizar persona parcial
# DELETE /personas/{id}/               - Eliminar persona
#
# HISTORIAL:
# GET /historial/                      - Listar historial
# GET /historial/{id}/                 - Detalle de cambio
#
# ENDPOINTS ADICIONALES:
# GET /reportes/descargar/             - Descargar reportes
# POST /personas/validar/              - Validar datos de persona