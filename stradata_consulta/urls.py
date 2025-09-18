from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StratadaDocumentoViewSet,
    subir_documento_stradata,
    listar_documentos_stradata,
    eliminar_documento_stradata,
    descargar_documento_stradata,
    ejecutar_consulta_stradata,
    ejecutar_consulta_tercero_completo,
    # Nuevas vistas para consulta integrada
    consultar_tercero_stradata,
    resumen_personas_tercero
)

# Router para el ViewSet
router = DefaultRouter()
router.register(r'documentos', StratadaDocumentoViewSet, basename='stradata-documento')

urlpatterns = [
    # Rutas específicas que espera el frontend
    path('terceros/<uuid:tercero_id>/documentos/subir/', subir_documento_stradata, name='subir-documento-stradata'),
    path('terceros/<uuid:tercero_id>/documentos/', listar_documentos_stradata, name='listar-documentos-stradata'),
    path('documentos/<int:documento_id>/eliminar/', eliminar_documento_stradata, name='eliminar-documento-stradata'),
    path('documentos/<int:documento_id>/descargar/', descargar_documento_stradata, name='descargar-documento-stradata'),
    
    # Endpoints para ejecutar consultas por lotes
    path('ejecutar/', ejecutar_consulta_stradata, name='ejecutar-consulta-stradata'),
    path('terceros/<uuid:tercero_id>/consultar/', ejecutar_consulta_tercero_completo, name='consultar-tercero-completo'),
    
    # Nuevos endpoints para consulta integrada con terceros
    path('terceros/<uuid:tercero_id>/consultar-stradata/', consultar_tercero_stradata, name='consultar-tercero-stradata'),
    path('terceros/<uuid:tercero_id>/resumen-personas/', resumen_personas_tercero, name='resumen-personas-tercero'),
    
    # ViewSet routes (opcionales para funcionalidad extendida)
    path('', include(router.urls)),
]