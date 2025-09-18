from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Usuario personalizado para el sistema EURO de Gestión de Terceros
    """
    class RoleChoices(models.TextChoices):
        PROCESOS = 'procesos', _('Procesos')
        COMERCIAL = 'comercial', _('Comercial') 
        GESTION_HUMANA = 'gestion_humana', _('Gestión Humana')
        OFICIAL_CUMPLIMIENTO = 'oficial_cumplimiento', _('Oficial de Cumplimiento')
        ADMINISTRADOR = 'administrador', _('Administrador')
    
    cargo = models.CharField(max_length=100, blank=True, null=True)

    class DocumentTypeChoices(models.TextChoices):
        CC = 'CC', _('Cédula de Ciudadanía')
        CE = 'CE', _('Cédula de Extranjería')
        TI = 'TI', _('Tarjeta de Identidad')
        PASAPORTE = 'PASAPORTE', _('Pasaporte')
        NIT = 'NIT', _('NIT')
    
    class EstadoEmpleadoChoices(models.TextChoices):
        ACTIVO = 'activo', _('Activo - Empleado habilitado')
        INACTIVO = 'inactivo', _('Inactivo - Empleado inhabilitado')
        SUSPENDIDO = 'suspendido', _('Suspendido - Empleado temporalmente inhabilitado')
        VACACIONES = 'vacaciones', _('En Vacaciones')
        LICENCIA = 'licencia', _('En Licencia')
    
    # Campos básicos del usuario
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.PROCESOS,
        verbose_name=_('Rol')
    )
    
    email = models.EmailField(
        unique=True,
        verbose_name=_('Correo electrónico')
    )
    
    first_name = models.CharField(
        max_length=150,
        verbose_name=_('Nombres')
    )
    
    last_name = models.CharField(
        max_length=150,
        verbose_name=_('Apellidos')
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('Teléfono')
    )
    
    # Campos adicionales para empleados
    cargo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Cargo'),
        help_text=_('Ej: Analista, Coordinador')
    )
    
    area = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Área'),
        help_text=_('Ej: Recursos Humanos, Contabilidad')
    )
    
    fecha_contratacion = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Fecha de Contratación')
    )
    
    tipo_documento = models.CharField(
        max_length=20,
        choices=DocumentTypeChoices.choices,
        blank=True,
        null=True,
        verbose_name=_('Tipo de Documento')
    )
    
    numero_documento = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('Número de Documento'),
        help_text=_('Número de identificación')
    )
    
    direccion = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Dirección'),
        help_text=_('Dirección completa')
    )
    
    # Estado del empleado
    estado_empleado = models.CharField(
        max_length=20,
        choices=EstadoEmpleadoChoices.choices,
        default=EstadoEmpleadoChoices.ACTIVO,
        verbose_name=_('Estado del Empleado')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Activo')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Fecha de actualización')
    )
    
    # Usar email como campo de identificación principal
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name', 'role']
    
    class Meta:
        verbose_name = _('Usuario')
        verbose_name_plural = _('Usuarios')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_role_display_name(self):
        """Retorna el nombre del rol en español"""
        return self.get_role_display()  # type: ignore
    
    @property
    def can_approve_terceros(self):
        """Determina si el usuario puede aprobar terceros"""
        return self.role in [self.RoleChoices.PROCESOS, self.RoleChoices.GESTION_HUMANA]
    
    @property
    def can_create_terceros(self):
        """Determina si el usuario puede crear terceros"""
        return self.role == self.RoleChoices.COMERCIAL
    
    @property
    def can_view_dashboard(self):
        """Determina si el usuario puede ver el dashboard"""
        return True  # Todos los roles pueden ver el dashboard
