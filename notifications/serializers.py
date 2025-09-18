from rest_framework import serializers
from .models import Notificacion, PreferenciasNotificacion
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificacionSerializer(serializers.ModelSerializer):
    """Serializer para notificaciones"""
    
    tiempo_transcurrido = serializers.ReadOnlyField()
    tercero_info = serializers.SerializerMethodField()
    usuario_relacionado_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Notificacion
        fields = [
            'id', 'titulo', 'mensaje', 'tipo', 'prioridad', 'leida',
            'fecha_creacion', 'fecha_leida', 'tiempo_transcurrido',
            'tercero_info', 'usuario_relacionado_info', 'datos_extra', 'url_accion'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'fecha_leida', 'tiempo_transcurrido']
    
    def get_tercero_info(self, obj):
        """Información básica del tercero relacionado"""
        if obj.tercero_relacionado:
            tercero = obj.tercero_relacionado
            return {
                'id': str(tercero.id),
                'numero_documento': tercero.numero_documento,
                'nombre_completo': (
                    f"{tercero.nombres} {tercero.apellidos}" 
                    if tercero.tipo_persona == 'natural' 
                    else tercero.razon_social
                ),
                'tipo_persona': tercero.tipo_persona,
                'estado_aprobacion': tercero.estado_aprobacion
            }
        return None
    
    def get_usuario_relacionado_info(self, obj):
        """Información del usuario que generó la notificación"""
        if obj.usuario_relacionado:
            usuario = obj.usuario_relacionado
            return {
                'id': str(usuario.id),
                'nombre_completo': usuario.get_full_name(),
                'email': usuario.email,
                'role': usuario.role
            }
        return None


class NotificacionCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear notificaciones"""
    
    class Meta:
        model = Notificacion
        fields = [
            'usuario', 'titulo', 'mensaje', 'tipo', 'prioridad',
            'tercero_relacionado', 'usuario_relacionado', 'datos_extra', 'url_accion'
        ]
    
    def validate(self, data):
        """Validaciones personalizadas"""
        # Verificar que el usuario tenga preferencias para este tipo de notificación
        usuario = data['usuario']
        tipo = data['tipo']
        
        try:
            preferencias = PreferenciasNotificacion.objects.get(usuario=usuario)
            if not preferencias.acepta_notificacion(tipo):
                raise serializers.ValidationError(
                    f"El usuario no acepta notificaciones de tipo '{tipo}'"
                )
        except PreferenciasNotificacion.DoesNotExist:
            # Si no tiene preferencias, crear las por defecto
            PreferenciasNotificacion.get_or_create_for_user(usuario)
        
        return data


class PreferenciasNotificacionSerializer(serializers.ModelSerializer):
    """Serializer para preferencias de notificación"""
    
    class Meta:
        model = PreferenciasNotificacion
        fields = [
            'tercero_asignado', 'tercero_aprobado', 'tercero_rechazado',
            'documento_subido', 'revision_requerida', 'estado_cambiado',
            'alerta_cumplimiento', 'sistema', 'recordatorio', 'usuario_creado',
            'rol_cambiado', 'notificaciones_email', 'notificaciones_push',
            'notificaciones_en_app', 'horario_inicio', 'horario_fin',
            'resumen_diario', 'resumen_semanal', 'fecha_actualizacion'
        ]
        read_only_fields = ['fecha_actualizacion']


class NotificacionResumenSerializer(serializers.Serializer):
    """Serializer para resumen de notificaciones"""
    
    total_notificaciones = serializers.IntegerField()
    no_leidas = serializers.IntegerField()
    por_tipo = serializers.DictField()
    por_prioridad = serializers.DictField()
    ultimas_5 = NotificacionSerializer(many=True)


class MarcarLeidaSerializer(serializers.Serializer):
    """Serializer para marcar notificaciones como leídas"""
    
    notificacion_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        help_text="Lista de IDs de notificaciones a marcar como leídas"
    )
    
    def validate_notificacion_ids(self, value):
        """Validar que las notificaciones existan y pertenezcan al usuario"""
        usuario = self.context['request'].user
        
        notificaciones = Notificacion.objects.filter(
            id__in=value,
            usuario=usuario
        )
        
        if len(notificaciones) != len(value):
            raise serializers.ValidationError(
                "Algunas notificaciones no existen o no pertenecen al usuario"
            )
        
        return value


class CrearNotificacionMasivaSerializer(serializers.Serializer):
    """Serializer para crear notificaciones masivas"""
    
    titulo = serializers.CharField(max_length=255)
    mensaje = serializers.CharField()
    tipo = serializers.ChoiceField(choices=Notificacion.TIPOS_NOTIFICACION)
    prioridad = serializers.ChoiceField(
        choices=Notificacion.NIVELES_PRIORIDAD,
        default='media'
    )
    roles_destino = serializers.MultipleChoiceField(
        choices=User.RoleChoices.choices,
        allow_empty=False,
        help_text="Roles de usuarios que recibirán la notificación"
    )
    usuarios_especificos = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="IDs específicos de usuarios (opcional)"
    )
    datos_extra = serializers.JSONField(required=False)
    url_accion = serializers.URLField(required=False)
    
    def validate(self, data):
        """Validar que se especifiquen roles o usuarios"""
        if not data.get('roles_destino') and not data.get('usuarios_especificos'):
            raise serializers.ValidationError(
                "Debe especificar al menos roles_destino o usuarios_especificos"
            )
        return data
    
    def create(self, validated_data):
        """Crear notificaciones masivas"""
        usuario_creador = self.context['request'].user
        
        # Obtener usuarios destino
        usuarios_destino = set()
        
        # Por roles
        if validated_data.get('roles_destino'):
            usuarios_por_rol = User.objects.filter(
                role__in=validated_data['roles_destino'],
                is_active=True
            )
            usuarios_destino.update(usuarios_por_rol)
        
        # Por usuarios específicos
        if validated_data.get('usuarios_especificos'):
            usuarios_especificos = User.objects.filter(
                id__in=validated_data['usuarios_especificos'],
                is_active=True
            )
            usuarios_destino.update(usuarios_especificos)
        
        # Crear notificaciones
        notificaciones_creadas = []
        for usuario in usuarios_destino:
            # Verificar preferencias del usuario
            preferencias, _ = PreferenciasNotificacion.get_or_create_for_user(usuario)
            
            if preferencias.acepta_notificacion(validated_data['tipo']):
                notificacion = Notificacion.crear_notificacion(
                    usuario=usuario,
                    titulo=validated_data['titulo'],
                    mensaje=validated_data['mensaje'],
                    tipo=validated_data['tipo'],
                    prioridad=validated_data['prioridad'],
                    usuario_relacionado=usuario_creador,
                    datos_extra=validated_data.get('datos_extra'),
                    url_accion=validated_data.get('url_accion')
                )
                notificaciones_creadas.append(notificacion)
        
        return {
            'notificaciones_creadas': len(notificaciones_creadas),
            'usuarios_notificados': len(usuarios_destino),
            'notificaciones': notificaciones_creadas
        }
