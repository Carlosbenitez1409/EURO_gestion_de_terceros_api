from rest_framework import serializers
from .models import TipoDocumento, DocumentoTercero, HistorialDocumento
from terceros.models import Tercero
import logging

logger = logging.getLogger(__name__)


class TipoDocumentoSerializer(serializers.ModelSerializer):
    """
    Serializer para tipos de documentos
    """
    class Meta:
        model = TipoDocumento
        fields = [
            'id', 'nombre', 'descripcion', 'es_obligatorio', 
            'activo', 'orden', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DocumentoTerceroListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listado de documentos
    """
    tipo_documento_nombre = serializers.CharField(source='tipo_documento.nombre', read_only=True)
    subido_por_nombre = serializers.CharField(source='subido_por.get_full_name', read_only=True)
    validado_por_nombre = serializers.CharField(source='validado_por.get_full_name', read_only=True)
    tamano_legible = serializers.CharField(read_only=True)
    extension_archivo = serializers.CharField(read_only=True)
    
    class Meta:
        model = DocumentoTercero
        fields = [
            'id', 'tipo_documento_nombre', 'nombre_original', 'tamano_legible',
            'extension_archivo', 'estado_validacion', 'fecha_subida', 'fecha_validacion',
            'subido_por_nombre', 'validado_por_nombre'
        ]


class DocumentoTerceroSerializer(serializers.ModelSerializer):
    """
    Serializer completo para documentos de terceros
    """
    tipo_documento_info = TipoDocumentoSerializer(source='tipo_documento', read_only=True)
    subido_por_info = serializers.SerializerMethodField()
    validado_por_info = serializers.SerializerMethodField()
    tamano_legible = serializers.CharField(read_only=True)
    extension_archivo = serializers.CharField(read_only=True)
    archivo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentoTercero
        fields = [
            'id', 'tercero', 'tipo_documento', 'tipo_documento_info',
            'archivo', 'archivo_url', 'nombre_original', 'tamano_archivo',
            'tamano_legible', 'extension_archivo', 'estado_validacion',
            'subido_por', 'subido_por_info', 'validado_por', 'validado_por_info',
            'fecha_subida', 'fecha_validacion', 'observaciones_validacion'
        ]
        read_only_fields = [
            'id', 'nombre_original', 'tamano_archivo', 'subido_por',
            'fecha_subida', 'tamano_legible', 'extension_archivo', 'archivo_url'
        ]
    
    def get_subido_por_info(self, obj):
        if obj.subido_por:
            return {
                'id': obj.subido_por.id,
                'username': obj.subido_por.username,
                'full_name': obj.subido_por.get_full_name(),
                'email': obj.subido_por.email
            }
        return None
    
    def get_validado_por_info(self, obj):
        if obj.validado_por:
            return {
                'id': obj.validado_por.id,
                'username': obj.validado_por.username,
                'full_name': obj.validado_por.get_full_name(),
                'email': obj.validado_por.email
            }
        return None
    
    def get_archivo_url(self, obj):
        if obj.archivo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.archivo.url)
        return None


class DocumentoTerceroUploadSerializer(serializers.ModelSerializer):
    """
    Serializer específico para subida de documentos
    """
    class Meta:
        model = DocumentoTercero
        fields = ['tercero', 'tipo_documento', 'archivo']
    
    def validate_archivo(self, value):
        """
        Validaciones específicas para archivos
        """
        # Validar tamaño máximo (10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"El archivo es demasiado grande. Máximo permitido: 10MB. "
                f"Tamaño actual: {value.size / (1024*1024):.1f}MB"
            )
        
        # Validar extensiones permitidas
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
        extension = value.name.split('.')[-1].lower()
        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                f"Extensión de archivo no permitida: .{extension}. "
                f"Extensiones permitidas: {', '.join(allowed_extensions)}"
            )
        
        return value
    
    def validate(self, attrs):
        """
        Validaciones a nivel de objeto
        """
        tercero = attrs.get('tercero')
        tipo_documento = attrs.get('tipo_documento')
        
        # Verificar que no exista ya un documento de este tipo para este tercero
        if DocumentoTercero.objects.filter(
            tercero=tercero, 
            tipo_documento=tipo_documento
        ).exists():
            raise serializers.ValidationError(
                f"Ya existe un documento de tipo '{tipo_documento.nombre}' "
                f"para este tercero. Elimine el anterior antes de subir uno nuevo."
            )
        
        return attrs
    
    def create(self, validated_data):
        """
        Crear documento con usuario automático si está autenticado
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['subido_por'] = request.user
        else:
            # Para registros públicos, necesitamos manejar esto diferente
            # Por ahora usaremos un usuario sistema o None
            validated_data['subido_por'] = None
        
        documento = super().create(validated_data)
        
        logger.info(
            f"Document uploaded: {documento.tipo_documento.nombre} "
            f"for tercero {documento.tercero.numero_documento}"
        )
        
        return documento


class HistorialDocumentoSerializer(serializers.ModelSerializer):
    """
    Serializer para historial de documentos
    """
    usuario_info = serializers.SerializerMethodField()
    
    class Meta:
        model = HistorialDocumento
        fields = [
            'id', 'estado_anterior', 'estado_nuevo', 'usuario',
            'usuario_info', 'comentarios', 'fecha_cambio'
        ]
        read_only_fields = ['id', 'fecha_cambio']
    
    def get_usuario_info(self, obj):
        return {
            'id': obj.usuario.id,
            'username': obj.usuario.username,
            'full_name': obj.usuario.get_full_name()
        }


class DocumentoValidacionSerializer(serializers.Serializer):
    """
    Serializer para validación de documentos
    """
    estado_validacion = serializers.ChoiceField(
        choices=DocumentoTercero.EstadoValidacion.choices
    )
    observaciones_validacion = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000
    )
    
    def validate(self, attrs):
        estado = attrs.get('estado_validacion')
        observaciones = attrs.get('observaciones_validacion', '')
        
        # Si rechaza o requiere ajustes, las observaciones son obligatorias
        if estado in ['rechazado', 'requiere_ajustes'] and not observaciones:
            raise serializers.ValidationError(
                "Las observaciones son obligatorias cuando se rechaza un documento "
                "o se requieren ajustes."
            )
        
        return attrs
