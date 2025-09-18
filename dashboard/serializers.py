from rest_framework import serializers


class DashboardMetricsSerializer(serializers.Serializer):
    """
    Serializer para métricas del dashboard
    """
    # Métricas de terceros
    total_terceros = serializers.IntegerField()
    pendientes_aprobacion = serializers.IntegerField()
    aprobados = serializers.IntegerField()
    rechazados = serializers.IntegerField()
    
    # Métricas de tiempo
    terceros_este_mes = serializers.IntegerField()
    terceros_mes_anterior = serializers.IntegerField()
    crecimiento_mensual = serializers.FloatField()
    
    # Métricas por tipo
    personas_naturales = serializers.IntegerField()
    personas_juridicas = serializers.IntegerField()
    
    # Métricas de actividad reciente
    actividad_reciente = serializers.ListField(child=serializers.DictField())
    
    # Métricas por usuario
    top_usuarios_creadores = serializers.ListField(child=serializers.DictField())


class DashboardMainSerializer(serializers.Serializer):
    """
    Serializer para vista principal del dashboard
    """
    bienvenida = serializers.CharField()
    resumen_actividad = serializers.DictField()
    accesos_rapidos = serializers.ListField(child=serializers.DictField())
    notificaciones = serializers.ListField(child=serializers.DictField())
