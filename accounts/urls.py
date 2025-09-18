from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_users import UserManagementViewSet
from .form_options import form_options
from .views import empleados_list, usuarios_por_rol, usuarios_disponibles_asignacion

# Configurar router con ViewSets
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'user-management', UserManagementViewSet, basename='user-management')

app_name = 'accounts'

urlpatterns = [
    # Rutas del router - proporciona CRUD completo para users
    path('', include(router.urls)),
    
    # Rutas adicionales de autenticación
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    
    # Ruta específica para empleados
    path('empleados/', empleados_list, name='empleados-list'),
    
    # Opciones para formularios
    path('form-options/', form_options, name='form-options'),
    
    # Nuevos endpoints
    path('usuarios-por-rol/<str:rol>/', usuarios_por_rol, name='usuarios-por-rol'),
    path('usuarios-disponibles/', usuarios_disponibles_asignacion, name='usuarios-disponibles'),
]
