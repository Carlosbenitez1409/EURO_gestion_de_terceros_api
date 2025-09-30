# usuarios_consultas/serializers.py
"""
Serializers para el Sistema de Usuarios GH (Consultas de Personal)
Implementación según API_SPECIFICATION_USUARIOS_GH.md
"""

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Solicitud, Persona, HistorialCambio, EstadoSolicitud, TipoDocumento, Riesgo

User = get_user_model()


class UsuarioBasicoSerializer(serializers.ModelSerializer):
    """Serializer básico para información de usuario"""
    nombre_completo = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'nombre_completo']
        read_only_fields = ['id', 'username', 'first_name', 'last_name', 'email', 'nombre_completo']
    
    def get_nombre_completo(self, obj):
        return obj.get_full_name() or obj.username


class PersonaSerializer(serializers.ModelSerializer):
    """Serializer para Persona con validaciones"""
    
    # Definir explícitamente el campo riesgo para personalizar su validación
    riesgo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = Persona
        fields = [
            'id', 'orden', 'nombres_apellidos', 'tipo_documento', 
            'numero_documento', 'antecedentes', 'observaciones', 
            'riesgo', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'fecha_actualizacion']
    
    def validate_nombres_apellidos(self, value):
        """Validar nombres y apellidos"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("Los nombres y apellidos son obligatorios")
        
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Los nombres y apellidos deben tener al menos 3 caracteres")
        
        return value.strip().title()
    
    def validate_numero_documento(self, value):
        """Validar número de documento"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("El número de documento es obligatorio")
        
        # Remover espacios y caracteres especiales
        numero_limpio = ''.join(c for c in value if c.isalnum())
        
        if len(numero_limpio) < 6:
            raise serializers.ValidationError("El número de documento debe tener al menos 6 caracteres")
        
        return numero_limpio
    
    def validate_orden(self, value):
        """Validar que el orden esté en rango válido"""
        if value < 1 or value > 10:
            raise serializers.ValidationError("El orden debe estar entre 1 y 10")
        return value
    
    def validate_riesgo(self, value):
        """Normalizar valores de riesgo para aceptar minúsculas"""
        if not value or value.strip() == '':
            return None
            
        # Mapeo de valores en minúsculas a mayúsculas
        riesgo_map = {
            'alto': 'ALTO',
            'medio': 'MEDIO', 
            'bajo': 'BAJO',
            'sin_antecedentes': 'SIN_ANTECEDENTES'
        }
        
        # Convertir a minúsculas para comparar
        value_lower = value.strip().lower()
        
        # Si está en el mapeo de minúsculas, convertir a mayúsculas
        if value_lower in riesgo_map:
            return riesgo_map[value_lower]
        
        # Si ya viene en el formato correcto de mayúsculas, verificar que sea válido
        value_upper = value.strip().upper()
        if value_upper in ['ALTO', 'MEDIO', 'BAJO', 'SIN_ANTECEDENTES']:
            return value_upper
        
        # Si no es un valor reconocido, lanzar error
        raise serializers.ValidationError(f"'{value}' no es un valor válido. Use: alto, medio, bajo, sin_antecedentes")
    
    def validate(self, attrs):
        """Validaciones a nivel de objeto"""
        # Si estamos editando, verificar que no se duplique documento en la solicitud
        if self.instance and self.instance.solicitud:
            solicitud = self.instance.solicitud
            tipo_doc = attrs.get('tipo_documento', self.instance.tipo_documento)
            num_doc = attrs.get('numero_documento', self.instance.numero_documento)
            
            duplicados = Persona.objects.filter(
                solicitud=solicitud,
                tipo_documento=tipo_doc,
                numero_documento=num_doc
            ).exclude(id=self.instance.id)
            
            if duplicados.exists():
                raise serializers.ValidationError({
                    'numero_documento': f'Ya existe una persona con {tipo_doc} {num_doc} en esta solicitud'
                })
        
        return attrs
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar permisos de edición según el rol del usuario
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user_role = getattr(request.user, 'role', None)
            
            # Antecedentes: solo editables por Admin y Procesos
            if user_role not in ['administrador', 'procesos']:
                self.fields['antecedentes'].read_only = True
            
            # Riesgo: solo asignable por Admin y Procesos
            if user_role not in ['administrador', 'procesos']:
                self.fields['riesgo'].read_only = True
            
            # Observaciones: editables por GH, Admin y Procesos
            # (Por defecto es editable, no necesita restricción)
            
            # Datos básicos (nombres, documento): solo editables por GH durante creación
            # En edición, solo GH puede modificar datos básicos
            if self.instance and user_role not in ['gestion_humana']:
                self.fields['nombres_apellidos'].read_only = True
                self.fields['tipo_documento'].read_only = True
                self.fields['numero_documento'].read_only = True


