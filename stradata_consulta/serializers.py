from rest_framework import serializers
from .models import StrataDataDocumento


class StrataDataDocumentoSerializer(serializers.ModelSerializer):
    """
    Serializer para documentos de Stradata
    """
    nombre_archivo = serializers.ReadOnlyField()
    url_descarga = serializers.ReadOnlyField()
    subido_por_nombre = serializers.CharField(source='subido_por.get_full_name', read_only=True)
    
    class Meta:
        model = StrataDataDocumento
        fields = [
            'id',
            'uuid',
            'nombre',
            'tercero',
            'archivo',
            'tipo_consulta',
            'descripcion',
            'tamaño_archivo',
            'tipo_mime',
            'fecha_subida',
            'fecha_actualizacion',
            'subido_por',
            'subido_por_nombre',
            'nombre_archivo',
            'url_descarga',
            'activo'
        ]
        read_only_fields = ['id', 'uuid', 'nombre', 'tamaño_archivo', 'tipo_mime', 'fecha_subida', 'fecha_actualizacion', 'subido_por']


class StrataDataDocumentoUploadSerializer(serializers.ModelSerializer):
    """
    Serializer específico para subir documentos
    """
    class Meta:
        model = StrataDataDocumento
        fields = ['archivo', 'tipo_consulta', 'descripcion']
        
    def validate_archivo(self, value):
        """Validar que el archivo sea PDF"""
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Solo se permiten archivos PDF")
        
        # Validar tamaño (máximo 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("El archivo no puede ser mayor a 10MB")
            
        return value


# Alias para compatibilidad
StratadaDocumentoSerializer = StrataDataDocumentoSerializer
StratadaDocumentoUploadSerializer = StrataDataDocumentoUploadSerializer