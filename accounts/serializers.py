from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User
import logging

logger = logging.getLogger(__name__)

class CustomTokenObtainPairSerializer(serializers.Serializer):
    """
    Serializer personalizado para JWT que maneja autenticación con username, password y role
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    role = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        role = attrs.get('role')
        
        logger.info(f"Attempting authentication for user: {username} with role: {role}")
        
        if not username or not password or not role:
            raise serializers.ValidationError(
                'Debe incluir "username", "password" y "role".'
            )
        
        user = authenticate(
            request=self.context.get('request'),
            username=username, 
            password=password
        )
        
        if not user:
            logger.error(f"Authentication failed for user: {username}")
            raise serializers.ValidationError(
                'Usuario o contraseña incorrectos.'
            )
        
        if not user.is_active:
            logger.error(f"User {username} is not active")
            raise serializers.ValidationError(
                'La cuenta de usuario está desactivada.'
            )
        
        # VERIFICAR QUE EL ROL COINCIDA
        if user.role != role:
            logger.error(f"Role mismatch for user {username}. Expected: {role}, Got: {user.role}")
            raise serializers.ValidationError(
                f'El rol especificado ({role}) no coincide con el usuario (tiene: {user.role}).'
            )
        
        logger.info(f"Authentication successful for user: {username}")
        
        # GENERAR TOKENS
        refresh = RefreshToken.for_user(user)
        
        # Agregar datos personalizados al token
        refresh['role'] = user.role
        refresh['username'] = user.username
        
        # Actualizar last_login
        from django.contrib.auth import login
        from django.utils import timezone
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'is_active': user.is_active,
            }
        }


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer para mostrar y actualizar usuarios
    """
    full_name = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    
    class Meta:
        model = User
        fields = [
            # Información básica
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'password', 'role',
            # Información de contacto
            'phone', 'direccion',
            # Información laboral
            'cargo', 'area', 'fecha_contratacion', 'estado_empleado',
            # Información de documento
            'tipo_documento', 'numero_documento',
            # Sistema
            'is_active', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        """Retornar nombre completo"""
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def update(self, instance, validated_data):
        """Actualizar usuario, manejando password por separado"""
        password = validated_data.pop('password', None)
        
        # Actualizar campos normales
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Si se proporciona nueva password, hashearla
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear usuarios nuevos con todos los campos del frontend
    """
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=['procesos', 'comercial', 'gestion_humana'])
    tipo_documento = serializers.ChoiceField(
        choices=['CC', 'CE', 'TI', 'PASAPORTE', 'NIT'],
        required=False,
        allow_blank=True
    )
    estado_empleado = serializers.ChoiceField(
        choices=['activo', 'inactivo', 'suspendido', 'vacaciones', 'licencia'],
        default='activo',
        required=False
    )
    
    class Meta:
        model = User
        fields = [
            # Información básica del usuario
            'id', 'username', 'email', 'first_name', 'last_name', 
            'password', 'password_confirm', 'role',
            # Información de contacto
            'phone', 'direccion',
            # Información de documento
            'tipo_documento', 'numero_documento',
            # Información laboral
            'cargo', 'area', 'fecha_contratacion', 'estado_empleado'
        ]
        read_only_fields = ['id']
    
    def validate_email(self, value):
        """Validar que el email sea único"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este email.")
        return value
    
    def validate_username(self, value):
        """Validar que el username sea único y cumpla con el formato"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este nombre de usuario.")
        
        # Validar formato del username (solo letras, dígitos y @/./+/-/_)
        import re
        if not re.match(r'^[a-zA-Z0-9@.+\-_]+$', value):
            raise serializers.ValidationError(
                "El nombre de usuario solo puede contener letras, dígitos y @/./+/-/_"
            )
        return value
    
    def validate_numero_documento(self, value):
        """Validar que el número de documento sea único si se proporciona"""
        if value and User.objects.filter(numero_documento=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este número de documento.")
        return value
    
    def validate(self, attrs):
        """Validaciones adicionales"""
        # Validar que las contraseñas coincidan
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        
        if password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': 'Las contraseñas no coinciden.'
            })
        
        # Validar que si se proporciona tipo_documento, también numero_documento
        tipo_documento = attrs.get('tipo_documento')
        numero_documento = attrs.get('numero_documento')
        
        if tipo_documento and not numero_documento:
            raise serializers.ValidationError({
                'numero_documento': 'Si especifica un tipo de documento, debe proporcionar el número.'
            })
        
        if numero_documento and not tipo_documento:
            raise serializers.ValidationError({
                'tipo_documento': 'Si especifica un número de documento, debe seleccionar el tipo.'
            })
        
        return attrs
    
    def create(self, validated_data):
        """Crear usuario removiendo password_confirm del data"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


# Nuevos serializers para gestión de usuarios por administradores
class UserManagementSerializer(serializers.ModelSerializer):
    """
    Serializer para mostrar información de usuarios en el panel de administración
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'role_display', 'is_active', 'is_staff', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'full_name', 'role_display']


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear nuevos usuarios (solo administradores)
    """
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'role',
            'password', 'password_confirm', 'is_active', 'is_staff'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Las contraseñas no coinciden.'
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar usuarios existentes
    """
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff'
        ]
    
    def validate_email(self, value):
        user = self.instance
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        return value