# models.py en 'terceros'
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import uuid
import os

User = get_user_model()  # Usamos el modelo de usuario personalizado

def asignar_procesos_automaticamente():
    """
    Asigna un usuario de procesos de forma equitativa basado en la carga actual
    """
    from django.db.models import Count
    
    # Obtener todos los usuarios con rol procesos que estén activos
    usuarios_procesos = User.objects.filter(
        role='procesos',
        is_active=True
    ).annotate(
        num_terceros_asignados=Count('terceros_asignados_procesos')
    ).order_by('num_terceros_asignados')
    
    if not usuarios_procesos.exists():
        # Si no hay usuarios de procesos, retornar None
        return None
    
    # Retornar el usuario de procesos con menos terceros asignados
    return usuarios_procesos.first()

# Primero definimos la función de carga
def upload_documento_tercero(instance, filename):
    """
    Guarda el archivo en: documentos/terceros/<numero_documento>/<tipo_documento>/<archivo>
    Estructura: documentos/terceros/1015069071/RUT/rut.pdf
    """
    # Obtener la extensión del archivo
    ext = filename.split('.')[-1].lower()
    
    # Obtener el número de documento del tercero
    numero_doc = getattr(instance.tercero, 'numero_documento', 'pendiente')
    
    # Mapear tipos de documento a nombres de carpetas amigables
    tipo_doc_carpetas = {
        'documento_identidad': 'Documento de Identidad',
        'rut': 'RUT',
        'certificacion_comercial': 'Certificación Comercial',
        'certificacion_bancaria': 'Certificación Bancaria',
        'documento_identidad_representante': 'Documento Representante Legal',
        'certificado_existencia_representacion': 'Certificado de Existencia',
        'composicion_accionaria_certificada': 'Composición Accionaria',
        'estados_financieros_comparativos': 'Estados Financieros',
        'declaracion_renta': 'Declaración de Renta',
        'certificacion_comercial_1': 'Certificación Comercial 1',
        'certificacion_comercial_2': 'Certificación Comercial 2',
        'cedula': 'Cédula',
        'certificado': 'Certificado',
        'otros': 'Otros'
    }
    
    # Obtener el nombre de la carpeta para el tipo de documento
    carpeta_tipo = tipo_doc_carpetas.get(instance.tipo_documento, 'Otros')
    
    # Crear nombre único para el archivo manteniendo la extensión original
    nombre_base = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Truncar nombre base si es muy largo para evitar errores de almacenamiento
    if len(nombre_base) > 30:  # Más restrictivo
        nombre_base = nombre_base[:30]
    
    # Limpiar caracteres especiales del nombre
    import re
    nombre_base = re.sub(r'[^\w\s-]', '', nombre_base)
    nombre_base = re.sub(r'\s+', '_', nombre_base.strip())
    
    # Generar nombre corto con UUID
    nombre_archivo = f"{nombre_base}_{uuid.uuid4().hex[:8]}.{ext}"
    
    return f"documentos/terceros/{numero_doc}/{carpeta_tipo}/{nombre_archivo}"


def upload_documento_debida_diligencia(instance, filename):
    """
    Guarda los documentos de Debida Diligencia en una carpeta separada:
    debida_diligencia/<numero_documento>/<categoria>/<archivo>
    Estructura: debida_diligencia/1015069071/Formularios_DD/formulario_dd_abc123.pdf
    """
    # Obtener la extensión del archivo
    ext = filename.split('.')[-1].lower()
    
    # Obtener el número de documento del tercero
    numero_doc = getattr(instance.tercero, 'numero_documento', 'pendiente')
    
    # Mapear tipos de DD a carpetas organizadas por categoría
    categorias_dd = {
        # Formularios de Debida Diligencia
        'debida_diligencia_formulario': 'Formularios_DD',
        'debida_diligencia_verificacion': 'Formularios_DD',
        'debida_diligencia_bienes': 'Formularios_DD',
        'debida_diligencia_vinculacion': 'Formularios_DD',
        
        # Perfil de Riesgo
        'perfil_riesgo_matriz': 'Perfil_Riesgo',
        'perfil_riesgo_evaluacion': 'Perfil_Riesgo',
        'perfil_riesgo_actualizacion': 'Perfil_Riesgo',
        'perfil_riesgo_calificacion': 'Perfil_Riesgo',
        
        # Documentos de Soporte
        'soporte_referencias': 'Documentos_Soporte',
        'soporte_financieros': 'Documentos_Soporte',
        'soporte_certificaciones': 'Documentos_Soporte',
        'soporte_licencias': 'Documentos_Soporte',
        
        # Evaluación de Riesgo
        'evaluacion_informe': 'Evaluacion_Riesgo',
        'evaluacion_recomendaciones': 'Evaluacion_Riesgo',
        'evaluacion_mitigacion': 'Evaluacion_Riesgo',
        
        # Seguimiento y Monitoreo
        'seguimiento_revision': 'Seguimiento',
        'seguimiento_actualizacion': 'Seguimiento',
        'seguimiento_monitoreo': 'Seguimiento',
        
        # Otros
        'debida_diligencia_otro': 'Otros_DD'
    }
    
    # Obtener la categoría para el tipo de documento
    categoria = categorias_dd.get(instance.tipo_documento, 'Otros_DD')
    
    # Crear nombre único para el archivo manteniendo la extensión original
    nombre_base = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Truncar nombre base si es muy largo
    if len(nombre_base) > 30:
        nombre_base = nombre_base[:30]
    
    # Limpiar caracteres especiales del nombre
    import re
    nombre_base = re.sub(r'[^\w\s-]', '', nombre_base)
    nombre_base = re.sub(r'\s+', '_', nombre_base.strip())
    
    # Generar nombre con prefijo DD y UUID corto
    nombre_archivo = f"dd_{nombre_base}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Devolver la ruta completa del archivo
    return f"debida_diligencia/{numero_doc}/{categoria}/{nombre_archivo}"
    
def get_upload_path(instance, filename):
    """
    Función dinámica que decide qué función de upload usar según el tipo de documento
    """
    # Lista de tipos de documentos de Debida Diligencia
    tipos_dd = [
        'debida_diligencia_formulario', 'debida_diligencia_verificacion',
        'debida_diligencia_bienes', 'debida_diligencia_vinculacion',
        'perfil_riesgo_matriz', 'perfil_riesgo_evaluacion',
        'perfil_riesgo_actualizacion', 'perfil_riesgo_calificacion',
        'soporte_referencias', 'soporte_financieros', 'soporte_certificaciones',
        'soporte_licencias', 'evaluacion_informe', 'evaluacion_recomendaciones',
        'evaluacion_mitigacion', 'seguimiento_revision', 'seguimiento_actualizacion',
        'seguimiento_monitoreo', 'debida_diligencia_otro'
    ]
    
    # Si es un documento de Debida Diligencia, usar carpeta separada
    if instance.tipo_documento in tipos_dd:
        return upload_documento_debida_diligencia(instance, filename)
    else:
        # Para documentos normales del tercero
        return upload_documento_tercero(instance, filename)

