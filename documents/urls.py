from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router para ViewSets
router = DefaultRouter()
router.register(r'tipos-documento', views.TipoDocumentoViewSet, basename='tipo-documento')
router.register(r'documentos', views.DocumentoTerceroViewSet, basename='documento')

app_name = 'documents'

urlpatterns = [
    # Rutas del router
    path('', include(router.urls)),
    
    # Rutas adicionales
    path('terceros/<uuid:tercero_id>/documentos/', views.DocumentosByTerceroView.as_view(), name='documentos-tercero'),
    path('estadisticas/', views.DocumentosEstadisticasView.as_view(), name='documentos-estadisticas'),
]