class PersonaCreacionSerializer(PersonaSerializer):
    """Serializer específico para creación de personas (incluye solicitud)"""
    
    class Meta(PersonaSerializer.Meta):
        fields = PersonaSerializer.Meta.fields + ['solicitud']
    
    def validate(self, attrs):
        solicitud = attrs.get('solicitud')
        if not solicitud:
            raise serializers.ValidationError({'solicitud': 'La solicitud es obligatoria'})
        
        # Verificar que la solicitud esté en estado que permita agregar personas
        if solicitud.estado not in [EstadoSolicitud.CREADA, EstadoSolicitud.DEVUELTA_GH]:
            raise serializers.ValidationError({
                'solicitud': 'No se pueden agregar personas a una solicitud en este estado'
            })
        
        # Verificar límite de personas (máximo 10)
        personas_actuales = solicitud.personas.count()
        if personas_actuales >= 10:
            raise serializers.ValidationError({
                'solicitud': 'Una solicitud no puede tener más de 10 personas'
            })
        
        # Verificar duplicados de documento en la solicitud
        tipo_doc = attrs.get('tipo_documento')
        num_doc = attrs.get('numero_documento')
        
        if Persona.objects.filter(
            solicitud=solicitud,
            tipo_documento=tipo_doc,
            numero_documento=num_doc
        ).exists():
            raise serializers.ValidationError({
                'numero_documento': f'Ya existe una persona con {tipo_doc} {num_doc} en esta solicitud'
            })
        
        # Auto-asignar orden si no se proporciona
        if 'orden' not in attrs:
            ultimo_orden = solicitud.personas.aggregate(
                max_orden=serializers.models.Max('orden')
            )['max_orden'] or 0
            attrs['orden'] = ultimo_orden + 1
        
        return super().validate(attrs)


class HistorialCambioSerializer(serializers.ModelSerializer):
    """Serializer para historial de cambios"""
    usuario = UsuarioBasicoSerializer(read_only=True)
    estado_anterior_display = serializers.CharField(source='get_estado_anterior_display', read_only=True)
    estado_nuevo_display = serializers.CharField(source='get_estado_nuevo_display', read_only=True)
    
    class Meta:
        model = HistorialCambio
        fields = [
            'id', 'fecha_cambio', 'usuario', 'accion', 'descripcion',
            'estado_anterior', 'estado_anterior_display',
            'estado_nuevo', 'estado_nuevo_display'
        ]
        read_only_fields = fields  # Todos los campos son de solo lectura