class TipoDocumento(models.Model):
    """
    Catálogo de tipos de documentos requeridos
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Nombre del Documento')
    )
    
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Descripción')
    )
    
    es_obligatorio = models.BooleanField(
        default=True,
        verbose_name=_('Es Obligatorio')
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name=_('Activo')
    )
    
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Orden de presentación')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Fecha de creación')
    )
    
    class Meta:
        verbose_name = _('Tipo de Documento')
        verbose_name_plural = _('Tipos de Documentos')
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return self.nombre

class HistorialTercero(models.Model):
    """
    Modelo para registrar el historial de cambios de estado y asignaciones de terceros
    Proporciona trazabilidad completa y auditoría
    """
    
    class TipoAccion(models.TextChoices):
        CREACION = 'creacion', 'Creación'
        CAMBIO_ESTADO = 'cambio_estado', 'Cambio de Estado'
        ASIGNACION_COMERCIAL = 'asignacion_comercial', 'Asignación a Comercial'
        ASIGNACION_PROCESOS = 'asignacion_procesos', 'Asignación a Procesos'
        ASIGNACION_CUMPLIMIENTO = 'asignacion_cumplimiento', 'Asignación a Cumplimiento'
        ASIGNACION_ADMINISTRADOR = 'asignacion_administrador', 'Asignación a Administrador'
        APROBACION = 'aprobacion', 'Aprobación'
        RECHAZO = 'rechazo', 'Rechazo'
        REASIGNACION = 'reasignacion', 'Reasignación'
        OBSERVACION = 'observacion', 'Agregó Observación'
        RESET = 'reset', 'Reset por Administrador'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tercero = models.ForeignKey(
        'Tercero',  # Referencia forward porque Tercero se define después
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Tercero'
    )
    
    # Información de la acción
    accion = models.CharField(
        max_length=25,
        choices=TipoAccion.choices,
        verbose_name='Tipo de Acción'
    )
    
    # Estados (antes y después)
    estado_anterior = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        verbose_name='Estado Anterior'
    )
    
    estado_nuevo = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        verbose_name='Estado Nuevo'
    )
    
    # Usuario que realizó la acción
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_acciones',
        verbose_name='Usuario'
    )
    
    # Información de asignación
    usuario_asignado_anterior = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_asignaciones_anterior',
        verbose_name='Usuario Asignado Anterior'
    )
    
    usuario_asignado_nuevo = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_asignaciones_nuevo',
        verbose_name='Usuario Asignado Nuevo'
    )
    
    # Departamento/Rol involucrado
    departamento = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Departamento',
        help_text='comercial, procesos, cumplimiento, administrador'
    )
    
    # Observaciones y notas
    observaciones = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones',
        help_text='Comentarios o notas sobre la acción realizada'
    )
    
    # Metadatos adicionales (JSON para flexibilidad)
    metadatos = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadatos Adicionales',
        help_text='Información adicional sobre la acción en formato JSON'
    )
    
    # Información temporal
    fecha_accion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Acción'
    )
    
    # Información de la sesión/contexto
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name='User Agent'
    )
    
    class Meta:
        verbose_name = 'Historial de Tercero'
        verbose_name_plural = 'Historiales de Terceros'
        ordering = ['-fecha_accion']
        indexes = [
            models.Index(fields=['tercero', '-fecha_accion']),
            models.Index(fields=['usuario', '-fecha_accion']),
            models.Index(fields=['accion', '-fecha_accion']),
            models.Index(fields=['estado_nuevo', '-fecha_accion']),
        ]
    
    def __str__(self):
        return f"{self.tercero.numero_documento} - {self.get_accion_display()} - {self.fecha_accion.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def descripcion_completa(self):
        """Genera una descripción legible de la acción"""
        descripcion = f"{self.usuario.get_full_name() if self.usuario else 'Sistema'} "
        
        if self.accion == self.TipoAccion.CAMBIO_ESTADO:
            descripcion += f"cambió el estado de '{self.estado_anterior}' a '{self.estado_nuevo}'"
        elif self.accion == self.TipoAccion.ASIGNACION_COMERCIAL:
            if self.usuario_asignado_nuevo:
                descripcion += f"asignó a {self.usuario_asignado_nuevo.get_full_name()} (Comercial)"
            else:
                descripcion += "desasignó el comercial"
        elif self.accion == self.TipoAccion.ASIGNACION_PROCESOS:
            if self.usuario_asignado_nuevo:
                descripcion += f"asignó a {self.usuario_asignado_nuevo.get_full_name()} (Procesos)"
            else:
                descripcion += "desasignó de procesos"
        elif self.accion == self.TipoAccion.ASIGNACION_CUMPLIMIENTO:
            if self.usuario_asignado_nuevo:
                descripcion += f"asignó a {self.usuario_asignado_nuevo.get_full_name()} (Cumplimiento)"
            else:
                descripcion += "desasignó de cumplimiento"
        else:
            descripcion += self.get_accion_display().lower()
            
        if self.observaciones:
            descripcion += f" - Observaciones: {self.observaciones[:100]}{'...' if len(self.observaciones) > 100 else ''}"
            
        return descripcion

class Tercero(models.Model):
    """
    Modelo principal para la gestión de terceros
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class TipoDocumento(models.TextChoices):
        CEDULA = 'CC', 'Cédula de Ciudadanía'
        CEDULA_EXTRANJERIA = 'CE', 'Cédula de Extranjería'
        PASAPORTE = 'PA', 'Pasaporte'
        NIT = 'NIT', 'NIT'
        OTRO = 'OTRO', 'Otro/Exterior'
    
    class TipoPersona(models.TextChoices):
        NATURAL = 'natural', 'Persona Natural'
        JURIDICA = 'juridica', 'Persona Jurídica'
        PUBLICA = 'publica', 'Entidad Pública'
    
    class EstadoAprobacion(models.TextChoices):
        # Estados principales según flujo de negocio definido
        PENDIENTE = 'pendiente', 'Pendiente'
        EN_ESPERA_CORRECCION = 'en_espera_correccion', 'En espera (corrección)'
        EN_CURSO_COMERCIAL = 'en_curso_comercial', 'En curso (Comercial)'
        EN_CURSO_ADMINISTRADOR = 'en_curso_administrador', 'En curso (Administrador)'
        EN_CURSO_PROCESOS = 'en_curso_procesos', 'En curso (Procesos)'
        EN_CURSO_CUMPLIMIENTO = 'en_curso_cumplimiento', 'En curso (Cumplimiento)'
        ASIGNADA_ADMINISTRADOR = 'asignada_administrador', 'Asignada a Administrador'
        ASIGNADA_PROCESOS = 'asignada_procesos', 'Asignada a Procesos'
        ASIGNADA_OFICIAL_CUMPLIMIENTO = 'asignada_oficial_cumplimiento', 'Asignada a Oficial de Cumplimiento'
        DEVUELTO_COMERCIAL = 'devuelto_comercial', 'Devuelto a Comercial'
        APROBADO = 'aprobado', 'Aprobado'
        RECHAZADO = 'rechazado', 'Rechazado'
        FINALIZADO = 'finalizado', 'Finalizado'
    
    # Campos básicos
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tipo_documento = models.CharField(
        max_length=5,
        choices=TipoDocumento.choices,
        verbose_name='Tipo de Documento'
    )
    
    numero_documento = models.CharField(
        max_length=20,
        unique=True,
        validators=[RegexValidator(regex=r'^[0-9A-Za-z\-]+$', message='El número de documento solo puede contener números, letras y guiones.')],
        verbose_name='Número de Documento'
    )
    
    digito_verificacion = models.CharField(
        max_length=1,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^[0-9]$', message='El dígito de verificación debe ser un número.')],
        verbose_name='Dígito de Verificación',
        help_text='Obligatorio para NIT y RUT'
    )
    
    tipo_persona = models.CharField(
        max_length=10,
        choices=TipoPersona.choices,
        verbose_name='Tipo de Persona'
    )
    
    # Información personal/empresarial
    nombres = models.CharField(
        max_length=150,
        verbose_name='Nombres',
        help_text='Para personas naturales: nombres completos. Para jurídicas: razón social'
    )
    
    apellidos = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='Apellidos',
        help_text='Solo para personas naturales'
    )
    
    razon_social = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Razón Social',
        help_text='Solo para personas jurídicas'
    )
    
    # Nuevos campos para identificación
    fecha_nacimiento = models.DateField(null=True, blank=True)  # Para persona natural
    fecha_creacion = models.DateField(null=True, blank=True)    # Para persona jurídica
    actividad_economica_principal = models.CharField(max_length=300, blank=True)
    codigo_ciiu = models.CharField(max_length=4, blank=True)
    
    # Información de contacto expandida
    direccion = models.TextField(blank=True)
    pais = models.CharField(max_length=100, default='Colombia')
    departamento = models.CharField(max_length=100, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, null=True, verbose_name='Correo Electrónico')
    
    # Campos de contacto separados (nuevos)
    nombre_persona_contacto = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name='Nombre Persona de Contacto',
        help_text='Nombre completo de la persona de contacto principal'
    )
    cargo_persona_contacto = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name='Cargo Persona de Contacto',
        help_text='Cargo o posición de la persona de contacto en la empresa'
    )
    
    # Campos para activos virtuales (nuevos)
    manejo_activos_virtuales = models.BooleanField(
        default=False, 
        verbose_name='Maneja Activos Virtuales',
        help_text='Indica si realiza transacciones con criptomonedas, NFT u otros activos virtuales'
    )
    detalle_activos_virtuales = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Detalle de Activos Virtuales',
        help_text='Especifique los tipos de activos virtuales que maneja (Bitcoin, Ethereum, NFT, etc.)'
    )
    
    # Calidad tributaria
    responsable_iva = models.BooleanField(default=False)
    correo_facturacion_electronica = models.EmailField(
        verbose_name='Correo para Facturación Electrónica',
        help_text='Obligatorio para todos los terceros',
        default='facturacion@empresa.com'  # Placeholder genérico
    )
    gran_contribuyente = models.BooleanField(default=False)
    numero_resolucion_gc = models.CharField(max_length=100, blank=True)
    fecha_resolucion_gc = models.DateField(null=True, blank=True)
    auto_retenedor = models.BooleanField(default=False)
    numero_resolucion_autorretenedor = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name='Número Resolución Autorretenedor'
    )
    fecha_resolucion_autorretenedor = models.DateField(
        null=True, 
        blank=True,
        verbose_name='Fecha Resolución Autorretenedor'
    )
    exento_impuesto_renta = models.BooleanField(default=False)
    condiciones_exencion = models.TextField(blank=True, null=True)
    exento_renta = models.BooleanField(
        default=False,
        verbose_name='Exento de Renta'
    )
    condiciones_exento_renta = models.TextField(
        blank=True,
        verbose_name='Condiciones de Exención de Renta'
    )
    
    # Operaciones y observaciones
    tipo_formulario = models.CharField(
        max_length=20, 
        choices=[('vinculacion', 'Vinculación'), ('actualizacion', 'Actualización')],
        default='vinculacion',
        verbose_name='Tipo de Formulario'
    )
    
    # === INFORMACIÓN FINANCIERA (desde PROMPT) ===
    ingreso_mensual = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Ingresos Mensuales'
    )
    costos_gastos_mensuales = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Costos y Gastos Mensuales'
    )
    otros_ingresos = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Otros Ingresos'
    )
    total_ingresos = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Total Ingresos'
    )
    activos = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Activos'
    )
    pasivos = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Pasivos'
    )
    patrimonio = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name='Patrimonio'
    )
    detalle_otros_ingresos = models.TextField(
        blank=True,
        verbose_name='Detalle de Otros Ingresos'
    )
    
    operaciones_moneda_extranjera = models.BooleanField(default=False)
    tipos_operaciones_extranjera = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Tipos de Operaciones en Moneda Extranjera',
        help_text='Array de: exportacion, importacion, etc.'
    )
    detalle_operaciones_extranjera = models.TextField(
        default="No, solo operaciones en pesos colombianos",
        blank=True
    )
    
    # === DECLARACIONES SARLAFT/PEP (desde PROMPT) ===
    persona_expuesta_politica = models.BooleanField(
        default=False,
        verbose_name='Persona Expuesta Políticamente (PEP)'
    )
    origen_fondos = models.TextField(
        verbose_name='Origen de los Fondos',
        help_text='Descripción del origen de los recursos',
        default='Actividad económica principal'
    )
    tipos_recursos = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Tipos de Recursos',
        help_text='Array de: efectivo, transferencia, etc. Máximo 2 tipos'
    )
    manejo_alto_efectivo = models.BooleanField(
        default=False,
        verbose_name='Manejo de Alto Volumen de Efectivo'
    )
    autorizacion_tratamiento_datos = models.BooleanField(
        default=False,
        verbose_name='Autorización Tratamiento de Datos Personales',
        help_text='Obligatorio para procesar la información'
    )
    
    observaciones_adicionales = models.TextField(blank=True, null=True)
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones',
        help_text='Observaciones del proceso de aprobación'
    )
    
    # === CAMPOS DEL FORMULARIO FRONTEND (camelCase) ===
    # Campos tributarios que envía el frontend
    responsableIVA = models.BooleanField(null=True, blank=True, verbose_name='Responsable IVA (Frontend)')
    correoFacturacion = models.EmailField(max_length=255, blank=True, verbose_name='Correo Facturación (Frontend)')
    granContribuyente = models.BooleanField(null=True, blank=True, verbose_name='Gran Contribuyente (Frontend)')
    numeroResolucionGC = models.CharField(max_length=100, blank=True, verbose_name='Número Resolución GC (Frontend)')
    fechaResolucionGC = models.DateField(null=True, blank=True, verbose_name='Fecha Resolución GC (Frontend)')
    numeroResolucionAutorretenedor = models.CharField(max_length=100, blank=True, verbose_name='Número Resolución Autorretenedor (Frontend)')
    fechaResolucionAutorretenedor = models.DateField(null=True, blank=True, verbose_name='Fecha Resolución Autorretenedor (Frontend)')
    exentoRenta = models.BooleanField(null=True, blank=True, verbose_name='Exento Renta (Frontend)')
    condicionesExentoRenta = models.TextField(blank=True, verbose_name='Condiciones Exento Renta (Frontend)')
    
    # Campos financieros que envía el frontend
    ingresoMensual = models.CharField(max_length=50, blank=True, verbose_name='Ingreso Mensual (Frontend)')
    costosGastos = models.CharField(max_length=50, blank=True, verbose_name='Costos y Gastos (Frontend)')
    otrosIngresos = models.CharField(max_length=50, blank=True, verbose_name='Otros Ingresos (Frontend)')
    totalIngresos = models.CharField(max_length=50, blank=True, verbose_name='Total Ingresos (Frontend)')
    detalleOtrosIngresos = models.TextField(blank=True, verbose_name='Detalle Otros Ingresos (Frontend)')
    
    # Campos comerciales que envía el frontend
    operacionesMonedaExtranjera = models.BooleanField(null=True, blank=True, verbose_name='Operaciones Moneda Extranjera (Frontend)')
    tiposOperacionesMonedaExtranjera = models.JSONField(default=list, blank=True, verbose_name='Tipos Operaciones Moneda Extranjera (Frontend)')
    manejoAltoEfectivo = models.BooleanField(null=True, blank=True, verbose_name='Manejo Alto Efectivo (Frontend)')
    autorizacionTratamientoDatos = models.BooleanField(null=True, blank=True, verbose_name='Autorización Tratamiento Datos (Frontend)')
    
    # Campos SARLAFT/PEP que envía el frontend
    personaExpuestaPolitica = models.BooleanField(null=True, blank=True, verbose_name='Persona Expuesta Política (Frontend)')
    detallesPEP = models.TextField(blank=True, verbose_name='Detalles PEP (Frontend)', help_text='Detalles si es persona expuesta políticamente')
    origenFondos = models.TextField(blank=True, verbose_name='Origen Fondos (Frontend)')
    fuentesFondos = models.JSONField(default=list, blank=True, verbose_name='Fuentes de Fondos (Frontend)', help_text='Array con opciones múltiples de fuentes')
    tiposRecursos = models.JSONField(default=list, blank=True, verbose_name='Tipos Recursos (Frontend)')
    
    # Declaraciones obligatorias SARLAFT/PEP
    constituyePatrimoniosAutonomos = models.BooleanField(
        null=True, 
        blank=True, 
        verbose_name='Constituye Patrimonios Autónomos (Frontend)',
        help_text='Declaración obligatoria SARLAFT'
    )
    declaracionTransparencia = models.BooleanField(
        null=True, 
        blank=True, 
        verbose_name='Declaración de Transparencia (Frontend)',
        help_text='Declaración obligatoria SARLAFT'
    )
    
    # === CAMPOS NUEVOS DEL FORMULARIO FRONTEND ===
    # Campo para que el tercero elija su comercial
    comercial_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_elegidos_por_tercero',
        verbose_name='Comercial Asignado por el Tercero',
        help_text='Comercial elegido por el tercero durante el registro'
    )
    
    # Campos adicionales del formulario
    nombreRazonSocial = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name='Nombre/Razón Social (Frontend)',
        help_text='Campo unificado del frontend'
    )
    
    # Campos PEP específicos
    patrimonioFiducia = models.BooleanField(
        null=True, 
        blank=True, 
        verbose_name='Patrimonio en Fiducia (Frontend)'
    )
    
    relacionesComerciales = models.BooleanField(
        null=True, 
        blank=True, 
        verbose_name='Relaciones Comerciales (Frontend)'
    )
    
    # Información adicional PEP
    informacionPEP = models.JSONField(
        default=list, 
        blank=True, 
        verbose_name='Información PEP (Frontend)',
        help_text='Array de objetos con datos de personas expuestas políticamente'
    )
    
    # Arrays de representantes y accionistas que envía el frontend
    representantes = models.JSONField(default=list, blank=True, verbose_name='Representantes (Frontend)')
    accionistas_frontend = models.JSONField(default=list, blank=True, verbose_name='Accionistas Frontend')
    
    # Campos de workflow
    estado_aprobacion = models.CharField(
        max_length=30,  # Aumentamos para los nuevos estados más largos
        choices=EstadoAprobacion.choices,
        default=EstadoAprobacion.PENDIENTE,
        verbose_name='Estado de Aprobación'
    )
    
    # Relaciones
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='terceros_creados',
        verbose_name='Creado por'
    )
    
    aprobado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_aprobados',
        verbose_name='Aprobado por'
    )
    
    asignado_a = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_asignados_comercial',
        verbose_name='Asignado Comercial',
        help_text='Comercial asignado para gestión del tercero'
    )
    
    asignado_a_procesos = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_asignados_procesos',
        verbose_name='Asignado a Procesos',
        help_text='Usuario de procesos asignado para revisión'
    )
    
    asignado_cumplimiento = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_asignados_cumplimiento',
        verbose_name='Asignado a Cumplimiento',
        help_text='Oficial de cumplimiento asignado para revisión SARLAFT'
    )
    
    # Fechas de asignación
    fecha_asignacion_comercial = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de asignación a comercial'
    )
    
    fecha_asignacion_procesos = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de asignación a procesos'
    )
    
    fecha_asignacion_cumplimiento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de asignación a cumplimiento'
    )
    
    # Observaciones por departamento
    observaciones_comercial = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones del Comercial',
        help_text='Comentarios del comercial durante la revisión'
    )
    
    observaciones_procesos = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones de Procesos',
        help_text='Comentarios de procesos durante la revisión'
    )
    
    observaciones_cumplimiento = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones de Cumplimiento',
        help_text='Comentarios del oficial de cumplimiento durante revisión SARLAFT'
    )
    
    observaciones_administrador = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones del Administrador',
        help_text='Comentarios del administrador durante la gestión del tercero'
    )
    
    # Historial de cambios de estado
    fecha_ultimo_cambio_estado = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha último cambio de estado'
    )
    
    usuario_ultimo_cambio = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_cambios_estado',
        verbose_name='Usuario último cambio',
        help_text='Usuario que realizó el último cambio de estado'
    )
    
    # Nuevos campos para el flujo extendido
    aprobado_por_comercial = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_aprobados_comercial',
        verbose_name='Aprobado por Comercial',
        help_text='Usuario comercial que realizó la aprobación inicial'
    )
    
    fecha_aprobacion_comercial = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de aprobación comercial'
    )
    
    asignado_administrador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_asignados_admin',
        verbose_name='Asignado a Administrador',
        help_text='Administrador que gestiona la asignación a procesos'
    )
    
    fecha_asignacion_administrador = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de asignación a administrador'
    )
    
    aprobado_por_procesos = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_aprobados_procesos',
        verbose_name='Aprobado por Procesos',
        help_text='Usuario de procesos que realizó la aprobación'
    )
    
    fecha_aprobacion_procesos = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de aprobación procesos'
    )
    
    asignado_cumplimiento = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_asignados_cumplimiento',
        verbose_name='Asignado a Cumplimiento',
        help_text='Oficial de cumplimiento asignado para revisión'
    )
    
    fecha_asignacion_cumplimiento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de asignación a cumplimiento'
    )
    
    # CAMPOS CENTRALIZADOS SEGÚN NUEVO FLUJO
    # ==========================================
    usuario_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terceros_asignados_actual',
        verbose_name='Usuario Asignado Actual',
        help_text='Usuario actualmente responsable de la solicitud'
    )
    
    rol_asignado = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('comercial', 'Comercial'),
            ('administrador', 'Administrador'),
            ('procesos', 'Procesos'),
            ('oficial_cumplimiento', 'Oficial de Cumplimiento'),
        ],
        verbose_name='Rol Asignado',
        help_text='Rol del usuario actualmente responsable'
    )
    
    fecha_asignacion_actual = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Asignación Actual',
        help_text='Fecha de la asignación actual'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')
    
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de aprobación')
    
    # Campos adicionales
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')
    
    # Campos específicos para comerciales
    observaciones_comercial = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Observaciones del Comercial',
        help_text='Comentarios y observaciones del comercial durante la gestión'
    )
    
    comentarios_aprobacion = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Comentarios de Aprobación',
        help_text='Comentarios específicos durante el proceso de aprobación'
    )
    
    notas_internas = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Notas Internas',
        help_text='Notas internas del equipo comercial'
    )
    
    fecha_contacto_inicial = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='Fecha de Contacto Inicial',
        help_text='Fecha del primer contacto comercial'
    )
    
    canal_contacto = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('telefono', 'Teléfono'),
            ('email', 'Email'),
            ('whatsapp', 'WhatsApp'),
            ('presencial', 'Presencial'),
            ('web', 'Página Web'),
            ('referido', 'Referido'),
            ('otro', 'Otro')
        ],
        verbose_name='Canal de Contacto',
        help_text='Canal por el cual se estableció el primer contacto'
    )
    
    prioridad_comercial = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ('alta', 'Alta'),
            ('media', 'Media'),
            ('baja', 'Baja')
        ],
        default='media',
        verbose_name='Prioridad Comercial',
        help_text='Prioridad asignada por el comercial'
    )
    
    activo = models.BooleanField(default=True, verbose_name='Activo')

    # ==========================================
    # MÉTODOS DE VALIDACIÓN DE WORKFLOW
    # ==========================================
    
    @classmethod
    def get_transiciones_validas(cls):
        """
        Retorna las transiciones válidas según el flujo de negocio definido.
        
        Flujo de Gestión de Terceros:
        1. Tercero diligencia formulario → PENDIENTE
        2. Se asigna automáticamente a Comercial → EN_CURSO_COMERCIAL
        3. Comercial puede:
           - Enviar a corrección → EN_ESPERA_CORRECCION
           - Asignar a Administrador → ASIGNADA_ADMINISTRADOR
        4. Administrador puede:
           - Trabajar directamente → EN_CURSO_ADMINISTRADOR
           - Asignar a Procesos → ASIGNADA_PROCESOS
           - Asignar a Cumplimiento → ASIGNADA_OFICIAL_CUMPLIMIENTO
           - Aprobar/Rechazar/Finalizar directamente
        5. Procesos puede:
           - Trabajar → EN_CURSO_PROCESOS
           - Devolver a Comercial → DEVUELTO_COMERCIAL
           - Asignar a Cumplimiento → ASIGNADA_OFICIAL_CUMPLIMIENTO
           - Finalizar/Rechazar
        6. Cumplimiento puede:
           - Trabajar → EN_CURSO_CUMPLIMIENTO
           - Aprobar/Rechazar (estados finales)
        """
        return {
            # 1. Estado inicial
            cls.EstadoAprobacion.PENDIENTE: [
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL  # Asignación automática a comercial
            ],
            
            # 2. Flujo Comercial
            cls.EstadoAprobacion.EN_CURSO_COMERCIAL: [
                cls.EstadoAprobacion.EN_ESPERA_CORRECCION,  # Solicitar corrección al tercero
                cls.EstadoAprobacion.ASIGNADA_ADMINISTRADOR  # Enviar a administrador
            ],
            cls.EstadoAprobacion.EN_ESPERA_CORRECCION: [
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL  # Tercero corrige y vuelve a comercial
            ],
            cls.EstadoAprobacion.DEVUELTO_COMERCIAL: [
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL  # Comercial retoma el trabajo
            ],
            
            # 3. Flujo Administrador
            cls.EstadoAprobacion.ASIGNADA_ADMINISTRADOR: [
                cls.EstadoAprobacion.EN_CURSO_ADMINISTRADOR  # Administrador comienza a trabajar
            ],
            cls.EstadoAprobacion.EN_CURSO_ADMINISTRADOR: [
                cls.EstadoAprobacion.ASIGNADA_PROCESOS,                # Enviar a procesos
                cls.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO,    # Enviar a cumplimiento
                cls.EstadoAprobacion.APROBADO,                         # Aprobar directamente
                cls.EstadoAprobacion.RECHAZADO,                        # Rechazar directamente
                cls.EstadoAprobacion.FINALIZADO                        # Finalizar directamente
            ],
            
            # 4. Flujo Procesos
            cls.EstadoAprobacion.ASIGNADA_PROCESOS: [
                cls.EstadoAprobacion.EN_CURSO_PROCESOS  # Procesos comienza a trabajar
            ],
            cls.EstadoAprobacion.EN_CURSO_PROCESOS: [
                cls.EstadoAprobacion.DEVUELTO_COMERCIAL,               # Devolver a comercial
                cls.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO,    # Enviar a cumplimiento
                cls.EstadoAprobacion.FINALIZADO,                       # Finalizar directamente
                cls.EstadoAprobacion.RECHAZADO                         # Rechazar directamente
            ],
            
            # 5. Flujo Cumplimiento
            cls.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO: [
                cls.EstadoAprobacion.EN_CURSO_CUMPLIMIENTO  # Cumplimiento comienza a trabajar
            ],
            cls.EstadoAprobacion.EN_CURSO_CUMPLIMIENTO: [
                cls.EstadoAprobacion.APROBADO,    # Estado final: Aprobado
                cls.EstadoAprobacion.RECHAZADO    # Estado final: Rechazado
            ],
            
            # 6. Estados finales (solo administrador puede reabrir)
            cls.EstadoAprobacion.APROBADO: [
                cls.EstadoAprobacion.PENDIENTE,              # Reabrir proceso
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL,     # Volver a comercial
                cls.EstadoAprobacion.ASIGNADA_ADMINISTRADOR  # Volver a administrador
            ],
            cls.EstadoAprobacion.RECHAZADO: [
                cls.EstadoAprobacion.PENDIENTE,              # Reabrir proceso
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL,     # Volver a comercial
                cls.EstadoAprobacion.ASIGNADA_ADMINISTRADOR  # Volver a administrador
            ],
            cls.EstadoAprobacion.FINALIZADO: [
                cls.EstadoAprobacion.PENDIENTE,              # Reabrir proceso
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL,     # Volver a comercial
                cls.EstadoAprobacion.ASIGNADA_ADMINISTRADOR  # Volver a administrador
            ]
        }
    
    @classmethod
    def get_permisos_por_rol(cls):
        """
        Retorna los estados que puede cambiar cada rol según el flujo de negocio.
        
        Restricciones por rol:
        - Comercial: solo puede cambiar dentro de su área
        - Procesos: puede devolver a comercial y enviar a cumplimiento
        - Cumplimiento: puede dar estados finales (Aprobado/Rechazado)
        - Administrador: puede cambiar cualquier estado y reasignar
        """
        return {
            'administrador': '*',  # Puede cambiar a cualquier estado
            'comercial': [
                cls.EstadoAprobacion.EN_CURSO_COMERCIAL,
                cls.EstadoAprobacion.EN_ESPERA_CORRECCION,
                cls.EstadoAprobacion.ASIGNADA_ADMINISTRADOR
            ],
            'procesos': [
                cls.EstadoAprobacion.EN_CURSO_PROCESOS,
                cls.EstadoAprobacion.DEVUELTO_COMERCIAL,
                cls.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO,
                cls.EstadoAprobacion.FINALIZADO,
                cls.EstadoAprobacion.RECHAZADO
            ],
            'oficial_cumplimiento': [
                cls.EstadoAprobacion.EN_CURSO_CUMPLIMIENTO,
                cls.EstadoAprobacion.APROBADO,
                cls.EstadoAprobacion.RECHAZADO
            ]
        }
    
    def puede_transicionar_a(self, nuevo_estado):
        """Valida si el tercero puede cambiar al nuevo estado"""
        transiciones_validas = self.get_transiciones_validas()
        estados_permitidos = transiciones_validas.get(self.estado_aprobacion, [])
        return nuevo_estado in estados_permitidos
    
    def usuario_puede_cambiar_estado(self, usuario, nuevo_estado):
        """Valida si el usuario tiene permisos para cambiar al nuevo estado"""
        if not hasattr(usuario, 'role'):
            return False
            
        permisos = self.get_permisos_por_rol()
        estados_permitidos = permisos.get(usuario.role, [])
        
        # Administrador puede cambiar a cualquier estado
        if estados_permitidos == '*':
            return True
            
        return nuevo_estado in estados_permitidos
    
    def puede_cambiar_a_estado(self, nuevo_estado, usuario):
        """
        Valida si se puede cambiar al nuevo estado considerando transiciones y permisos
        Método wrapper para mantener compatibilidad con views
        """
        # Primero verificar permisos del usuario
        if not self.usuario_puede_cambiar_estado(usuario, nuevo_estado):
            return False
        
        # Si es administrador, permitir transiciones especiales desde estados finales
        if hasattr(usuario, 'role') and usuario.role == 'administrador':
            # Los administradores pueden "resetear" desde estados finales
            estados_finales = [
                self.EstadoAprobacion.APROBADO,
                self.EstadoAprobacion.RECHAZADO,
                self.EstadoAprobacion.FINALIZADO
            ]
            
            estados_reset_permitidos = [
                self.EstadoAprobacion.PENDIENTE,
                self.EstadoAprobacion.EN_CURSO_COMERCIAL,
                self.EstadoAprobacion.ASIGNADA_PROCESOS,
                self.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO,
                self.EstadoAprobacion.ASIGNADA_ADMINISTRADOR
            ]
            
            # Si está en estado final y quiere ir a un estado de reset, permitir
            if (self.estado_aprobacion in estados_finales and 
                nuevo_estado in estados_reset_permitidos):
                return True
        
        # Para otros casos, verificar que la transición es válida
        return self.puede_transicionar_a(nuevo_estado)
    
    def obtener_transiciones_permitidas(self, usuario):
        """
        Obtiene las transiciones permitidas desde el estado actual para un usuario específico
        Retorna dict con estados como claves y listas de transiciones como valores
        """
        if not hasattr(usuario, 'role'):
            return {}
            
        # Obtener transiciones válidas desde el estado actual
        transiciones_validas = self.get_transiciones_validas()
        estados_permitidos_desde_actual = transiciones_validas.get(self.estado_aprobacion, [])
        
        # Obtener permisos del rol del usuario
        permisos = self.get_permisos_por_rol()
        estados_permitidos_por_rol = permisos.get(usuario.role, [])
        
        # Si el administrador puede cambiar a cualquier estado
        if estados_permitidos_por_rol == '*':
            # Los administradores pueden hacer cualquier transición válida desde el estado actual
            # más pueden "resetear" a ciertos estados estratégicos
            estados_finales = estados_permitidos_desde_actual.copy()
            
            # Agregar estados estratégicos para administradores
            estados_estrategicos = [
                self.EstadoAprobacion.PENDIENTE,
                self.EstadoAprobacion.EN_CURSO_COMERCIAL,
                self.EstadoAprobacion.ASIGNADA_PROCESOS,
                self.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO
            ]
            
            for estado in estados_estrategicos:
                if estado not in estados_finales:
                    estados_finales.append(estado)
                    
            return {self.estado_aprobacion: estados_finales}
        
        # Para otros roles, filtrar transiciones válidas por permisos del rol
        transiciones_permitidas = []
        for estado_destino in estados_permitidos_desde_actual:
            if estado_destino in estados_permitidos_por_rol:
                transiciones_permitidas.append(estado_destino)
        
        return {self.estado_aprobacion: transiciones_permitidas}
    
    def cambiar_estado(self, nuevo_estado, usuario, observaciones=None, request=None):
        """
        Cambia el estado del tercero con validaciones completas
        Retorna tuple (success: bool, message: str)
        """
        # Validar transición
        if not self.puede_transicionar_a(nuevo_estado):
            return False, f"Transición no válida de {self.estado_aprobacion} a {nuevo_estado}"
        
        # Validar permisos de usuario
        if not self.usuario_puede_cambiar_estado(usuario, nuevo_estado):
            return False, f"Usuario {usuario.role} no puede cambiar a estado {nuevo_estado}"
        
        # Ejecutar cambio de estado
        estado_anterior = self.estado_aprobacion
        self.estado_aprobacion = nuevo_estado
        self.usuario_ultimo_cambio = usuario
        self.fecha_ultimo_cambio_estado = timezone.now()
        
        # Guardar observaciones según el rol
        if observaciones:
            if usuario.role == 'comercial':
                self.observaciones_comercial = observaciones
            elif usuario.role == 'procesos':
                self.observaciones_procesos = observaciones
            elif usuario.role == 'oficial_cumplimiento':
                self.observaciones_cumplimiento = observaciones
            elif usuario.role == 'administrador':
                self.observaciones_administrador = observaciones
        
        # Lógica específica según el nuevo estado
        if nuevo_estado == self.EstadoAprobacion.EN_CURSO_COMERCIAL:
            self._asignar_comercial_automatico()
        elif nuevo_estado == self.EstadoAprobacion.ASIGNADA_PROCESOS:
            self._asignar_procesos_automatico()
        elif nuevo_estado == self.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO:
            self._asignar_cumplimiento_automatico()
        
        self.save()
        
        # Registrar en historial
        self._registrar_historial_cambio_estado(
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            usuario=usuario,
            observaciones=observaciones,
            request=request
        )
        
        # Enviar notificaciones/emails según corresponda
        self._enviar_notificacion_cambio_estado(estado_anterior, nuevo_estado, usuario, observaciones)
        
        return True, f"Estado cambiado exitosamente a {nuevo_estado}"
    
    def _asignar_comercial_automatico(self):
        """Asigna automáticamente un comercial disponible"""
        from django.db.models import Count
        
        comercial = User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            num_terceros=Count('terceros_asignados_comercial')
        ).order_by('num_terceros').first()
        
        if comercial:
            self.asignado_a = comercial
            self.fecha_asignacion_comercial = timezone.now()
    
    def _asignar_procesos_automatico(self):
        """Asigna automáticamente un usuario de procesos disponible"""
        from django.db.models import Count
        
        procesos = User.objects.filter(
            role='procesos',
            is_active=True
        ).annotate(
            num_terceros=Count('terceros_asignados_procesos')
        ).order_by('num_terceros').first()
        
        if procesos:
            self.asignado_a_procesos = procesos
            self.fecha_asignacion_procesos = timezone.now()
    
    def _asignar_cumplimiento_automatico(self):
        """Asigna automáticamente un oficial de cumplimiento disponible"""
        from django.db.models import Count
        
        cumplimiento = User.objects.filter(
            role='oficial_cumplimiento',
            is_active=True
        ).annotate(
            num_terceros=Count('terceros_asignados_cumplimiento')
        ).order_by('num_terceros').first()
        
        if cumplimiento:
            self.asignado_cumplimiento = cumplimiento
            self.fecha_asignacion_cumplimiento = timezone.now()
    
    def _enviar_notificacion_cambio_estado(self, estado_anterior, nuevo_estado, usuario, observaciones):
        """Envía notificaciones/emails según el cambio de estado"""
        from django.core.mail import send_mail
        
        try:
            # Importar configuración de correos
            from django.conf import settings
            
            # Email cuando comercial rechaza -> al usuario original
            if nuevo_estado == self.EstadoAprobacion.RECHAZADO_COMERCIAL:
                if self.email:
                    send_mail(
                        subject=f'Tercero {self.numero_documento} requiere ajustes',
                        message=f'Su solicitud ha sido devuelta por el comercial.\nObservaciones: {observaciones or "No especificadas"}',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[self.email],
                        fail_silently=True
                    )
            
            # Email cuando procesos rechaza -> al comercial asignado
            elif nuevo_estado == self.EstadoAprobacion.RECHAZADO_PROCESOS:
                if self.asignado_a and self.asignado_a.email:
                    send_mail(
                        subject=f'Tercero {self.numero_documento} devuelto por procesos',
                        message=f'El tercero ha sido devuelto por procesos.\nObservaciones: {observaciones or "No especificadas"}',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[self.asignado_a.email],
                        fail_silently=True
                    )
            
            # Email cuando se aprueba final -> a destinatarios configurados
            elif nuevo_estado == self.EstadoAprobacion.APROBADO:
                # Usar destinatarios configurados en lugar de hardcodeados
                destinatarios = getattr(settings, 'EMAILS_PREDETERMINADOS', [])
                if destinatarios:
                    send_mail(
                        subject=f'Nuevo tercero aprobado: {self.numero_documento}',
                        message=f'El tercero {self.numero_documento} ha sido aprobado y está listo para contabilidad.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=destinatarios,
                        fail_silently=True
                    )
                
        except Exception as e:
            # Log error pero no fallar el cambio de estado
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando email para tercero {self.id}: {str(e)}")

    # ==========================================
    # MÉTODOS DE CORREO ELECTRÓNICO
    # ==========================================
    
    def generar_datos_para_correo(self, incluir_cert_bancaria=False, 
                                  incluir_info_comercial=False, 
                                  incluir_info_adicional=False):
        """
        Genera estructura de datos completa para el correo
        Incluye: información personal, jurídica, comercial y documentos
        """
        from datetime import datetime
        
        datos = {
            # Información de identificación
            'identificacion': {
                'tipo_persona': self.get_tipo_persona_display(),
                'tipo_documento': self.get_tipo_documento_display(),
                'numero_documento': self.numero_documento,
                'digito_verificacion': self.digito_verificacion or ''
            },
            
            # Información personal 
            'informacion_personal': {
                'nombres': self.nombres or '',
                'apellidos': self.apellidos or '',
                'nombre_completo': f"{self.nombres or ''} {self.apellidos or ''}".strip(),
                'razon_social': self.razon_social or '',
                'fecha_nacimiento': self.fecha_nacimiento.strftime('%d/%m/%Y') if self.fecha_nacimiento else ''
            },
            
            # Información de contacto
            'informacion_contacto': {
                'email': self.email or '',
                'telefono': self.telefono or '',
                'celular': self.celular or '',
                'direccion': self.direccion or '',
                'ciudad': self.ciudad or '',
                'departamento': self.departamento or '',
                'pais': self.pais or 'Colombia'
            },
            
            # Información jurídica/comercial
            'informacion_juridica': {
                'estado_aprobacion': self.get_estado_aprobacion_display(),
                'fecha_creacion': self.fecha_creacion.strftime('%d/%m/%Y') if self.fecha_creacion else '',
                'actividad_economica': self.actividad_economica_principal or '',
                'codigo_ciiu': self.codigo_ciiu or '',
                'responsable_iva': self.responsable_iva,
                'gran_contribuyente': self.gran_contribuyente,
                'auto_retenedor': self.auto_retenedor
            },
            
            # Metadatos del correo
            'fecha_aprobacion': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'fecha_envio': datetime.now().strftime('%d/%m/%Y %H:%M'),
            
            # Tercero original para referencia
            'tercero': self
        }
        
        # Agregar documentos si están disponibles
        documentos = self._obtener_documentos_para_correo(incluir_cert_bancaria)
        if documentos:
            datos['documentos'] = documentos
            
        return datos
    
    def _obtener_documentos_para_correo(self, incluir_cert_bancaria=False):
        """
        Obtiene documentos del tercero para adjuntar al correo
        Incluye RUT, certificación bancaria y otros documentos según configuración
        """
        documentos = {}
        
        try:
            # Usar el modelo DocumentoTercero de la misma app terceros
            docs_tercero = DocumentoTercero.objects.filter(
                tercero=self,
                es_vigente=True  # Solo documentos vigentes
            ).order_by('-fecha_subida')
            
            # Importar configuración
            from euro_terceros.config import DOCUMENTOS_CONFIG
            
            # Obtener mapeo de tipos para buscar documentos
            mapeo_tipos = DOCUMENTOS_CONFIG.get('mapeo_tipos', {})
            tipos_incluir = DOCUMENTOS_CONFIG.get('tipos_incluir', [])
            tipos_opcionales = DOCUMENTOS_CONFIG.get('tipos_opcionales', [])
            
            # Función para verificar si un tipo de documento coincide
            def tipo_coincide(tipo_doc, tipos_buscar):
                tipo_doc_lower = tipo_doc.lower()
                for tipo_buscar in tipos_buscar:
                    if tipo_buscar.lower() in tipo_doc_lower:
                        return True
                return False
            
            for doc in docs_tercero:
                incluir_documento = False
                categoria_documento = None
                
                # Verificar documentos que SIEMPRE se incluyen (RUT y certificación bancaria)
                for tipo_categoria, tipos_buscar in mapeo_tipos.items():
                    if tipo_categoria in tipos_incluir and tipo_coincide(doc.tipo_documento, tipos_buscar):
                        incluir_documento = True
                        categoria_documento = tipo_categoria
                        break
                
                # Incluir el documento si cumple criterios
                if incluir_documento and doc.archivo:
                    # Verificar que el archivo existe y es accesible
                    try:
                        if hasattr(doc.archivo, 'url') and hasattr(doc.archivo, 'path'):
                            import os
                            if os.path.exists(doc.archivo.path):
                                # Determinar nombre del archivo
                                nombre_display = doc.get_tipo_documento_display() if hasattr(doc, 'get_tipo_documento_display') else doc.tipo_documento
                                extension = '.pdf'  # Por defecto PDF
                                if doc.archivo.name:
                                    _, ext = os.path.splitext(doc.archivo.name)
                                    if ext:
                                        extension = ext
                                
                                documentos[categoria_documento or doc.tipo_documento] = {
                                    'nombre': f"{nombre_display}{extension}",
                                    'url': doc.archivo.url,
                                    'path': doc.archivo.path,
                                    'fecha_subida': doc.fecha_subida.strftime('%d/%m/%Y') if doc.fecha_subida else '',
                                    'tipo_display': nombre_display,
                                    'categoria': categoria_documento or 'otros',
                                    'tamano': getattr(doc, 'tamano_archivo', 0)
                                }
                                
                                # ✅ Continuar procesando otros documentos (no usar break)
                    except Exception as archivo_error:
                        # Log pero continuar con otros documentos
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error accediendo archivo {doc.archivo}: {str(archivo_error)}")
                        continue
            
            # Log de documentos encontrados para debug
            if documentos:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Documentos encontrados para tercero {self.numero_documento}: {list(documentos.keys())}")
            
        except Exception as e:
            # Log error pero continuar
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo documentos para tercero {self.id}: {str(e)}")
            
        return documentos

    # ==========================================
    # MÉTODOS DE HISTORIAL Y AUDITORÍA
    # ==========================================

    def _registrar_historial_cambio_estado(self, estado_anterior, estado_nuevo, usuario, observaciones=None, request=None):
        """Registra un cambio de estado en el historial"""
        # Determinar el tipo de acción específico
        accion = HistorialTercero.TipoAccion.CAMBIO_ESTADO
        
        if 'aprobado' in estado_nuevo.lower():
            accion = HistorialTercero.TipoAccion.APROBACION
        elif 'rechazado' in estado_nuevo.lower():
            accion = HistorialTercero.TipoAccion.RECHAZO
        elif usuario and hasattr(usuario, 'role') and usuario.role == 'administrador' and estado_nuevo == 'pendiente':
            accion = HistorialTercero.TipoAccion.RESET
        
        self._crear_entrada_historial(
            accion=accion,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            usuario=usuario,
            observaciones=observaciones,
            departamento=getattr(usuario, 'role', None) if usuario else None,
            request=request
        )

    def _registrar_historial_asignacion(self, tipo_asignacion, usuario_anterior, usuario_nuevo, usuario_asignador, observaciones=None, request=None):
        """Registra una asignación en el historial"""
        acciones_map = {
            'comercial': HistorialTercero.TipoAccion.ASIGNACION_COMERCIAL,
            'procesos': HistorialTercero.TipoAccion.ASIGNACION_PROCESOS,
            'cumplimiento': HistorialTercero.TipoAccion.ASIGNACION_CUMPLIMIENTO,
            'administrador': HistorialTercero.TipoAccion.ASIGNACION_ADMINISTRADOR,
        }
        
        accion = acciones_map.get(tipo_asignacion, HistorialTercero.TipoAccion.ASIGNACION_COMERCIAL)
        if usuario_anterior and usuario_nuevo and usuario_anterior != usuario_nuevo:
            accion = HistorialTercero.TipoAccion.REASIGNACION
        
        self._crear_entrada_historial(
            accion=accion,
            usuario=usuario_asignador,
            usuario_asignado_anterior=usuario_anterior,
            usuario_asignado_nuevo=usuario_nuevo,
            departamento=tipo_asignacion,
            observaciones=observaciones,
            request=request
        )

    def _registrar_historial_observacion(self, usuario, observaciones, request=None):
        """Registra cuando se agregan observaciones"""
        self._crear_entrada_historial(
            accion=HistorialTercero.TipoAccion.OBSERVACION,
            usuario=usuario,
            observaciones=observaciones,
            departamento=getattr(usuario, 'role', None) if usuario else None,
            request=request
        )

    def _crear_entrada_historial(self, accion, usuario=None, estado_anterior=None, estado_nuevo=None, 
                                usuario_asignado_anterior=None, usuario_asignado_nuevo=None, 
                                departamento=None, observaciones=None, metadatos=None, request=None):
        """Método auxiliar para crear entradas en el historial"""
        # Extraer información de la request si está disponible
        ip_address = None
        user_agent = None
        
        if request:
            # Obtener IP del cliente
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Obtener User Agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Crear la entrada de historial
        HistorialTercero.objects.create(
            tercero=self,
            accion=accion,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            usuario=usuario,
            usuario_asignado_anterior=usuario_asignado_anterior,
            usuario_asignado_nuevo=usuario_asignado_nuevo,
            departamento=departamento,
            observaciones=observaciones,
            metadatos=metadatos or {},
            ip_address=ip_address,
            user_agent=user_agent
        )

    def asignar_a_comercial(self, comercial, usuario_asignador, observaciones=None, request=None):
        """Asigna el tercero a un comercial específico"""
        usuario_anterior = self.asignado_a
        self.asignado_a = comercial
        self.fecha_asignacion_comercial = timezone.now()
        self.save()
        
        # Registrar en historial
        self._registrar_historial_asignacion(
            tipo_asignacion='comercial',
            usuario_anterior=usuario_anterior,
            usuario_nuevo=comercial,
            usuario_asignador=usuario_asignador,
            observaciones=observaciones,
            request=request
        )

    def asignar_a_procesos(self, procesos, usuario_asignador, observaciones=None, request=None):
        """Asigna el tercero a un usuario de procesos específico"""
        usuario_anterior = self.asignado_a_procesos
        self.asignado_a_procesos = procesos
        self.fecha_asignacion_procesos = timezone.now()
        self.save()
        
        # Registrar en historial
        self._registrar_historial_asignacion(
            tipo_asignacion='procesos',
            usuario_anterior=usuario_anterior,
            usuario_nuevo=procesos,
            usuario_asignador=usuario_asignador,
            observaciones=observaciones,
            request=request
        )

    def asignar_a_cumplimiento(self, cumplimiento, usuario_asignador, observaciones=None, request=None):
        """Asigna el tercero a un oficial de cumplimiento específico"""
        usuario_anterior = self.asignado_cumplimiento
        self.asignado_cumplimiento = cumplimiento
        self.fecha_asignacion_cumplimiento = timezone.now()
        self.save()
        
        # Registrar en historial
        self._registrar_historial_asignacion(
            tipo_asignacion='cumplimiento',
            usuario_anterior=usuario_anterior,
            usuario_nuevo=cumplimiento,
            usuario_asignador=usuario_asignador,
            observaciones=observaciones,
            request=request
        )

    def obtener_historial_completo(self):
        """Retorna el historial completo del tercero ordenado por fecha"""
        return self.historial.all().select_related(
            'usuario', 'usuario_asignado_anterior', 'usuario_asignado_nuevo'
        ).order_by('-fecha_accion')

    def obtener_asignacion_actual(self):
        """Retorna información de la asignación actual"""
        asignacion_actual = {
            'comercial': {
                'usuario': self.asignado_a,
                'fecha': self.fecha_asignacion_comercial,
                'observaciones': self.observaciones_comercial
            },
            'procesos': {
                'usuario': self.asignado_a_procesos,
                'fecha': self.fecha_asignacion_procesos,
                'observaciones': self.observaciones_procesos
            },
            'cumplimiento': {
                'usuario': self.asignado_cumplimiento,
                'fecha': self.fecha_asignacion_cumplimiento,
                'observaciones': self.observaciones_cumplimiento
            },
            'administrador': {
                'observaciones': self.observaciones_administrador
            }
        }
        
        return asignacion_actual

    def obtener_ultima_accion(self):
        """Retorna la última acción realizada en el tercero"""
        return self.historial.first()

    def obtener_historial_por_tipo(self, accion_tipo):
        """Retorna el historial filtrado por tipo de acción"""
        return self.historial.filter(accion=accion_tipo).order_by('-fecha_accion')

    def obtener_aprobaciones(self):
        """Retorna todas las aprobaciones del tercero"""
        return self.historial.filter(
            accion=HistorialTercero.TipoAccion.APROBACION
        ).order_by('-fecha_accion')

    def obtener_rechazos(self):
        """Retorna todos los rechazos del tercero"""
        return self.historial.filter(
            accion=HistorialTercero.TipoAccion.RECHAZO
        ).order_by('-fecha_accion')

    def obtener_asignaciones(self):
        """Retorna todas las asignaciones del tercero"""
        return self.historial.filter(
            accion__in=[
                HistorialTercero.TipoAccion.ASIGNACION_COMERCIAL,
                HistorialTercero.TipoAccion.ASIGNACION_PROCESOS,
                HistorialTercero.TipoAccion.ASIGNACION_CUMPLIMIENTO,
                HistorialTercero.TipoAccion.REASIGNACION
            ]
        ).order_by('-fecha_accion')

    def quien_aprobo_en_etapa(self, etapa):
        """
        Retorna quién aprobó en una etapa específica
        etapa: 'comercial', 'procesos', 'cumplimiento', 'final'
        """
        # Como solo tenemos un tipo de aprobación genérico, 
        # buscaremos por el estado del tercero en el momento de la aprobación
        aprobaciones = self.historial.filter(accion=HistorialTercero.TipoAccion.APROBACION)
        
        # Buscar por el estado nuevo que corresponde a la etapa
        estado_map = {
            'comercial': 'en_curso_comercial',
            'procesos': 'en_curso_procesos', 
            'cumplimiento': 'en_curso_cumplimiento',
            'final': 'aprobado'
        }
        
        if etapa not in estado_map:
            return None
            
        aprobacion = aprobaciones.filter(estado_nuevo=estado_map[etapa]).first()
        return aprobacion.usuario if aprobacion else None

    def obtener_observaciones_por_etapa(self, etapa):
        """
        Retorna las observaciones de una etapa específica
        etapa: 'comercial', 'procesos', 'cumplimiento', 'administrador'
        """
        historial_etapa = None
        
        if etapa == 'comercial':
            # Buscar aprobaciones o rechazos que resulten en estados de comercial
            historial_etapa = self.historial.filter(
                accion__in=[HistorialTercero.TipoAccion.APROBACION, HistorialTercero.TipoAccion.RECHAZO],
                estado_nuevo__in=['en_curso_comercial', 'rechazado']
            ).first()
        elif etapa == 'procesos':
            historial_etapa = self.historial.filter(
                accion__in=[HistorialTercero.TipoAccion.APROBACION, HistorialTercero.TipoAccion.RECHAZO],
                estado_nuevo__in=['en_curso_procesos', 'rechazado']
            ).first()
        elif etapa == 'cumplimiento':
            historial_etapa = self.historial.filter(
                accion__in=[HistorialTercero.TipoAccion.APROBACION, HistorialTercero.TipoAccion.RECHAZO],
                estado_nuevo__in=['en_curso_cumplimiento', 'aprobado', 'rechazado']
            ).first()
        elif etapa == 'administrador':
            # Buscar acciones de administrador
            historial_etapa = self.historial.filter(
                usuario__role='administrador'
            ).first()
        
        return historial_etapa.observaciones if historial_etapa else None

    def generar_resumen_workflow(self):
        """Genera un resumen del flujo de trabajo del tercero"""
        historial = self.obtener_historial_completo()
        
        resumen = {
            'estado_actual': self.estado_aprobacion,
            'asignacion_actual': self.obtener_asignacion_actual(),
            'fecha_creacion': self.created_at,
            'fecha_ultima_accion': historial.first().fecha_accion if historial.exists() else None,
            'total_acciones': historial.count(),
            'etapas_completadas': {
                'comercial': {
                    'aprobado_por': self.quien_aprobo_en_etapa('comercial'),
                    'observaciones': self.obtener_observaciones_por_etapa('comercial')
                },
                'procesos': {
                    'aprobado_por': self.quien_aprobo_en_etapa('procesos'),
                    'observaciones': self.obtener_observaciones_por_etapa('procesos')
                },
                'cumplimiento': {
                    'aprobado_por': self.quien_aprobo_en_etapa('cumplimiento'),
                    'observaciones': self.obtener_observaciones_por_etapa('cumplimiento')
                },
                'final': {
                    'aprobado_por': self.quien_aprobo_en_etapa('final'),
                    'observaciones': self.obtener_observaciones_por_etapa('administrador')
                }
            },
            'total_aprobaciones': self.obtener_aprobaciones().count(),
            'total_rechazos': self.obtener_rechazos().count(),
            'total_asignaciones': self.obtener_asignaciones().count()
        }
        
        return resumen

    # MÉTODOS DE MIGRACIÓN AL NUEVO FLUJO
    # ==========================================
    
    def migrar_a_nuevo_flujo(self):
        """Migra el tercero del flujo legacy al nuevo flujo"""
        mapeo_estados = {
            # Estados legacy → nuevos estados
            'pendiente': 'pendiente',
            'asignado_comercial': 'en_curso_comercial', 
            'aprobado_comercial': 'asignada_administrador',
            'rechazado_comercial': 'devuelto_comercial',
            'asignado_administrador': 'en_curso_administrador',
            'asignado_procesos': 'en_curso_procesos',
            'aprobado_procesos': 'asignada_oficial_cumplimiento', 
            'rechazado_procesos': 'devuelto_comercial',
            'enviado_cumplimiento': 'en_curso_cumplimiento',
            'aprobado_cumplimiento': 'aprobado',
            'rechazado_cumplimiento': 'rechazado',
            'aprobado_final': 'aprobado',
            'rechazado_final': 'rechazado',
            'en_revision': 'en_curso_procesos',
            'requiere_ajustes': 'en_espera_correccion',
        }
        
        # Migrar estado
        estado_actual = self.estado_aprobacion
        nuevo_estado = mapeo_estados.get(estado_actual, estado_actual)
        
        if nuevo_estado != estado_actual:
            self.estado_aprobacion = nuevo_estado
        
        # Migrar asignaciones centralizadas
        self._actualizar_asignacion_centralizada()
        
        self.save()
        
        return f"Migrado de '{estado_actual}' a '{nuevo_estado}'"
    
    def _actualizar_asignacion_centralizada(self):
        """Actualiza los campos centralizados basado en el estado actual"""
        estado_to_rol = {
            'pendiente': None,
            'en_curso_comercial': 'comercial',
            'en_espera_correccion': 'comercial', 
            'asignada_administrador': 'administrador',
            'en_curso_administrador': 'administrador',
            'asignada_procesos': 'procesos',
            'en_curso_procesos': 'procesos',
            'asignada_oficial_cumplimiento': 'oficial_cumplimiento',
            'en_curso_cumplimiento': 'oficial_cumplimiento',
            'devuelto_comercial': 'comercial',
            'aprobado': None,
            'rechazado': None,
            'finalizado': None,
        }
        
        self.rol_asignado = estado_to_rol.get(self.estado_aprobacion)
        
        # Actualizar usuario asignado basado en los campos legacy
        if self.rol_asignado == 'comercial' and self.asignado_a:
            self.usuario_asignado = self.asignado_a
            self.fecha_asignacion_actual = self.fecha_asignacion_comercial or timezone.now()
        elif self.rol_asignado == 'administrador' and self.asignado_administrador:
            self.usuario_asignado = self.asignado_administrador  
            self.fecha_asignacion_actual = self.fecha_asignacion_administrador or timezone.now()
        elif self.rol_asignado == 'procesos' and self.asignado_a_procesos:
            self.usuario_asignado = self.asignado_a_procesos
            self.fecha_asignacion_actual = self.fecha_asignacion_procesos or timezone.now()
        elif self.rol_asignado == 'oficial_cumplimiento' and self.asignado_cumplimiento:
            self.usuario_asignado = self.asignado_cumplimiento
            self.fecha_asignacion_actual = self.fecha_asignacion_cumplimiento or timezone.now()
        else:
            self.usuario_asignado = None
            self.fecha_asignacion_actual = None
    
    @classmethod
    def migrar_todos_a_nuevo_flujo(cls):
        """Migra todos los terceros al nuevo flujo"""
        terceros = cls.objects.all()
        resultados = []
        
        for tercero in terceros:
            try:
                resultado = tercero.migrar_a_nuevo_flujo()
                resultados.append(f"Tercero {tercero.id}: {resultado}")
            except Exception as e:
                resultados.append(f"Error en tercero {tercero.id}: {str(e)}")
        
        return resultados

    class Meta:
        verbose_name = 'Tercero'
        verbose_name_plural = 'Terceros'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['numero_documento']),
            models.Index(fields=['estado_aprobacion']),
            models.Index(fields=['created_at']),
        ]
    
    def contar_asignaciones_actuales(self):
        """Cuenta las asignaciones actuales del tercero"""
        count = 0
        if self.asignado_a:
            count += 1
        if self.asignado_a_procesos:
            count += 1
        if self.asignado_cumplimiento:
            count += 1
        if self.asignado_administrador:
            count += 1
        return count
    
    def registrar_accion(self, accion, usuario, observaciones=None, estado_anterior=None, estado_nuevo=None, request=None):
        """Registra una accion en el historial del tercero"""
        historial_data = {
            'tercero': self,
            'accion': accion,
            'usuario': usuario,
            'estado_anterior': estado_anterior or self.estado_aprobacion,
            'estado_nuevo': estado_nuevo or self.estado_aprobacion,
            'observaciones': observaciones or '',
        }
        
        # Agregar información de contexto si está disponible
        if request:
            historial_data['ip_address'] = request.META.get('REMOTE_ADDR')
            historial_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        return HistorialTercero.objects.create(**historial_data)
    
    def reparar_historial_asignaciones(self):
        """Repara el historial de asignaciones verificando el estado actual"""
        reparaciones = []
        
        # Verificar asignación comercial
        if self.asignado_a and not self.historial.filter(
            accion=HistorialTercero.TipoAccion.ASIGNACION_COMERCIAL,
            usuario_asignado_nuevo=self.asignado_a
        ).exists():
            self.registrar_accion(
                accion=HistorialTercero.TipoAccion.ASIGNACION_COMERCIAL,
                usuario=self.asignado_a,
                observaciones="Reparación automática de historial"
            )
            reparaciones.append("asignacion_comercial")
        
        # Verificar asignación procesos
        if self.asignado_a_procesos and not self.historial.filter(
            accion=HistorialTercero.TipoAccion.ASIGNACION_PROCESOS,
            usuario_asignado_nuevo=self.asignado_a_procesos
        ).exists():
            self.registrar_accion(
                accion=HistorialTercero.TipoAccion.ASIGNACION_PROCESOS,
                usuario=self.asignado_a_procesos,
                observaciones="Reparación automática de historial"
            )
            reparaciones.append("asignacion_procesos")
        
        # Verificar asignación cumplimiento
        if self.asignado_cumplimiento and not self.historial.filter(
            accion=HistorialTercero.TipoAccion.ASIGNACION_CUMPLIMIENTO,
            usuario_asignado_nuevo=self.asignado_cumplimiento
        ).exists():
            self.registrar_accion(
                accion=HistorialTercero.TipoAccion.ASIGNACION_CUMPLIMIENTO,
                usuario=self.asignado_cumplimiento,
                observaciones="Reparación automática de historial"
            )
            reparaciones.append("asignacion_cumplimiento")
        
        return reparaciones

    def clean(self):
        """Validaciones del modelo Tercero"""
        from django.core.exceptions import ValidationError
        
        # Validar que personas jurídicas solo usen NIT
        if self.tipo_persona in [self.TipoPersona.JURIDICA, self.TipoPersona.PUBLICA]:
            if self.tipo_documento != self.TipoDocumento.NIT:
                raise ValidationError(
                    "Las personas jurídicas y públicas deben usar únicamente NIT como tipo de documento"
                )
        
        # Validar campos de contacto obligatorios para registro nuevo
        if hasattr(self, '_validar_campos_registro') and self._validar_campos_registro:
            if not self.nombre_persona_contacto:
                raise ValidationError("El nombre de la persona de contacto es obligatorio")
            if not self.cargo_persona_contacto:
                raise ValidationError("El cargo de la persona de contacto es obligatorio")
        
        # Validar activos virtuales condicionales
        if self.manejo_activos_virtuales and not self.detalle_activos_virtuales:
            raise ValidationError(
                "Debe especificar el detalle de activos virtuales cuando indica que los maneja"
            )

    def __str__(self):
        if self.tipo_persona == self.TipoPersona.NATURAL:
            return f"{self.nombres} {self.apellidos or ''} ({self.numero_documento})"
        else:
            return f"{self.razon_social or self.nombres} ({self.numero_documento})"
    
    def get_nombre_completo(self):
        """Retorna el nombre completo dependiendo del tipo de persona"""
        if self.tipo_persona == self.TipoPersona.NATURAL:
            return f"{self.nombres} {self.apellidos or ''}".strip()
        else:
            return self.razon_social or self.nombres
    
    @property
    def puede_ser_aprobado(self):
        """Determina si el tercero puede ser aprobado"""
        return self.estado_aprobacion in [
            self.EstadoAprobacion.PENDIENTE,
            self.EstadoAprobacion.EN_REVISION,
            self.EstadoAprobacion.REQUIERE_AJUSTES
        ]
    
    @property
    def esta_aprobado(self):
        """Determina si el tercero está aprobado"""
        return self.estado_aprobacion == self.EstadoAprobacion.APROBADO
    
    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para asignar automáticamente a procesos
        Flujo: Terceros nuevos → Procesos (automático) → Comercial (manual por procesos)
        """
        # Si es un tercero nuevo (no existe en la BD) y no tiene usuario de procesos asignado
        is_new = self._state.adding
        if is_new and not self.asignado_a_procesos:
            self.asignado_a_procesos = asignar_procesos_automaticamente()
            self.fecha_asignacion_procesos = timezone.now()
        
        super().save(*args, **kwargs)
    
    def asignar_comercial(self, comercial_user):
        """
        Permite a procesos asignar manualmente un comercial específico
        """
        if comercial_user and hasattr(comercial_user, 'role') and comercial_user.role == 'comercial':
            self.asignado_a = comercial_user
            self.save()
            return True
        return False
    
    # Nuevos métodos para el flujo extendido
    def aprobar_por_comercial(self, comercial_user):
        """
        Aprueba el tercero en la etapa comercial y lo marca como aprobado final
        """
        if comercial_user and hasattr(comercial_user, 'role') and comercial_user.role == 'comercial':
            self.estado_aprobacion = self.EstadoAprobacion.APROBADO
            self.aprobado_por_comercial = comercial_user
            self.fecha_aprobacion_comercial = timezone.now()
            self.fecha_aprobacion = timezone.now()  # Fecha final de aprobación
            
            # Asignar automáticamente al primer administrador disponible para gestión
            admin_user = User.objects.filter(
                role='administrador',
                is_active=True
            ).first()
            
            if admin_user:
                self.asignado_administrador = admin_user
                self.fecha_asignacion_administrador = timezone.now()
                # Mantener estado como APROBADO
            
            self.save()
            return True
        return False
    
    def asignar_a_procesos_por_admin(self, admin_user, usuario_procesos):
        """
        Permite al administrador asignar el tercero a un usuario específico de procesos
        """
        if (admin_user and hasattr(admin_user, 'role') and admin_user.role == 'administrador' and
            usuario_procesos and hasattr(usuario_procesos, 'role') and usuario_procesos.role == 'procesos'):
            
            self.asignado_a_procesos = usuario_procesos
            self.fecha_asignacion_procesos = timezone.now()
            self.estado_aprobacion = self.EstadoAprobacion.ASIGNADA_PROCESOS
            self.save()
            return True
        return False
    
    def aprobar_por_procesos(self, usuario_procesos):
        """
        Aprueba el tercero en la etapa de procesos - aprobación final
        """
        if usuario_procesos and hasattr(usuario_procesos, 'role') and usuario_procesos.role == 'procesos':
            self.estado_aprobacion = self.EstadoAprobacion.APROBADO
            self.aprobado_por_procesos = usuario_procesos
            self.fecha_aprobacion_procesos = timezone.now()
            self.fecha_aprobacion = timezone.now()  # Fecha final de aprobación
            self.save()
            return True
        return False
    
    def enviar_a_cumplimiento(self, usuario_procesos):
        """
        Envía el tercero al oficial de cumplimiento para revisión
        """
        if usuario_procesos and hasattr(usuario_procesos, 'role') and usuario_procesos.role == 'procesos':
            # Asignar automáticamente al primer oficial de cumplimiento disponible
            oficial_cumplimiento = User.objects.filter(
                role='oficial_cumplimiento',
                is_active=True
            ).first()
            
            if oficial_cumplimiento:
                self.asignado_cumplimiento = oficial_cumplimiento
                self.fecha_asignacion_cumplimiento = timezone.now()
                self.estado_aprobacion = self.EstadoAprobacion.ASIGNADA_OFICIAL_CUMPLIMIENTO
                self.save()
                return True
        return False
    
    def aprobar_por_cumplimiento(self, oficial_cumplimiento):
        """
        Aprueba el tercero desde el área de cumplimiento - aprobación final
        """
        if oficial_cumplimiento and hasattr(oficial_cumplimiento, 'role') and oficial_cumplimiento.role == 'oficial_cumplimiento':
            self.estado_aprobacion = self.EstadoAprobacion.APROBADO
            self.fecha_aprobacion = timezone.now()
            self.save()
            return True
        return False
    
    def desasignar_comercial(self):
        """
        Quita el comercial asignado al tercero
        """
        if self.asignado_a:
            self.asignado_a = None
            self.save()
            return True
        return False
    
    def get_comerciales_disponibles(self):
        """
        Retorna lista de comerciales activos ordenados por carga de trabajo
        """
        from django.db.models import Count
        
        return User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            num_terceros_asignados=Count('terceros_asignados')
        ).order_by('num_terceros_asignados')
    
    @classmethod
    def get_comerciales_para_seleccion(cls):
        """
        Método de clase para obtener comerciales disponibles para selección del tercero
        """
        from django.db.models import Count
        
        return User.objects.filter(
            role='comercial',
            is_active=True
        ).annotate(
            num_terceros_asignados=Count('terceros_asignados')
        ).order_by('num_terceros_asignados').values(
            'id', 'first_name', 'last_name', 'username', 'num_terceros_asignados'
        )

class DocumentoTercero(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    TIPOS_DOCUMENTO_VINCULACION = [
        # Para persona natural
        ('documento_identidad', 'Documento de Identidad'),
        ('rut', 'RUT'),
        ('firma', 'Firma'),  # Nuevo documento agregado
        ('certificacion_comercial', 'Certificación Comercial'),
        ('certificacion_bancaria', 'Certificación Bancaria'),
        
        # Para persona jurídica
        ('documento_identidad_representante', 'Documento de Identidad del Representante Legal'),
        ('certificado_existencia_representacion', 'Certificado de Existencia y Representación'),
        ('composicion_accionaria_certificada', 'Composición Accionaria Certificada'),
        ('estados_financieros_comparativos', 'Estados Financieros Comparativos (2 años)'),
        ('declaracion_renta', 'Declaración de Renta'),
        ('certificacion_comercial_1', 'Certificación Comercial #1'),
        ('certificacion_comercial_2', 'Certificación Comercial #2'),
        
        # Documentos de Stradata
        ('stradata', 'Documento de Stradata'),
        
        # Documentos de Debida Diligencia y Perfil de Riesgo
        ('debida_diligencia_formulario', 'Formulario de Debida Diligencia'),
        ('debida_diligencia_verificacion', 'Lista de Verificación DD'),
        ('debida_diligencia_bienes', 'Declaración de Bienes'),
        ('debida_diligencia_vinculacion', 'Carta de No Vinculación'),
        ('perfil_riesgo_matriz', 'Matriz de Riesgo'),
        ('perfil_riesgo_evaluacion', 'Evaluación Inicial de Riesgo'),
        ('perfil_riesgo_actualizacion', 'Actualización de Perfil'),
        ('perfil_riesgo_calificacion', 'Calificación de Riesgo'),
        ('soporte_referencias', 'Referencias Comerciales'),
        ('soporte_financieros', 'Estados Financieros'),
        ('soporte_certificaciones', 'Certificaciones'),
        ('soporte_licencias', 'Licencias y Permisos'),
        ('evaluacion_informe', 'Informe de Evaluación'),
        ('evaluacion_recomendaciones', 'Recomendaciones'),
        ('evaluacion_mitigacion', 'Plan de Mitigación'),
        ('seguimiento_revision', 'Revisión Periódica'),
        ('seguimiento_actualizacion', 'Actualización de Datos'),
        ('seguimiento_monitoreo', 'Monitoreo Continuo'),
        ('debida_diligencia_otro', 'Otro Documento DD'),
        
        # Tipos existentes
        ('cedula', 'Cédula'),
        ('certificado', 'Certificado'),
        ('otros', 'Otros'),
    ]
    
    tercero = models.ForeignKey(Tercero, on_delete=models.CASCADE, related_name='documentos')
    tipo_documento = models.CharField(max_length=50, choices=TIPOS_DOCUMENTO_VINCULACION)
    archivo = models.FileField(upload_to=get_upload_path)  # Usar función dinámica
    nombre_original = models.CharField(max_length=255, blank=True)
    tamano_archivo = models.PositiveIntegerField(null=True, blank=True)  # en bytes
    fecha_subida = models.DateTimeField(auto_now_add=True)
    es_vigente = models.BooleanField(default=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)  # Para RUT que debe tener vigencia < 30 días
    created_at = models.DateTimeField(default=timezone.now)  # Usar default en lugar de auto_now_add
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento de Tercero"
        verbose_name_plural = "Documentos de Terceros"
        # Remover cualquier índice que referencie 'estado_validacion'
        indexes = [
            models.Index(fields=['tercero', 'tipo_documento']),
            models.Index(fields=['fecha_subida']),
            models.Index(fields=['es_vigente']),
        ]

    def __str__(self):
        return f"{self.tercero.numero_documento} - {self.get_tipo_documento_display()}"

    def save(self, *args, **kwargs):
        if not self.nombre_original and self.archivo:
            self.nombre_original = self.archivo.name
        if not self.tamano_archivo and self.archivo:
            self.tamano_archivo = self.archivo.size
        super().save(*args, **kwargs)

    @property
    def es_imagen(self):
        """Determina si el archivo es una imagen"""
        if self.archivo:
            extension = self.archivo.name.split('.')[-1].lower()
            return extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp']
        return False

    @property
    def es_pdf(self):
        """Determina si el archivo es un PDF"""
        if self.archivo:
            extension = self.archivo.name.split('.')[-1].lower()
            return extension == 'pdf'
        return False

    @property
    def extension(self):
        """Obtiene la extensión del archivo"""
        if self.archivo:
            return self.archivo.name.split('.')[-1].lower()
        return None

    @property
    def tamano_legible(self):
        """Convierte el tamaño en bytes a formato legible"""
        if not self.tamano_archivo:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.tamano_archivo < 1024.0:
                return f"{self.tamano_archivo:.1f} {unit}"
            self.tamano_archivo /= 1024.0
        return f"{self.tamano_archivo:.1f} TB"

class RepresentanteLegal(models.Model):
    tercero = models.ForeignKey(Tercero, on_delete=models.CASCADE, related_name='representantes_legales')
    nombre_completo = models.CharField(max_length=200)
    tipo_identificacion = models.CharField(max_length=50, choices=[
        ('cedula_ciudadania', 'Cédula de Ciudadanía'),
        ('cedula_extranjeria', 'Cédula de Extranjería'),
        ('pasaporte', 'Pasaporte'),
        ('otro', 'Otro')
    ])
    numero_identificacion = models.CharField(max_length=50)
    telefono = models.CharField(max_length=20)
    direccion = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Representante Legal"
        verbose_name_plural = "Representantes Legales"

class ComposicionAccionaria(models.Model):
    tercero = models.ForeignKey(Tercero, on_delete=models.CASCADE, related_name='composicion_accionaria')
    nombre_razon_social = models.CharField(max_length=200)
    tipo_identificacion = models.CharField(max_length=50, choices=[
        ('cedula_ciudadania', 'Cédula de Ciudadanía'),
        ('cedula_extranjeria', 'Cédula de Extranjería'),
        ('nit', 'NIT'),
        ('pasaporte', 'Pasaporte'),
        ('otro', 'Otro')
    ])
    numero_identificacion = models.CharField(max_length=50)
    porcentaje_participacion = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Composición Accionaria"
        verbose_name_plural = "Composiciones Accionarias"

class Accionista(models.Model):
    """
    Modelo específico para accionistas con estructura jerárquica
    """
    tercero = models.ForeignKey(Tercero, on_delete=models.CASCADE, related_name='accionistas')
    
    # ✨ NUEVOS CAMPOS PARA ESTRUCTURA JERÁRQUICA
    empresa_padre = models.CharField(
        max_length=50, 
        blank=True, 
        default='',
        verbose_name='Identificación Empresa Padre',
        help_text='Identificación de la empresa padre (para sub-accionistas)'
    )
    
    nivel = models.IntegerField(
        default=0,
        verbose_name='Nivel Jerárquico',
        help_text='0=principal, 1=sub-accionista, etc.'
    )
    
    padre = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_accionistas',
        verbose_name='Accionista Padre'
    )
    
    # CAMPOS EXISTENTES
    nombre = models.CharField(max_length=200, verbose_name='Nombre/Razón Social')
    
    tipo_identificacion = models.CharField(
        max_length=5, 
        choices=[
            ('CC', 'Cédula de Ciudadanía'),
            ('CE', 'Cédula de Extranjería'),
            ('PP', 'Pasaporte'),
            ('NIT', 'NIT'),
            ('RUT', 'RUT'),
            ('OTRO', 'Otro')  # ✨ Agregamos OTRO para compatibilidad
        ],
        verbose_name='Tipo de Identificación'
    )
    
    numero_identificacion = models.CharField(
        max_length=50,  # ✨ Aumentamos tamaño para IDs más largos
        verbose_name='Número de Identificación'
    )
    
    porcentaje_participacion = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        verbose_name='Porcentaje de Participación'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accionista"
        verbose_name_plural = "Accionistas"
        unique_together = ['tercero', 'numero_identificacion', 'nivel']  # Evitar duplicados por nivel
        indexes = [
            models.Index(fields=['tercero']),
            models.Index(fields=['empresa_padre']),
            models.Index(fields=['padre']),
            models.Index(fields=['nivel']),
        ]
        
    def __str__(self):
        nivel_str = f" (Nivel {self.nivel})" if self.nivel > 0 else ""
        return f"{self.nombre} - {self.porcentaje_participacion}%{nivel_str}"
    
    # ✨ NUEVOS MÉTODOS PARA ESTRUCTURA JERÁRQUICA
    @property
    def es_principal(self):
        """Determina si es un accionista principal (nivel 0)"""
        return self.nivel == 0 and self.padre is None
    
    @property
    def es_sub_accionista(self):
        """Determina si es un sub-accionista (nivel > 0)"""
        return self.nivel > 0 and self.padre is not None
    
    def get_sub_accionistas(self):
        """Retorna todos los sub-accionistas de este accionista"""
        return self.sub_accionistas.all().order_by('nombre')
    
    def get_accionistas_recursivo(self):
        """Retorna estructura jerárquica completa de sub-accionistas"""
        result = []
        for sub in self.get_sub_accionistas():
            sub_data = {
                'accionista': sub,
                'sub_accionistas': sub.get_accionistas_recursivo()
            }
            result.append(sub_data)
        return result
    
    def validar_porcentajes_nivel(self):
        """Valida que la suma de porcentajes del mismo nivel no exceda 100%"""
        from decimal import Decimal
        
        if self.padre:
            # Para sub-accionistas, validar dentro del mismo padre
            hermanos = self.padre.sub_accionistas.exclude(id=self.id)
            total = sum(Decimal(str(h.porcentaje_participacion)) for h in hermanos) + Decimal(str(self.porcentaje_participacion))
        else:
            # Para principales, validar dentro del mismo tercero
            hermanos = self.tercero.accionistas.filter(nivel=0).exclude(id=self.id)
            total = sum(Decimal(str(h.porcentaje_participacion)) for h in hermanos) + Decimal(str(self.porcentaje_participacion))
        
        return total <= Decimal('100')
    
    def clean(self):
        """Validaciones del modelo"""
        from django.core.exceptions import ValidationError
        
        # Validar consistencia de empresa_padre con padre
        if self.padre and self.empresa_padre:
            if self.empresa_padre != self.padre.numero_identificacion:
                raise ValidationError(
                    f"empresa_padre ({self.empresa_padre}) debe coincidir con la identificación del padre ({self.padre.numero_identificacion})"
                )
        
        # Validar nivel
        if self.padre and self.nivel <= self.padre.nivel:
            raise ValidationError("El nivel debe ser mayor al del accionista padre")
        
        # Validar porcentajes
        if not self.validar_porcentajes_nivel():
            raise ValidationError("La suma de porcentajes excede 100% en este nivel")
        
        # Solo validar sub-accionistas si el objeto ya tiene ID (está guardado)
        if self.pk and self.sub_accionistas.exists() and self.tipo_identificacion != 'NIT':
            raise ValidationError("Solo empresas (NIT) pueden tener sub-accionistas")
    
    def save(self, *args, **kwargs):
        """Override del save para aplicar validaciones"""
        # Validaciones que no requieren acceso a sub_accionistas
        self._validate_basic_fields()
        super().save(*args, **kwargs)
        
        # Validaciones post-save
        self._validate_post_save()
    
    def _validate_basic_fields(self):
        """Validaciones básicas que no requieren acceso a relaciones"""
        from django.core.exceptions import ValidationError
        
        # Validar consistencia de empresa_padre con padre
        if self.padre and self.empresa_padre:
            if self.empresa_padre != self.padre.numero_identificacion:
                raise ValidationError(
                    f"empresa_padre ({self.empresa_padre}) debe coincidir con la identificación del padre ({self.padre.numero_identificacion})"
                )
        
        # Validar nivel
        if self.padre and self.nivel <= self.padre.nivel:
            raise ValidationError("El nivel debe ser mayor al del accionista padre")
        
        # Validar porcentajes
        if not self.validar_porcentajes_nivel():
            raise ValidationError("La suma de porcentajes excede 100% en este nivel")
    
    def _validate_post_save(self):
        """Validaciones después de guardar (cuando ya tiene ID)"""
        from django.core.exceptions import ValidationError
        
        # Solo empresas (NIT) pueden tener sub-accionistas
        if self.sub_accionistas.exists() and self.tipo_identificacion != 'NIT':
            raise ValidationError("Solo empresas (NIT) pueden tener sub-accionistas")

class InformacionFinanciera(models.Model):
    tercero = models.OneToOneField(Tercero, on_delete=models.CASCADE, related_name='informacion_financiera')
    ingreso_mensual = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    costos_gastos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    otros_ingresos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_ingresos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    activos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pasivos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    patrimonio = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    detalle_otros_ingresos = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Información Financiera"
        verbose_name_plural = "Informaciones Financieras"


class InformacionPEP(models.Model):
    """
    Modelo ACTUALIZADO para información de Personas Expuestas Políticamente
    Requerido por SARLAFT para cumplimiento legal colombiano
    ESTRUCTURA NUEVA según documentación PEP 2025
    """
    TIPOS_DOCUMENTO = [
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('NIT', 'NIT'),
        ('PASAPORTE', 'Pasaporte')
    ]
    
    tercero = models.ForeignKey(
        Tercero, 
        on_delete=models.CASCADE, 
        related_name='informacion_pep_nueva',
        verbose_name='Tercero'
    )
    
    # Campos mantenidos de la estructura anterior
    nombre = models.CharField(
        max_length=255, 
        verbose_name='Nombre Completo',
        help_text='Nombres y apellidos completos de la persona PEP'
    )
    tipo = models.CharField(
        max_length=15, 
        choices=TIPOS_DOCUMENTO, 
        verbose_name='Tipo de Documento',
        help_text='Tipo de documento de identificación'
    )
    numero_identificacion = models.CharField(
        max_length=50, 
        verbose_name='Número de Identificación',
        help_text='Número de documento de identidad de la persona PEP'
    )
    
    # NUEVOS CAMPOS según estructura actualizada
    cargo = models.CharField(
        max_length=255,
        default='No especificado',
        verbose_name='Cargo',
        help_text='Cargo o posición que desempeña la persona PEP'
    )
    parentesco = models.CharField(
        max_length=255,
        default='No especificado',
        verbose_name='Parentesco',
        help_text='Relación de parentesco con el tercero (Cónyuge, Hijo, Padre, Socio, etc.)'
    )
    fecha_vinculacion = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Vinculación',
        help_text='Fecha de inicio en el cargo (YYYY-MM-DD)'
    )
    fecha_retiro = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Retiro',
        help_text='Fecha de retiro del cargo (YYYY-MM-DD)'
    )
    cuentas_financieras_exterior = models.BooleanField(
        default=False,
        verbose_name='Cuentas Financieras en el Exterior',
        help_text='¿Posee o tiene poder sobre cuentas financieras en el exterior?'
    )
    
    # CAMPOS LEGACY - Mantener temporalmente para migración
    patrimonio_fiducia = models.BooleanField(
        default=False,
        verbose_name='Patrimonio en Fiducia (LEGACY)',
        help_text='CAMPO LEGACY - Será migrado a cuentas_financieras_exterior'
    )
    relaciones_comerciales = models.BooleanField(
        default=False,
        verbose_name='Relaciones Comerciales (LEGACY)',
        help_text='CAMPO LEGACY - Información manejada ahora con cargo y parentesco'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Información PEP"
        verbose_name_plural = "Información PEP"
        indexes = [
            models.Index(fields=['tercero', 'tipo']),
            models.Index(fields=['numero_identificacion']),
            models.Index(fields=['fecha_vinculacion']),
            models.Index(fields=['fecha_retiro']),
        ]
        
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # Validar que fecha_retiro sea posterior a fecha_vinculacion
        if self.fecha_vinculacion and self.fecha_retiro:
            if self.fecha_retiro <= self.fecha_vinculacion:
                raise ValidationError(
                    'La fecha de retiro debe ser posterior a la fecha de vinculación'
                )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.nombre} - {self.cargo} ({self.get_tipo_display()}) - {self.tercero}"


class RevisionCumplimiento(models.Model):
    """
    Modelo para registrar revisiones de cumplimiento SARLAFT
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name='ID'
    )
    tercero = models.ForeignKey(
        Tercero,
        on_delete=models.CASCADE,
        related_name='revisiones_cumplimiento',
        verbose_name='Tercero'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='revisiones_realizadas',
        verbose_name='Usuario que revisó'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Comentarios y observaciones de la revisión'
    )
    aprobado = models.BooleanField(
        default=False,
        verbose_name='Aprobado por cumplimiento'
    )
    nivel_riesgo = models.CharField(
        max_length=20,
        choices=[
            ('bajo', 'Riesgo Bajo'),
            ('medio', 'Riesgo Medio'),
            ('alto', 'Riesgo Alto')
        ],
        default='bajo',
        verbose_name='Nivel de Riesgo'
    )
    requiere_monitoreo = models.BooleanField(
        default=False,
        verbose_name='Requiere Monitoreo Continuo'
    )
    fecha_revision = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Revisión'
    )
    
    class Meta:
        verbose_name = "Revisión de Cumplimiento"
        verbose_name_plural = "Revisiones de Cumplimiento"
        ordering = ['-fecha_revision']
        indexes = [
            models.Index(fields=['tercero', 'fecha_revision']),
            models.Index(fields=['usuario', 'fecha_revision']),
            models.Index(fields=['nivel_riesgo']),
        ]
    
    def __str__(self):
        return f"Revisión {self.tercero} - {self.usuario.get_full_name()} - {self.get_nivel_riesgo_display()}"


