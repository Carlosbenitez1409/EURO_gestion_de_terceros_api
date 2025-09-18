from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TerceroViewSet, 
    DocumentoTerceroViewSet,
    InformacionPEPViewSet,
    HistorialTerceroViewSet,
    comerciales_disponibles_publico,
    transiciones_disponibles,
    # cambiar_estado_tercero,  # Comentado: no se usa, se usa el del ViewSet
    TransicionesDisponiblesView,
    ejecutar_scraping_tercero,
    ejecutar_scraping_masivo,
    obtener_documentos_stradata,
    listar_documentos_tercero,
    TerceroHistorialAPIView,
    tercero_estadisticas,
    tercero_historial_detallado,
    # Endpoints de Debida Diligencia
    listar_documentos_debida_diligencia,
    subir_documento_debida_diligencia,
    eliminar_documento_debida_diligencia,
    descargar_documento_debida_diligencia,
    opciones_debida_diligencia,
    # Endpoint de Exportar
    exportar_tercero_excel
)

router = DefaultRouter()
router.register(r'terceros', TerceroViewSet, basename='tercero')
router.register(r'terceros-documentos', DocumentoTerceroViewSet, basename='documento-tercero')
router.register(r'informacion-pep', InformacionPEPViewSet, basename='informacion-pep')
router.register(r'historial-terceros', HistorialTerceroViewSet, basename='historial-tercero')

urlpatterns = [
    # URLs específicas ANTES del router para evitar conflictos
    path('comerciales-disponibles/', comerciales_disponibles_publico, name='comerciales-disponibles'),
    path('transiciones-disponibles/', TransicionesDisponiblesView.as_view(), name='transiciones-disponibles'),
    # path('terceros/<uuid:tercero_id>/cambiar_estado/', cambiar_estado_tercero, name='cambiar-estado-tercero'),  # Comentado: conflicto con DRF ViewSet
    path('terceros/<uuid:tercero_id>/scraping/', ejecutar_scraping_tercero, name='ejecutar-scraping-tercero'),
    path('terceros/scraping-masivo/', ejecutar_scraping_masivo, name='ejecutar-scraping-masivo'),
    path('terceros/<uuid:tercero_id>/documentos/', listar_documentos_tercero, name='listar-documentos-tercero'),
    path('terceros/<uuid:tercero_id>/documentos-stradata/', obtener_documentos_stradata, name='documentos-stradata'),
    path('terceros/<uuid:tercero_id>/historial/', TerceroHistorialAPIView.as_view(), name='tercero-historial'),
    path('terceros/<uuid:tercero_id>/estadisticas/', tercero_estadisticas, name='tercero-estadisticas'),
    path('terceros/<uuid:tercero_id>/historial-detallado/', tercero_historial_detallado, name='tercero-historial-detallado'),
    
    # URLs específicas para Debida Diligencia
    path('terceros/<uuid:tercero_id>/debida-diligencia/', listar_documentos_debida_diligencia, name='listar-documentos-dd'),
    path('terceros/<uuid:tercero_id>/debida-diligencia/upload/', subir_documento_debida_diligencia, name='subir-documento-dd'),
    path('terceros/debida-diligencia/<uuid:documento_id>/', eliminar_documento_debida_diligencia, name='eliminar-documento-dd'),
    path('terceros/debida-diligencia/<uuid:documento_id>/download/', descargar_documento_debida_diligencia, name='descargar-documento-dd'),
    path('terceros/debida-diligencia/opciones/', opciones_debida_diligencia, name='opciones-dd'),
    
    # URL para exportar tercero a Excel
    path('terceros/<uuid:tercero_id>/exportar/', exportar_tercero_excel, name='exportar-tercero-excel'),
    
    # Router genérico al final
    path('', include(router.urls)),
]
