from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from .models import TipoDocumento, DocumentoTercero, HistorialDocumento
from .serializers import (
    TipoDocumentoSerializer,
    DocumentoTerceroSerializer,
    DocumentoTerceroListSerializer,
    DocumentoTerceroUploadSerializer,
    HistorialDocumentoSerializer,
    DocumentoValidacionSerializer
)
from terceros.models import Tercero
from terceros.permissions import TerceroPermissions
import logging

logger = logging.getLogger(__name__)


class TipoDocumentoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para tipos de documentos (solo lectura)
    """
    queryset = TipoDocumento.objects.filter(activo=True).order_by('orden', 'nombre')
    serializer_class = TipoDocumentoSerializer
    permission_classes = [IsAuthenticated]


class DocumentoTerceroViewSet(viewsets.ModelViewSet):
    """
    ViewSet para documentos de terceros
    """
    queryset = DocumentoTercero.objects.all()
    serializer_class = DocumentoTerceroSerializer
    permission_classes = [TerceroPermissions]  # Usar los mismos permisos que terceros


class DocumentosByTerceroView(generics.ListAPIView):
    """
    Vista para obtener todos los documentos de un tercero específico
    """
    serializer_class = DocumentoTerceroListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        tercero_id = self.kwargs.get('tercero_id')
        return DocumentoTercero.objects.filter(
            tercero_id=tercero_id
        ).order_by('tipo_documento__orden', '-fecha_subida')


class DocumentosEstadisticasView(generics.GenericAPIView):
    """
    Vista para estadísticas generales de documentos
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        total_documentos = DocumentoTercero.objects.count()
        pendientes = DocumentoTercero.objects.filter(estado_validacion='pendiente').count()
        aprobados = DocumentoTercero.objects.filter(estado_validacion='aprobado').count()
        rechazados = DocumentoTercero.objects.filter(estado_validacion='rechazado').count()
        requiere_ajustes = DocumentoTercero.objects.filter(estado_validacion='requiere_ajustes').count()
        
        return Response({
            'total_documentos': total_documentos,
            'pendientes': pendientes,
            'aprobados': aprobados,
            'rechazados': rechazados,
            'requiere_ajustes': requiere_ajustes,
            'por_estado': {
                'pendiente': pendientes,
                'aprobado': aprobados,
                'rechazado': rechazados,
                'requiere_ajustes': requiere_ajustes
            }
        })