class HistorialEstado(models.Model):
    """
    Modelo para registrar cambios de estado de terceros
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name='ID'
    )
    tercero = models.ForeignKey(
        Tercero,
        on_delete=models.CASCADE,
        related_name='historial_estados',
        verbose_name='Tercero'
    )
    estado_anterior = models.CharField(
        max_length=50,
        verbose_name='Estado Anterior'
    )
    estado_nuevo = models.CharField(
        max_length=50,
        verbose_name='Estado Nuevo'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cambios_estado_realizados',
        verbose_name='Usuario que cambió el estado'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones del cambio'
    )
    fecha_cambio = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha del cambio'
    )
    
    class Meta:
        verbose_name = "Historial de Estado"
        verbose_name_plural = "Historiales de Estado"
        ordering = ['-fecha_cambio']
        indexes = [
            models.Index(fields=['tercero', 'fecha_cambio']),
            models.Index(fields=['usuario', 'fecha_cambio']),
            models.Index(fields=['estado_nuevo']),
        ]
    
    def __str__(self):
        return f"{self.tercero} - {self.estado_anterior} → {self.estado_nuevo} por {self.usuario.get_full_name()}"


class ActividadAdministrativa(models.Model):
    """
    Modelo para registrar actividades administrativas del sistema
    """
    TIPOS_ACTIVIDAD = [
        ('usuario_creado', 'Usuario Creado'),
        ('usuario_modificado', 'Usuario Modificado'),
        ('usuario_desactivado', 'Usuario Desactivado'),
        ('tercero_reasignado', 'Tercero Reasignado'),
        ('configuracion_sistema', 'Configuración del Sistema'),
        ('backup_realizado', 'Backup Realizado'),
        ('mantenimiento', 'Mantenimiento del Sistema'),
        ('auditoria', 'Auditoría del Sistema'),
        ('redistribucion', 'Redistribución de Carga'),
        ('otros', 'Otros')
    ]
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name='ID'
    )
    tipo_actividad = models.CharField(
        max_length=50,
        choices=TIPOS_ACTIVIDAD,
        verbose_name='Tipo de Actividad'
    )
    usuario_administrador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='actividades_administrativas',
        verbose_name='Administrador'
    )
    descripcion = models.TextField(
        verbose_name='Descripción de la actividad'
    )
    datos_adicionales = models.JSONField(
        blank=True,
        null=True,
        verbose_name='Datos adicionales',
        help_text='Información adicional en formato JSON'
    )
    usuario_afectado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_recibidas',
        verbose_name='Usuario Afectado'
    )
    tercero_afectado = models.ForeignKey(
        Tercero,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_administrativas',
        verbose_name='Tercero Afectado'
    )
    fecha_actividad = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de la Actividad'
    )
    
    class Meta:
        verbose_name = "Actividad Administrativa"
        verbose_name_plural = "Actividades Administrativas"
        ordering = ['-fecha_actividad']
        indexes = [
            models.Index(fields=['usuario_administrador', 'fecha_actividad']),
            models.Index(fields=['tipo_actividad', 'fecha_actividad']),
            models.Index(fields=['usuario_afectado']),
            models.Index(fields=['tercero_afectado']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_actividad_display()} - {self.usuario_administrador.get_full_name()} - {self.fecha_actividad.strftime('%Y-%m-%d')}"
