from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ListaRestrictiva, ValidacionTercero, CoincidenciaLista


class ListaRestrictivaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listas restrictivas
    """
    permission_classes = [IsAuthenticated]
    queryset = ListaRestrictiva.objects.all()
    
    def list(self, request):
        listas = self.get_queryset()
        data = []
        for lista in listas:
            data.append({
                'id': lista.id,
                'nombre': lista.nombre,
                'tipo_lista': lista.tipo_lista,
                'activa': lista.activa,
                'fecha_ultima_actualizacion': lista.fecha_ultima_actualizacion,
            })
        return Response(data)


class ValidacionTerceroViewSet(viewsets.ModelViewSet):
    """
    ViewSet para validaciones de terceros
    """
    permission_classes = [IsAuthenticated]
    queryset = ValidacionTercero.objects.all()
    
    def list(self, request):
        return Response({'message': 'Lista de validaciones en desarrollo'})


class CoincidenciaListaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para coincidencias en listas
    """
    permission_classes = [IsAuthenticated]
    queryset = CoincidenciaLista.objects.all()
    
    def list(self, request):
        return Response({'message': 'Lista de coincidencias en desarrollo'})


class ValidateTerceroView(generics.CreateAPIView):
    """
    Vista para validar un tercero contra listas restrictivas
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, tercero_id):
        return Response({'message': 'Validación de tercero en desarrollo'})


class MarkFalsePositiveView(generics.UpdateAPIView):
    """
    Vista para marcar una coincidencia como falso positivo
    """
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, pk):
        return Response({'message': 'Marcar falso positivo en desarrollo'})