class SolicitudListSerializer(serializers.ModelSerializer):
    """Serializer para lista de solicitudes (vista resumida)"""
    creada_por = UsuarioBasicoSerializer(read_only=True)
    asignada_a = UsuarioBasicoSerializer(read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    total_personas = serializers.ReadOnlyField()
    
    class Meta:
        model = Solicitud
        fields = [
            'id', 'estado', 'estado_display', 'creada_por', 'asignada_a',
            'fecha_creacion', 'fecha_ultima_actualizacion', 'total_personas'
        ]
        read_only_fields = fields


class SolicitudDetalleSerializer(serializers.ModelSerializer):
    """Serializer para detalle completo de solicitud"""
    creada_por = UsuarioBasicoSerializer(read_only=True)
    asignada_a = UsuarioBasicoSerializer(read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    personas = PersonaSerializer(many=True, read_only=True)
    historial_cambios = HistorialCambioSerializer(many=True, read_only=True)
    total_personas = serializers.ReadOnlyField()
    
    # Campos computados para permisos
    puede_editar = serializers.SerializerMethodField()
    puede_tomar_revision = serializers.SerializerMethodField()
    puede_cambiar_estado = serializers.SerializerMethodField()
    
    class Meta:
        model = Solicitud
        fields = [
            'id', 'estado', 'estado_display', 'creada_por', 'asignada_a',
            'fecha_creacion', 'fecha_ultima_actualizacion', 'observaciones_generales',
            'personas', 'historial_cambios', 'total_personas',
            'puede_editar', 'puede_tomar_revision', 'puede_cambiar_estado'
        ]
        read_only_fields = [
            'id', 'fecha_creacion', 'fecha_ultima_actualizacion', 'creada_por',
            'estado_display', 'personas', 'historial_cambios', 'total_personas',
            'puede_editar', 'puede_tomar_revision', 'puede_cambiar_estado'
        ]
    
    def get_puede_editar(self, obj):
        """Determina si el usuario actual puede editar la solicitud"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.puede_ser_editada_por(request.user)
    
    def get_puede_tomar_revision(self, obj):
        """Determina si el usuario actual puede tomar la solicitud para revisión"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.puede_tomar_revision(request.user)
    
    def get_puede_cambiar_estado(self, obj):
        """Determina si el usuario actual puede cambiar el estado"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        if not hasattr(user, 'role'):
            return False
        
        role = user.role
        estado = obj.estado
        
        # Lógica según matriz de permisos del documento
        if role == 'gestion_humana':
            return estado in [EstadoSolicitud.DEVUELTA_GH]
        elif role == 'administrador':
            return estado in [EstadoSolicitud.EN_REVISION_ADMINISTRADOR] and obj.asignada_a == user
        elif role == 'procesos':
            return estado in [EstadoSolicitud.EN_REVISION_PROCESOS] and obj.asignada_a == user
        
        return False


class SolicitudCreacionSerializer(serializers.ModelSerializer):
    """Serializer para creación de solicitudes"""
    personas = PersonaSerializer(many=True, write_only=True)
    
    class Meta:
        model = Solicitud
        fields = ['observaciones_generales', 'personas']
    
    def validate_personas(self, value):
        """Validar lista de personas"""
        if not value:
            raise serializers.ValidationError("Debe incluir al menos una persona")
        
        if len(value) > 10:
            raise serializers.ValidationError("Una solicitud no puede tener más de 10 personas")
        
        # Validar documentos únicos
        documentos = set()
        ordenes = set()
        
        for i, persona_data in enumerate(value):
            # Validar orden único
            orden = persona_data.get('orden', i + 1)
            if orden in ordenes:
                raise serializers.ValidationError(f"El orden {orden} está duplicado")
            ordenes.add(orden)
            
            # Validar documento único
            tipo_doc = persona_data.get('tipo_documento')
            num_doc = persona_data.get('numero_documento')
            doc_key = (tipo_doc, num_doc)
            
            if doc_key in documentos:
                raise serializers.ValidationError(
                    f"El documento {tipo_doc} {num_doc} está duplicado"
                )
            documentos.add(doc_key)
        
        return value
    
    def create(self, validated_data):
        """Crear solicitud con personas"""
        personas_data = validated_data.pop('personas')
        
        # Crear solicitud
        solicitud = Solicitud.objects.create(
            creada_por=self.context['request'].user,
            **validated_data
        )
        
        # Crear personas
        for persona_data in personas_data:
            Persona.objects.create(
                solicitud=solicitud,
                **persona_data
            )
        
        return solicitud


class SolicitudEdicionSerializer(serializers.ModelSerializer):
    """Serializer para edición de solicitudes"""
    
    class Meta:
        model = Solicitud
        fields = ['observaciones_generales']
    
    def validate(self, attrs):
        """Validar que la solicitud pueda ser editada"""
        if not self.instance.puede_ser_editada_por(self.context['request'].user):
            raise serializers.ValidationError("No tiene permisos para editar esta solicitud")
        return attrs


class CambioEstadoSerializer(serializers.Serializer):
    """Serializer para cambios de estado con comentarios"""
    nuevo_estado = serializers.ChoiceField(choices=EstadoSolicitud.choices)
    comentario = serializers.CharField(
        required=False, 
        allow_blank=True,
        max_length=1000,
        help_text="Comentario opcional sobre el cambio de estado"
    )
    asignar_a = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        help_text="Usuario al que asignar la solicitud (opcional)"
    )
    
    def validate(self, attrs):
        """Validar transición de estado"""
        solicitud = self.context['solicitud']
        usuario = self.context['request'].user
        nuevo_estado = attrs['nuevo_estado']
        estado_actual = solicitud.estado
        
        # Matriz de transiciones válidas según especificación
        transiciones_validas = {
            EstadoSolicitud.CREADA: [EstadoSolicitud.ASIGNADA_ADMINISTRADOR],
            EstadoSolicitud.ASIGNADA_ADMINISTRADOR: [EstadoSolicitud.EN_REVISION_ADMINISTRADOR],
            EstadoSolicitud.EN_REVISION_ADMINISTRADOR: [
                EstadoSolicitud.DEVUELTA_GH, 
                EstadoSolicitud.ASIGNADA_PROCESOS,
                EstadoSolicitud.FINALIZADA
            ],
            EstadoSolicitud.DEVUELTA_GH: [EstadoSolicitud.ASIGNADA_ADMINISTRADOR],
            EstadoSolicitud.ASIGNADA_PROCESOS: [EstadoSolicitud.EN_REVISION_PROCESOS],
            EstadoSolicitud.EN_REVISION_PROCESOS: [
                EstadoSolicitud.DEVUELTA_GH,
                EstadoSolicitud.FINALIZADA
            ],
            EstadoSolicitud.FINALIZADA: []  # Estado final
        }
        
        if nuevo_estado not in transiciones_validas.get(estado_actual, []):
            raise serializers.ValidationError({
                'nuevo_estado': f'No se puede cambiar de {estado_actual} a {nuevo_estado}'
            })
        
        # Validar permisos según rol
        if not hasattr(usuario, 'role'):
            raise serializers.ValidationError("Usuario sin rol asignado")
        
        role = usuario.role
        
        # Validaciones específicas por rol
        if role == 'gestion_humana':
            if estado_actual != EstadoSolicitud.DEVUELTA_GH:
                raise serializers.ValidationError("GH solo puede cambiar estado desde DEVUELTA_GH")
        
        elif role == 'administrador':
            if estado_actual in [EstadoSolicitud.ASIGNADA_ADMINISTRADOR]:
                # Admin puede tomar solicitud
                if nuevo_estado != EstadoSolicitud.EN_REVISION_ADMINISTRADOR:
                    raise serializers.ValidationError("Admin debe pasar a EN_REVISION_ADMINISTRADOR")
            elif estado_actual == EstadoSolicitud.EN_REVISION_ADMINISTRADOR:
                # Admin asignado puede cambiar estado
                if solicitud.asignada_a != usuario:
                    raise serializers.ValidationError("Solo el admin asignado puede cambiar el estado")
        
        elif role == 'procesos':
            if estado_actual == EstadoSolicitud.ASIGNADA_PROCESOS:
                # Procesos puede tomar solicitud
                if nuevo_estado != EstadoSolicitud.EN_REVISION_PROCESOS:
                    raise serializers.ValidationError("Procesos debe pasar a EN_REVISION_PROCESOS")
            elif estado_actual == EstadoSolicitud.EN_REVISION_PROCESOS:
                # Procesos asignado puede cambiar estado
                if solicitud.asignada_a != usuario:
                    raise serializers.ValidationError("Solo el usuario de procesos asignado puede cambiar el estado")
        
        return attrs


class EstadisticasSerializer(serializers.Serializer):
    """Serializer para estadísticas del dashboard"""
    total_solicitudes = serializers.IntegerField()
    solicitudes_por_estado = serializers.DictField()
    solicitudes_asignadas_a_mi = serializers.IntegerField()
    solicitudes_creadas_por_mi = serializers.IntegerField()
    promedio_tiempo_procesamiento = serializers.FloatField()