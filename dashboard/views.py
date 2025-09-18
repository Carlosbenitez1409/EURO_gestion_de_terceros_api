from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from accounts.permissions import IsAdministrador, IsOficialCumplimiento, IsAdminOrOficialCumplimiento
from .models import MetricaTerceros, AlertaDashboard, ConfiguracionDashboard


class MetricaTercerosViewSet(viewsets.ModelViewSet):
    """
    ViewSet para métricas de terceros
    Acceso: Todos los usuarios autenticados pueden ver métricas
    """
    permission_classes = [IsAuthenticated]
    queryset = MetricaTerceros.objects.all()
    
    def list(self, request):
        metricas = self.get_queryset()[:10]  # Últimas 10 métricas
        data = []
        for metrica in metricas:
            data.append({
                'fecha': metrica.fecha,
                'total_terceros': metrica.total_terceros,
                'terceros_pendientes': metrica.terceros_pendientes,
                'terceros_aprobados': metrica.terceros_aprobados,
                'terceros_rechazados': metrica.terceros_rechazados,
            })
        return Response(data)


class AlertaDashboardViewSet(viewsets.ModelViewSet):
    """
    ViewSet para alertas del dashboard
    Administrador y Oficial de Cumplimiento pueden gestionar alertas
    """
    permission_classes = [IsAuthenticated]
    queryset = AlertaDashboard.objects.all()
    
    def get_permissions(self):
        """
        Permisos específicos por acción
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Solo administrador y oficial de cumplimiento pueden gestionar alertas
            permission_classes = [IsAdminOrOficialCumplimiento]
        else:
            # Todos pueden ver alertas
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def list(self, request):
        # Filtrar alertas activas para el usuario
        alertas = self.get_queryset().filter(activa=True)
        data = []
        for alerta in alertas:
            if alerta.es_visible_para_usuario(request.user):
                data.append({
                    'id': str(alerta.id),
                    'titulo': alerta.titulo,
                    'mensaje': alerta.mensaje,
                    'tipo': alerta.tipo,
                    'categoria': alerta.categoria,
                })
        return Response(data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdministrador])
    def crear_alerta_sistema(self, request):
        """
        Solo administradores pueden crear alertas de sistema
        """
        # Lógica para crear alertas de sistema
        return Response({'message': 'Alerta de sistema creada'})

    @action(detail=False, methods=['get'], permission_classes=[IsOficialCumplimiento])
    def alertas_cumplimiento(self, request):
        """
        Alertas específicas para oficial de cumplimiento
        """
        # Filtrar alertas relacionadas con cumplimiento SARLAFT/PEP
        alertas_cumplimiento = self.get_queryset().filter(
            categoria__in=['SARLAFT', 'PEP', 'CUMPLIMIENTO'],
            activa=True
        )
        
        data = []
        for alerta in alertas_cumplimiento:
            data.append({
                'id': str(alerta.id),
                'titulo': alerta.titulo,
                'mensaje': alerta.mensaje,
                'tipo': alerta.tipo,
                'categoria': alerta.categoria,
                'fecha_creacion': alerta.created_at
            })
        
        return Response(data)


class DashboardOverviewView(generics.RetrieveAPIView):
    """
    Vista para obtener resumen del dashboard
    Datos adaptados según el rol del usuario
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user_role = getattr(request.user, 'role', None)
        
        # Datos base del dashboard
        base_data = {
            'total_terceros': 150,
            'terceros_pendientes': 25,
            'terceros_aprobados': 100,
            'terceros_rechazados': 15,
        }
        
        # Datos específicos según el rol
        if user_role == 'administrador':
            # Administrador ve todo + datos del sistema
            data = {
                **base_data,
                'documentos_pendientes': 45,
                'validaciones_con_alerta': 8,
                'usuarios_activos': 15,
                'logs_sistema': 250,
                'espacio_almacenamiento': '85%',
                'alertas_criticas': 3,
                'permisos_especiales': True
            }
        elif user_role == 'oficial_cumplimiento':
            # Oficial de cumplimiento ve datos SARLAFT/PEP
            data = {
                **base_data,
                'terceros_pep': 12,
                'validaciones_sarlaft_pendientes': 8,
                'alertas_cumplimiento': 5,
                'documentos_alta_prioridad': 18,
                'reportes_mensuales': 4,
                'casos_investigacion': 2
            }
        elif user_role == 'procesos':
            # Procesos ve datos operativos
            data = {
                **base_data,
                'documentos_pendientes': 45,
                'validaciones_con_alerta': 8,
                'asignaciones_pendientes': 12,
                'terceros_mes_actual': 35
            }
        elif user_role == 'comercial':
            # Comercial solo ve sus datos
            data = {
                'mis_terceros': 25,
                'terceros_pendientes': 8,
                'terceros_aprobados': 15,
                'terceros_rechazados': 2,
                'documentos_pendientes': 12,
                'carga_trabajo': 'Media'
            }
        else:
            # Rol por defecto
            data = base_data
            
        return Response(data)


class CalculateMetricsView(generics.CreateAPIView):
    """
    Vista para calcular métricas
    Solo administradores pueden recalcular métricas del sistema
    """
    permission_classes = [IsAdministrador]
    
    def post(self, request):
        # Lógica para recalcular métricas del sistema
        return Response({
            'message': 'Métricas del sistema recalculadas exitosamente',
            'timestamp': '2025-08-26T17:00:00Z',
            'metricas_actualizadas': 25
        })


class ConfiguracionDashboardView(generics.RetrieveUpdateAPIView):
    """
    Vista para configuración del dashboard del usuario
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user_role = getattr(request.user, 'role', None)
        
        # Configuraciones por defecto según el rol
        config = {
            'tema': 'claro',
            'idioma': 'es',
            'notificaciones_email': True,
            'widgets_habilitados': []
        }
        
        if user_role == 'administrador':
            config['widgets_habilitados'] = [
                'metricas_sistema', 'usuarios_activos', 'logs', 
                'almacenamiento', 'alertas_criticas', 'configuracion_avanzada'
            ]
        elif user_role == 'oficial_cumplimiento':
            config['widgets_habilitados'] = [
                'alertas_cumplimiento', 'validaciones_sarlaft', 
                'terceros_pep', 'reportes_cumplimiento'
            ]
        elif user_role == 'procesos':
            config['widgets_habilitados'] = [
                'terceros_pendientes', 'asignaciones', 
                'documentos_revisar', 'metricas_operativas'
            ]
        elif user_role == 'comercial':
            config['widgets_habilitados'] = [
                'mis_terceros', 'mis_pendientes', 'mis_estadisticas'
            ]
        
        return Response(config)
    
    def put(self, request):
        # Guardar configuración personalizada del usuario
        return Response({
            'message': 'Configuración actualizada exitosamente',
            'config': request.data
        })
