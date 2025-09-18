from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import CustomTokenObtainPairView, current_user, empleados_list
from accounts.views_users import UserManagementViewSet
from terceros.views import comerciales_disponibles_publico
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (  # type: ignore
    TokenRefreshView,
    TokenVerifyView,
)
from . import views

# Router para user-management directo
user_management_router = DefaultRouter()
user_management_router.register(r'user-management', UserManagementViewSet, basename='user-management-direct')

urlpatterns = [
    # Root endpoints
    path('api/', views.api_root, name='api_root'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication endpoints
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/auth/me/', current_user, name='current_user'),
    
    # Ruta directa para user-management (para compatibilidad con frontend)
    path('api/', include(user_management_router.urls)),
    
    # Ruta específica para empleados
    path('api/empleados/', empleados_list, name='empleados-list'),
    
    # Ruta específica para comerciales públicos (ANTES de DRF para que no sea interceptada)
    path('api/public/comerciales-disponibles/', comerciales_disponibles_publico, name='comerciales-publico-directo'),
    
    # API endpoints - DRF includes
    path('api/accounts/', include('accounts.urls')),
    path('api/', include('terceros.urls')),
    # path('api/documents/', include('documents.urls')),  # Comentado para evitar conflictos
    path('api/validations/', include('validations.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    path('api/notifications/', include('notifications.urls')),  # Agregar URLs de notificaciones
    path('api/stradata/', include('stradata_consulta.urls')),  # URLs de Stradata
    # path('api/debida-diligencia/', include('debida_diligencia.urls')),  # Eliminado - usar sistema terceros
    path('api/email/', include('euro_terceros.email_urls')),  # URLs del sistema de correos
]

# Admin site configuration
admin.site.site_header = "EURO Sistema de Gestión de Terceros"
admin.site.site_title = "EURO Admin"
admin.site.index_title = "Panel de Administración"

# Serve media files in development
# Servir archivos estáticos y de medios durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

