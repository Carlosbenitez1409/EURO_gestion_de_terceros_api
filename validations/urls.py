from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router para ViewSets
router = DefaultRouter()
router.register(r'listas-restrictivas', views.ListaRestrictivaViewSet, basename='lista-restrictiva')
router.register(r'validaciones', views.ValidacionTerceroViewSet, basename='validacion')
router.register(r'coincidencias', views.CoincidenciaListaViewSet, basename='coincidencia')

app_name = 'validations'

urlpatterns = [
    # Rutas del router
    path('', include(router.urls)),
    
    # Rutas adicionales
    path('terceros/<uuid:tercero_id>/validate/', views.ValidateTerceroView.as_view(), name='validate-tercero'),
    path('coincidencias/<int:pk>/mark-false-positive/', views.MarkFalsePositiveView.as_view(), name='mark-false-positive'),
]
