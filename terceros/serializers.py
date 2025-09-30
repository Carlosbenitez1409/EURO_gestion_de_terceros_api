from rest_framework import serializers
from .models import Tercero, DocumentoTercero, TipoDocumento, RepresentanteLegal, ComposicionAccionaria, InformacionFinanciera, Accionista, InformacionPEP, HistorialTercero
from rest_framework import viewsets
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class TipoDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoDocumento
        fields = ['id', 'nombre', 'descripcion', 'es_obligatorio', 'activo', 'orden']

class DocumentoTerceroSerializer(serializers.ModelSerializer):
    extension = serializers.ReadOnlyField()
    es_imagen = serializers.ReadOnlyField()
    es_pdf = serializers.ReadOnlyField()
    tamano_legible = serializers.ReadOnlyField()
    
    class Meta:
        model = DocumentoTercero
        fields = [
            'id', 'tercero', 'tipo_documento', 'archivo', 'nombre_original',
            'tamano_archivo', 'fecha_subida', 'es_vigente', 'fecha_vencimiento',
            'extension', 'es_imagen', 'es_pdf', 'tamano_legible',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'fecha_subida', 'created_at', 'updated_at')

    def validate_archivo(self, value):
        """Validar archivo subido"""
        # Validar tamaño máximo (5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("El archivo no puede ser mayor a 5MB")
        
        # Validar extensión
        extension = value.name.split('.')[-1].lower()
        extensiones_permitidas = ['pdf', 'png', 'jpg', 'jpeg']
        if extension not in extensiones_permitidas:
            raise serializers.ValidationError(
                f"Extensión no permitida. Solo se permiten: {', '.join(extensiones_permitidas)}"
            )
        
        return value

    def validate_fecha_vencimiento(self, value):
        """Validar fecha de vencimiento"""
        if value and value < timezone.now().date():
            raise serializers.ValidationError("La fecha de vencimiento no puede ser anterior a hoy")
        return value

    def validate_tipo_documento(self, value):
        """Validar que el tipo de documento sea válido"""
        tipos_validos = [choice[0] for choice in DocumentoTercero.TIPOS_DOCUMENTO_VINCULACION]
        if value not in tipos_validos:
            raise serializers.ValidationError(f"Tipo de documento inválido. Opciones válidas: {tipos_validos}")
        return value

class DocumentoTerceroViewSet(viewsets.ModelViewSet):
    queryset = DocumentoTercero.objects.all()
    serializer_class = DocumentoTerceroSerializer

class TerceroConDocumentosSerializer(serializers.ModelSerializer):
    """
    Serializer de tercero que incluye información de documentos
    """
    documentos = serializers.SerializerMethodField()
    
    class Meta:
        model = Tercero
        fields = [
            'id', 'tipo_documento', 'numero_documento', 'tipo_persona',
            'nombres', 'apellidos', 'razon_social', 'email', 'telefono',
            'direccion', 'ciudad', 'departamento',
            'estado_aprobacion', 'observaciones', 'created_at', 'updated_at',
            'creado_por', 'aprobado_por', 'documentos',
            # Campos del formulario frontend
            'responsableIVA', 'correoFacturacion', 'granContribuyente', 'numeroResolucionGC', 
            'fechaResolucionGC', 'numeroResolucionAutorretenedor', 'fechaResolucionAutorretenedor',
            'exentoRenta', 'condicionesExentoRenta', 
            # Campos financieros correctos (DecimalField)
            'ingreso_mensual', 'costos_gastos_mensuales', 'otros_ingresos', 'total_ingresos', 
            'activos', 'pasivos', 'patrimonio', 'detalle_otros_ingresos',
            'operacionesMonedaExtranjera',
            'tiposOperacionesMonedaExtranjera', 'manejoAltoEfectivo', 'autorizacionTratamientoDatos',
            'personaExpuestaPolitica', 'detallesPEP', 'origenFondos', 'fuentesFondos', 
            'tiposRecursos', 'constituyePatrimoniosAutonomos', 'declaracionTransparencia',
            'representantes', 'accionistas_frontend'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'creado_por', 
            'aprobado_por', 'documentos'
        ]
    
    def get_documentos(self, obj):
        """
        Obtener información resumida de documentos asociados
        """
        # Usar el related_name correcto
        documentos = obj.documentos.all()  # El related_name es 'documentos'
        return [{
            'id': str(doc.id),
            'tipo_documento': doc.tipo_documento,
            'nombre_original': doc.nombre_original,
            'es_vigente': doc.es_vigente,
            'fecha_subida': doc.fecha_subida,
            'tamano_legible': doc.tamano_legible
        } for doc in documentos]


class TerceroCompletoPEPSerializer(serializers.ModelSerializer):
    """
    Serializer COMPLETO que incluye información PEP anidada
    Para validación completa SARLAFT/PEP
    """
    documentos = serializers.SerializerMethodField()
    informacion_pep = serializers.SerializerMethodField()
    
    class Meta:
        model = Tercero
        fields = [
            'id', 'tipo_documento', 'numero_documento', 'tipo_persona',
            'nombres', 'apellidos', 'razon_social', 'email', 'telefono',
            'direccion', 'ciudad', 'departamento',
            'estado_aprobacion', 'observaciones', 'created_at', 'updated_at',
            'creado_por', 'aprobado_por', 'documentos', 'informacion_pep',
            # Campos del formulario frontend COMPLETOS
            'responsableIVA', 'correoFacturacion', 'granContribuyente', 'numeroResolucionGC', 
            'fechaResolucionGC', 'numeroResolucionAutorretenedor', 'fechaResolucionAutorretenedor',
            'exentoRenta', 'condicionesExentoRenta', 
            # Campos financieros correctos (DecimalField)
            'ingreso_mensual', 'costos_gastos_mensuales', 'otros_ingresos', 'total_ingresos', 
            'activos', 'pasivos', 'patrimonio', 'detalle_otros_ingresos',
            'operacionesMonedaExtranjera',
            'tiposOperacionesMonedaExtranjera', 'manejoAltoEfectivo', 'autorizacionTratamientoDatos',
            'personaExpuestaPolitica', 'detallesPEP', 'origenFondos', 'fuentesFondos', 
            'tiposRecursos', 'constituyePatrimoniosAutonomos', 'declaracionTransparencia',
            'representantes', 'accionistas_frontend'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'creado_por', 
            'aprobado_por', 'documentos', 'informacion_pep'
        ]
        
    def get_documentos(self, obj):
        """Obtener documentos asociados"""
        documentos = obj.documentos.all()
        return [{
            'id': str(doc.id),
            'tipo_documento': doc.tipo_documento,
            'archivo': doc.archivo.url if doc.archivo else None,
            'nombre_original': doc.nombre_original,
            'created_at': doc.created_at.isoformat() if doc.created_at else None
        } for doc in documentos]
    
    def get_informacion_pep(self, obj):
        """Obtener información PEP asociada"""
        import logging
        logger = logging.getLogger('euro_terceros')
        
        # Usar la relación correcta del modelo
        pep_info = obj.informacion_pep_nueva.all()
        logger.info(f"🔍 SERIALIZER - Tercero ID: {obj.id}")
        logger.info(f"🔍 SERIALIZER - pep_info.count(): {pep_info.count()}")
        
        if pep_info.exists():
            logger.info(f"✅ SERIALIZER - Serializando {pep_info.count()} registros PEP")
            data = InformacionPEPSerializer(pep_info, many=True).data
            logger.info(f"✅ SERIALIZER - Datos PEP serializados: {data}")
            return data
        else:
            logger.warning(f"⚠️ SERIALIZER - No se encontraron registros PEP para tercero {obj.id}")
        return []
    
    def validate(self, data):
        """
        Validaciones críticas SARLAFT/PEP
        """
        errors = {}
        
        # Validación PEP obligatoria
        if data.get('personaExpuestaPolitica') is True:
            if not data.get('detallesPEP'):
                errors['detallesPEP'] = 'Si es PEP, debe proporcionar detalles'
        
        # Validaciones de declaraciones obligatorias
        if data.get('constituyePatrimoniosAutonomos') is None:
            errors['constituyePatrimoniosAutonomos'] = 'Declaración obligatoria para cumplimiento SARLAFT'
            
        if data.get('declaracionTransparencia') is None:
            errors['declaracionTransparencia'] = 'Declaración obligatoria para cumplimiento SARLAFT'
            
        if data.get('manejoAltoEfectivo') is None:
            errors['manejoAltoEfectivo'] = 'Declaración obligatoria para cumplimiento SARLAFT'
            
        if data.get('autorizacionTratamientoDatos') is None:
            errors['autorizacionTratamientoDatos'] = 'Autorización obligatoria para tratamiento de datos'
        
        # Correo facturación obligatorio
        if not data.get('correoFacturacion'):
            errors['correoFacturacion'] = 'Correo de facturación es obligatorio para todos los terceros'
        
        if errors:
            raise serializers.ValidationError(errors)
            
        return data


class TerceroPublicRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer específico para registro público de terceros
    Con validaciones adicionales de seguridad
    """
    
    # Hacer campos obligatorios explícitamente
    nombre_persona_contacto = serializers.CharField(max_length=255, required=True)
    cargo_persona_contacto = serializers.CharField(max_length=255, required=True)
    
    class Meta:
        model = Tercero
        fields = [
            'tipo_formulario', 'tipo_documento', 'numero_documento', 'tipo_persona',
            'nombres', 'apellidos', 'razon_social', 'email', 'telefono',
            'direccion', 'ciudad', 'departamento',
            # Nuevos campos de contacto separados
            'nombre_persona_contacto', 'cargo_persona_contacto',
            # Nuevos campos de activos virtuales
            'manejo_activos_virtuales', 'detalle_activos_virtuales'
        ]
    
    def validate_email(self, value):
        """
        Validación adicional de email para registro público
        """
        if not value:
            raise serializers.ValidationError("El email es requerido para registro público.")
        
        # Verificar que no haya otro tercero con el mismo email
        if Tercero.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Ya existe un registro con este email. Si ya se registró anteriormente, "
                "su solicitud está en proceso de revisión."
            )
        return value
    
    def validate_numero_documento(self, value):
        """
        Validación específica para registro público
        """
        if Tercero.objects.filter(numero_documento=value).exists():
            existing_tercero = Tercero.objects.get(numero_documento=value)
            if existing_tercero.estado_aprobacion == 'pendiente':
                raise serializers.ValidationError(
                    "Su solicitud ya está registrada y en proceso de revisión. "
                    "Recibirá una notificación cuando sea aprobada."
                )
            else:
                raise serializers.ValidationError(
                    "Ya existe un registro con este número de documento."
                )
        return value
    
    def validate_nombre_persona_contacto(self, value):
        """
        Validación del nombre de persona de contacto
        """
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre de la persona de contacto es obligatorio.")
        return value.strip()
    
    def validate_cargo_persona_contacto(self, value):
        """
        Validación del cargo de persona de contacto
        """
        if not value or not value.strip():
            raise serializers.ValidationError("El cargo de la persona de contacto es obligatorio.")
        return value.strip()
    
    def validate_tipo_documento(self, value):
        """
        Validación del tipo de documento según tipo de persona
        """
        # Obtener tipo_persona del contexto (si está siendo validado en conjunto)
        tipo_persona = self.initial_data.get('tipo_persona')
        
        if tipo_persona in ['juridica', 'publica']:
            if value != 'NIT':
                raise serializers.ValidationError(
                    "Las personas jurídicas y públicas deben usar únicamente NIT como tipo de documento."
                )
        
        return value
    
    def validate(self, data):
        """
        Validaciones generales que requieren múltiples campos
        """
        # Validar tipo documento para jurídicas
        if data.get('tipo_persona') in ['juridica', 'publica']:
            if data.get('tipo_documento') != 'NIT':
                raise serializers.ValidationError({
                    'tipo_documento': 'Las personas jurídicas y públicas deben usar únicamente NIT.'
                })
        
        # Validar activos virtuales condicionales
        if data.get('manejo_activos_virtuales'):
            if not data.get('detalle_activos_virtuales', '').strip():
                raise serializers.ValidationError({
                    'detalle_activos_virtuales': 'Debe especificar el detalle de activos virtuales cuando indica que los maneja.'
                })
        
        return data

    def create(self, validated_data):
        """
        Crear tercero con configuraciones específicas para registro público
        """
        # Determinar estado inicial basado en tipo_formulario
        tipo_formulario = validated_data.get('tipo_formulario', 'vinculacion')
        estado_inicial = 'asignada_administrador' if tipo_formulario == 'actualizacion' else 'pendiente'
        validated_data['estado_aprobacion'] = estado_inicial
        
        # Configurar flag para validar campos de registro
        tercero = Tercero(**validated_data)
        tercero._validar_campos_registro = True
        tercero.full_clean()  # Ejecutar validaciones del modelo
        tercero.save()
        
        logger.info(
            f"Public registration created: {tercero.numero_documento} - "
            f"{tercero.nombres} {tercero.apellidos or tercero.razon_social} - "
            f"Tipo: {tercero.tipo_formulario} - Estado: {tercero.estado_aprobacion} - "
            f"Contacto: {tercero.nombre_persona_contacto} ({tercero.cargo_persona_contacto}) - "
            f"Activos virtuales: {tercero.manejo_activos_virtuales}"
        )
        
        return tercero


class InformacionPEPSerializer(serializers.ModelSerializer):
    """
    Serializer CRÍTICO ACTUALIZADO para información de Personas Expuestas Políticamente
    Requerido por SARLAFT para cumplimiento legal colombiano
    ESTRUCTURA NUEVA según documentación PEP 2025
    """
    # Campo calculado para verificar si es estructura legacy
    es_estructura_legacy = serializers.SerializerMethodField()
    
    class Meta:
        model = InformacionPEP
        fields = [
            'id', 'tercero', 'nombre', 'tipo', 'numero_identificacion',
            # NUEVOS CAMPOS ESTRUCTURA ACTUALIZADA
            'cargo', 'parentesco', 'fecha_vinculacion', 'fecha_retiro', 
            'cuentas_financieras_exterior',
            # CAMPOS LEGACY (mantener por migración)
            'patrimonio_fiducia', 'relaciones_comerciales',
            'es_estructura_legacy', 'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'es_estructura_legacy')
    
    def get_es_estructura_legacy(self, obj):
        """Identifica si es un registro con estructura legacy"""
        return (
            not obj.cargo or 
            not obj.parentesco or 
            not obj.fecha_vinculacion or 
            not obj.fecha_retiro
        )
    
    def validate_numero_identificacion(self, value):
        """Validar formato del número de identificación"""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                "El número de identificación debe tener al menos 5 caracteres"
            )
        return value.strip()
    
    def validate_nombre(self, value):
        """Validar que el nombre esté completo"""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                "El nombre completo debe tener al menos 5 caracteres"
            )
        return value.strip()
    
    def validate_cargo(self, value):
        """Validar campo cargo"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "El cargo debe tener al menos 3 caracteres"
            )
        return value.strip()
    
    def validate_parentesco(self, value):
        """Validar campo parentesco"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "El parentesco debe tener al menos 3 caracteres"
            )
        return value.strip()
    
    def validate(self, data):
        """Validación global del serializador"""
        # Validar fechas
        fecha_vinculacion = data.get('fecha_vinculacion')
        fecha_retiro = data.get('fecha_retiro')
        
        if fecha_vinculacion and fecha_retiro:
            if fecha_retiro <= fecha_vinculacion:
                raise serializers.ValidationError({
                    'fecha_retiro': 'La fecha de retiro debe ser posterior a la fecha de vinculación'
                })
        
        return data
    
    def to_representation(self, instance):
        """Customizar representación para frontend"""
        representation = super().to_representation(instance)
        
        # Añadir información adicional para el frontend
        representation['resumen'] = {
            'nombre_cargo': f"{instance.nombre} - {instance.cargo or 'No especificado'}",
            'relacion': instance.parentesco or 'No especificado',
            'periodo': f"{instance.fecha_vinculacion or 'N/A'} - {instance.fecha_retiro or 'N/A'}",
            'riesgo_exterior': instance.cuentas_financieras_exterior,
            'estructura_actualizada': not self.get_es_estructura_legacy(instance)
        }
        
        return representation


class TerceroSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Tercero
    """
    asignado_a_nombre = serializers.CharField(source='asignado_a.get_full_name', read_only=True)
    asignado_a_email = serializers.CharField(source='asignado_a.email', read_only=True)
    asignado_a_procesos_nombre = serializers.CharField(source='asignado_a_procesos.get_full_name', read_only=True)
    asignado_a_procesos_email = serializers.CharField(source='asignado_a_procesos.email', read_only=True)
    
    # Campos adicionales para compatibilidad con frontend
    asignado_comercial = serializers.SerializerMethodField()
    asignado_procesos = serializers.SerializerMethodField()
    
    # Campos del nuevo flujo centralizado
    usuario_asignado_nombre = serializers.CharField(source='usuario_asignado.get_full_name', read_only=True)
    usuario_asignado_email = serializers.CharField(source='usuario_asignado.email', read_only=True)
    rol_asignado_display = serializers.CharField(source='get_rol_asignado_display', read_only=True)
    
    class Meta:
        model = Tercero
        fields = [
            'id', 'tipo_formulario', 'tipo_documento', 'numero_documento', 'tipo_persona',
            'nombres', 'apellidos', 'razon_social', 'email', 'telefono',
            'direccion', 'ciudad', 'departamento',
            'estado_aprobacion', 'observaciones', 'created_at', 'updated_at',
            'creado_por', 'aprobado_por', 'asignado_a', 'asignado_a_nombre', 'asignado_a_email',
            'asignado_a_procesos', 'asignado_a_procesos_nombre', 'asignado_a_procesos_email',
            'fecha_asignacion_procesos',
            # Campos adicionales para compatibilidad con frontend
            'asignado_comercial', 'asignado_procesos',
            # Campos del nuevo flujo centralizado
            'usuario_asignado', 'usuario_asignado_nombre', 'usuario_asignado_email',
            'rol_asignado', 'rol_asignado_display', 'fecha_asignacion_actual',
            # Campos del formulario frontend
            'responsableIVA', 'correoFacturacion', 'granContribuyente', 'numeroResolucionGC', 
            'fechaResolucionGC', 'numeroResolucionAutorretenedor', 'fechaResolucionAutorretenedor',
            'exentoRenta', 'condicionesExentoRenta', 
            # Campos financieros correctos (DecimalField)
            'ingreso_mensual', 'costos_gastos_mensuales', 'otros_ingresos', 'total_ingresos', 
            'activos', 'pasivos', 'patrimonio', 'detalle_otros_ingresos',
            'operacionesMonedaExtranjera',
            'tiposOperacionesMonedaExtranjera', 'manejoAltoEfectivo', 'autorizacionTratamientoDatos',
            'personaExpuestaPolitica', 'detallesPEP', 'origenFondos', 'fuentesFondos', 
            'tiposRecursos', 'constituyePatrimoniosAutonomos', 'declaracionTransparencia',
            'representantes', 'accionistas_frontend',
            # Campos específicos para comerciales
            'observaciones_comercial', 'comentarios_aprobacion', 'notas_internas',
            'fecha_contacto_inicial', 'canal_contacto', 'prioridad_comercial',
            # Campos del Perfil Comercial - Condiciones de Pago
            'condiciones_pago_8_dias', 'condiciones_pago_15_dias', 'condiciones_pago_30_dias',
            'condiciones_pago_45_dias', 'condiciones_pago_60_dias', 'condiciones_pago_otro',
            'condiciones_pago_otro_valor', 'otras_condiciones_pago',
            'condiciones_pago_establecidas_por', 'fecha_establecimiento_condiciones'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'creado_por', 
            'aprobado_por', 'asignado_a', 'asignado_a_nombre', 'asignado_a_email',
            'asignado_a_procesos_nombre', 'asignado_a_procesos_email', 'fecha_asignacion_procesos',
            'asignado_comercial', 'asignado_procesos'
        ]
        
    def validate_numero_documento(self, value):
        """
        Validar que el número de documento no esté duplicado
        """
        if self.instance:
            # Si estamos editando, excluir el registro actual
            if Tercero.objects.filter(numero_documento=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    "Ya existe un tercero con este número de documento."
                )
        else:
            # Si estamos creando, verificar que no exista
            if Tercero.objects.filter(numero_documento=value).exists():
                raise serializers.ValidationError(
                    "Ya existe un tercero con este número de documento."
                )
        return value
    
    def get_asignado_comercial(self, obj):
        """Obtener ID del comercial asignado"""
        return obj.asignado_a_id if obj.asignado_a else None
    
    def get_asignado_procesos(self, obj):
        """Obtener ID del usuario asignado a procesos"""
        return obj.asignado_a_procesos_id if obj.asignado_a_procesos else None
    
    def to_internal_value(self, data):
        """
        Mapeo automático de campos camelCase (frontend) a snake_case (backend)
        """
        # Mapeo completo de campos
        field_mapping = {
            # Campos financieros
            'ingresoMensual': 'ingreso_mensual',
            'costosGastos': 'costos_gastos_mensuales', 
            'otrosIngresos': 'otros_ingresos',
            'totalIngresos': 'total_ingresos',
            'detalleOtrosIngresos': 'detalle_otros_ingresos',
            
            # Campos booleanos (campos reales del modelo)
            'personaExpuestaPolitica': 'personaExpuestaPolitica',
            'responsableIVA': 'responsableIVA', 
            'granContribuyente': 'granContribuyente',
            'manejoAltoEfectivo': 'manejoAltoEfectivo',
            'autorizacionTratamientoDatos': 'autorizacionTratamientoDatos',
            
            # Campos de observaciones (mapeo real)
            'observaciones': 'observaciones',
            'observacionesAdicionales': 'observaciones_adicionales',
            'observacionesComercial': 'observaciones_comercial',
            'observacionesProcesos': 'observaciones_procesos',
            'observacionesCumplimiento': 'observaciones_cumplimiento',
            
            # Campos del perfil comercial (campos reales)
            'condicionesPago8Dias': 'condiciones_pago_8_dias',
            'condicionesPago15Dias': 'condiciones_pago_15_dias',
            'condicionesPago30Dias': 'condiciones_pago_30_dias',
            'condicionesPago45Dias': 'condiciones_pago_45_dias',
            'condicionesPago60Dias': 'condiciones_pago_60_dias',
            'condicionesPagoOtro': 'condiciones_pago_otro',
            'condicionesPagoOtroValor': 'condiciones_pago_otro_valor',
            'otrasCondicionesPago': 'otras_condiciones_pago',
        }
        
        # Aplicar mapeo si los campos camelCase están presentes
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        
        for camel_case, snake_case in field_mapping.items():
            if camel_case in data_copy:
                # Transferir valor del campo camelCase al snake_case
                data_copy[snake_case] = data_copy.pop(camel_case)
                
        return super().to_internal_value(data_copy)
    
    def validate(self, attrs):
        """
        Validaciones a nivel de objeto
        """
        tipo_persona = attrs.get('tipo_persona')
        
        # Si es persona natural, requiere nombres y apellidos
        if tipo_persona == 'natural':
            if not attrs.get('nombres'):
                raise serializers.ValidationError({
                    'nombres': 'Los nombres son obligatorios para personas naturales.'
                })
            if not attrs.get('apellidos'):
                raise serializers.ValidationError({
                    'apellidos': 'Los apellidos son obligatorios para personas naturales.'
                })
        
        # Si es persona jurídica, requiere razón social
        elif tipo_persona == 'juridica':
            if not attrs.get('razon_social'):
                raise serializers.ValidationError({
                    'razon_social': 'La razón social es obligatoria para personas jurídicas.'
                })
        
        return attrs
    
    def create(self, validated_data):
        """
        Crear tercero con manejo especial de campos JSON del frontend
        """
        import json
        
        # Procesar arrays que pueden venir como strings
        json_fields = ['tiposOperacionesMonedaExtranjera', 'tiposRecursos', 'representantes', 'accionistas_frontend']
        
        for field in json_fields:
            if field in validated_data and isinstance(validated_data[field], str):
                try:
                    validated_data[field] = json.loads(validated_data[field])
                except (json.JSONDecodeError, ValueError):
                    # Si no es JSON válido, mantener como lista vacía
                    validated_data[field] = []
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """
        Actualizar tercero con manejo especial de campos JSON del frontend
        """
        import json
        
        # Procesar arrays que pueden venir como strings
        json_fields = ['tiposOperacionesMonedaExtranjera', 'tiposRecursos', 'representantes', 'accionistas_frontend']
        
        for field in json_fields:
            if field in validated_data and isinstance(validated_data[field], str):
                try:
                    validated_data[field] = json.loads(validated_data[field])
                except (json.JSONDecodeError, ValueError):
                    # Si no es JSON válido, mantener como lista vacía
                    validated_data[field] = []
        
        return super().update(instance, validated_data)


class TerceroListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar terceros
    """
    nombre_completo = serializers.SerializerMethodField()
    asignado_a_nombre = serializers.CharField(source='asignado_a.get_full_name', read_only=True)
    asignado_a_procesos_nombre = serializers.CharField(source='asignado_a_procesos.get_full_name', read_only=True)
    
    # Campos adicionales para compatibilidad con frontend
    asignado_comercial = serializers.SerializerMethodField()
    asignado_procesos = serializers.SerializerMethodField()
    
    class Meta:
        model = Tercero
        fields = [
            'id', 'numero_documento', 'nombre_completo', 'email',
            'telefono', 'estado_aprobacion', 'created_at', 'asignado_a_nombre',
            'asignado_a_procesos_nombre', 'fecha_asignacion_procesos',
            # Campos adicionales para compatibilidad con frontend
            'asignado_comercial', 'asignado_procesos'
        ]
    
    def get_nombre_completo(self, obj):
        """
        Retorna el nombre completo según el tipo de persona
        """
        if obj.tipo_persona == 'natural':
            return f"{obj.nombres} {obj.apellidos or ''}".strip()
        else:
            return obj.razon_social or obj.nombres
    
    def get_asignado_comercial(self, obj):
        """Obtener ID del comercial asignado"""
        return obj.asignado_a_id if obj.asignado_a else None
    
    def get_asignado_procesos(self, obj):
        """Obtener ID del usuario asignado a procesos"""
        return obj.asignado_a_procesos_id if obj.asignado_a_procesos else None


class TerceroStatsSerializer(serializers.Serializer):
    """
    Serializer para estadísticas de terceros
    """
    total_terceros = serializers.IntegerField()
    pendientes_aprobacion = serializers.IntegerField()
    en_revision = serializers.IntegerField()
    aprobados = serializers.IntegerField()
    rechazados = serializers.IntegerField()
    requiere_ajustes = serializers.IntegerField()
    por_tipo_persona = serializers.DictField()
    por_tipo_documento = serializers.DictField()
    creados_este_mes = serializers.IntegerField()
    aprobados_este_mes = serializers.IntegerField()

class RepresentanteLegalSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepresentanteLegal
        fields = '__all__'
        read_only_fields = ('id', 'tercero', 'created_at', 'updated_at')

class ComposicionAccionariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComposicionAccionaria
        fields = '__all__'
        read_only_fields = ('id', 'tercero', 'created_at', 'updated_at')

class InformacionFinancieraSerializer(serializers.ModelSerializer):
    class Meta:
        model = InformacionFinanciera
        fields = '__all__'
        read_only_fields = ('id', 'tercero', 'created_at', 'updated_at')

class AccionistaSerializer(serializers.ModelSerializer):
    """
    Serializer para Accionista con estructura jerárquica
    """
    # ✨ NUEVOS CAMPOS PARA ESTRUCTURA JERÁRQUICA
    sub_accionistas = serializers.SerializerMethodField(read_only=True)
    
    # ✨ CAMPOS PARA COMPATIBILIDAD CON FRONTEND
    empresaPadre = serializers.CharField(
        source='empresa_padre',
        max_length=50,
        allow_blank=True,
        default='',
        required=False
    )
    identificacion = serializers.CharField(source='numero_identificacion', max_length=50)
    tipo = serializers.CharField(source='tipo_identificacion', max_length=10)
    porcentaje = serializers.DecimalField(
        source='porcentaje_participacion',
        max_digits=5,
        decimal_places=2,
        min_value=0.01,
        max_value=100
    )
    
    class Meta:
        model = Accionista
        fields = [
            'id', 'tercero', 'nombre', 'identificacion', 'tipo', 'porcentaje',
            'empresaPadre', 'nivel', 'padre', 'sub_accionistas',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'tercero', 'created_at', 'updated_at', 'sub_accionistas')
    
    def get_sub_accionistas(self, obj):
        """Obtener sub-accionistas recursivamente"""
        if obj.sub_accionistas.exists():
            return AccionistaSerializer(obj.sub_accionistas.all(), many=True).data
        return []
    
    def validate_porcentaje(self, value):
        """Validar que el porcentaje esté entre 0.01 y 100"""
        if value < 0.01 or value > 100:
            raise serializers.ValidationError("El porcentaje debe estar entre 0.01 y 100")
        return value
    
    def validate(self, attrs):
        """Validaciones a nivel de objeto"""
        # Si tiene empresa_padre, debe tener padre
        empresa_padre = attrs.get('empresa_padre', '')
        padre = attrs.get('padre')
        
        if empresa_padre and not padre:
            raise serializers.ValidationError({
                'empresaPadre': 'Si especifica empresa_padre, debe proporcionar el padre'
            })
        
        # Validar consistencia entre empresa_padre y padre
        if padre and empresa_padre:
            if empresa_padre != padre.numero_identificacion:
                raise serializers.ValidationError({
                    'empresaPadre': f'empresa_padre debe coincidir con la identificación del padre ({padre.numero_identificacion})'
                })
        
        return attrs


# ✨ NUEVOS SERIALIZERS PARA ESTRUCTURA JERÁRQUICA
class AccionistaJerarquicoSerializer(serializers.Serializer):
    """
    Serializer para recibir estructura jerárquica desde frontend
    """
    empresaPadre = serializers.CharField(max_length=50, allow_blank=True, default='', required=False)
    nombre = serializers.CharField(max_length=255)
    identificacion = serializers.CharField(max_length=50)
    tipo = serializers.ChoiceField(choices=['CC', 'CE', 'NIT', 'OTRO'])
    porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0.01, max_value=100)
    subAccionistas = serializers.ListField(
        child=serializers.DictField(),  # Recursivo - se manejará en la validación
        allow_empty=True,
        default=list,
        required=False
    )
    
    def validate_subAccionistas(self, value):
        """Validar sub-accionistas recursivamente"""
        if not value:
            return value
        
        # Validar cada sub-accionista con el mismo serializer
        for i, sub_acc in enumerate(value):
            sub_serializer = AccionistaJerarquicoSerializer(data=sub_acc)
            if not sub_serializer.is_valid():
                raise serializers.ValidationError(f"Sub-accionista {i+1}: {sub_serializer.errors}")
        
        # Validar suma de porcentajes ≤ 100%
        total_porcentaje = sum(float(sub.get('porcentaje', 0)) for sub in value)
        if total_porcentaje > 100:
            raise serializers.ValidationError(f"La suma de porcentajes de sub-accionistas ({total_porcentaje}%) excede 100%")
        
        return value


class AccionistaLegacySerializer(serializers.Serializer):
    """
    Serializer para compatibilidad con estructura legacy
    """
    nombre = serializers.CharField(max_length=255)
    tipoIdentificacion = serializers.CharField(max_length=10)
    numeroIdentificacion = serializers.CharField(max_length=50)
    porcentajeParticipacion = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0.01, max_value=100)


class AccionistasMixedSerializer(serializers.Serializer):
    """
    Serializer para manejar ambas estructuras: nueva y legacy
    """
    # ✨ NUEVA ESTRUCTURA JERÁRQUICA
    accionistas = serializers.ListField(
        child=AccionistaJerarquicoSerializer(),
        allow_empty=True,
        default=list,
        required=False
    )
    
    # 🔄 ESTRUCTURA LEGACY (para compatibilidad)
    accionistas_frontend = serializers.ListField(
        child=AccionistaLegacySerializer(),
        allow_empty=True,
        default=list,
        required=False
    )
    
    def validate(self, attrs):
        """Validar que al menos una estructura esté presente"""
        accionistas = attrs.get('accionistas', [])
        accionistas_frontend = attrs.get('accionistas_frontend', [])
        
        if not accionistas and not accionistas_frontend:
            raise serializers.ValidationError("Debe proporcionar accionistas o accionistas_frontend")
        
        # Si ambas están presentes, priorizar la nueva estructura
        if accionistas and accionistas_frontend:
            attrs['usar_estructura_nueva'] = True
        elif accionistas_frontend:
            attrs['usar_estructura_nueva'] = False
        else:
            attrs['usar_estructura_nueva'] = True
        
        return attrs

class TerceroVinculacionSerializer(serializers.ModelSerializer):
    """
    Serializer completo para vinculación con todas las relaciones anidadas
    """
    representantes_legales = RepresentanteLegalSerializer(many=True, required=False, read_only=True)
    composicion_accionaria = ComposicionAccionariaSerializer(many=True, required=False, read_only=True)
    accionistas = AccionistaSerializer(many=True, required=False, read_only=True)
    informacion_financiera = InformacionFinancieraSerializer(required=False, read_only=True)
    documentos = DocumentoTerceroSerializer(many=True, required=False, read_only=True)
    
    class Meta:
        model = Tercero
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'creado_por', 'aprobado_por', 
            'asignado_a', 'asignado_a_procesos', 'fecha_asignacion_procesos', 'fecha_aprobacion'
        )
    
    def validate_numero_documento(self, value):
        """
        Validar número de documento según tipo
        """
        # Aquí podríamos agregar validaciones específicas por tipo de documento
        return value
    
    def validate_digito_verificacion(self, value):
        """
        Validar dígito de verificación para NIT y RUT
        """
        tipo_documento = self.initial_data.get('tipo_documento')
        if tipo_documento in ['NIT', 'RUT'] and not value:
            raise serializers.ValidationError("El dígito de verificación es obligatorio para NIT y RUT")
        return value
    
    def validate_correo_facturacion_electronica(self, value):
        """
        Validar que el correo de facturación sea obligatorio
        """
        if not value:
            raise serializers.ValidationError("El correo de facturación electrónica es obligatorio")
        return value
    
    def validate_autorizacion_tratamiento_datos(self, value):
        """
        Validar autorización de tratamiento de datos
        """
        if not value:
            raise serializers.ValidationError("La autorización de tratamiento de datos es obligatoria")
        return value
    
    def validate_tipos_recursos(self, value):
        """
        Validar máximo 2 tipos de recursos según PROMPT
        """
        if len(value) > 2:
            raise serializers.ValidationError("Máximo 2 tipos de recursos permitidos")
        return value
    
    def validate(self, data):
        """
        Validaciones complejas entre campos
        """
        # Validar resoluciones de gran contribuyente
        if data.get('gran_contribuyente') and not data.get('numero_resolucion_gc'):
            raise serializers.ValidationError({
                'numero_resolucion_gc': 'El número de resolución es obligatorio para grandes contribuyentes'
            })
        
        # Validar resoluciones de autorretenedor
        if data.get('auto_retenedor') and not data.get('numero_resolucion_autorretenedor'):
            raise serializers.ValidationError({
                'numero_resolucion_autorretenedor': 'El número de resolución es obligatorio para autorretenedores'
            })
        
        # Validar campos obligatorios según tipo de persona
        tipo_persona = data.get('tipo_persona')
        if tipo_persona == 'natural':
            if not data.get('nombres') or not data.get('apellidos'):
                raise serializers.ValidationError("Nombres y apellidos son obligatorios para personas naturales")
        elif tipo_persona == 'juridica':
            if not data.get('razon_social'):
                raise serializers.ValidationError("La razón social es obligatoria para personas jurídicas")
        
        return data

class TerceroCompleteSerializer(serializers.ModelSerializer):
    """
    Serializer completo según especificaciones del PROMPT
    Incluye todos los campos y relaciones anidadas
    """
    informacion_pep = serializers.SerializerMethodField()
    informacionPEP = serializers.SerializerMethodField()  # Para compatibilidad frontend
    accionistas_frontend = serializers.SerializerMethodField()  # Formato legacy
    accionistas = serializers.SerializerMethodField()  # ✨ Nueva estructura jerárquica
    representantes = serializers.SerializerMethodField()
    
    class Meta:
        model = Tercero
        fields = '__all__'  # Usar todos los campos, no excluir nada
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'creado_por', 'aprobado_por', 
            'asignado_a_procesos', 'fecha_asignacion_procesos', 'fecha_aprobacion'
        )
    
    def get_informacion_pep(self, obj):
        """Obtener información PEP asociada"""
        import logging
        logger = logging.getLogger('euro_terceros')
        
        # Usar la relación correcta del modelo
        pep_info = obj.informacion_pep_nueva.all()
        logger.info(f"COMPLETE SERIALIZER - Tercero ID: {obj.id}")
        logger.info(f"COMPLETE SERIALIZER - pep_info.count(): {pep_info.count()}")
        
        if pep_info.exists():
            logger.info(f"COMPLETE SERIALIZER - Serializando {pep_info.count()} registros PEP")
            data = InformacionPEPSerializer(pep_info, many=True).data
            logger.info(f"COMPLETE SERIALIZER - Datos PEP serializados: {data}")
            return data
        else:
            logger.warning(f"COMPLETE SERIALIZER - No se encontraron registros PEP para tercero {obj.id}")
        return []
    
    def get_informacionPEP(self, obj):
        """Obtener información PEP asociada - Alias para compatibilidad frontend"""
        return self.get_informacion_pep(obj)
    
    def get_accionistas_frontend(self, obj):
        """Obtener accionistas asociados en formato legacy (para compatibilidad)"""
        import logging
        logger = logging.getLogger('euro_terceros')
        
        accionistas = obj.accionistas.all().order_by('nivel', 'nombre')
        logger.info(f"COMPLETE SERIALIZER - Accionistas para tercero {obj.id}: {accionistas.count()}")
        
        if accionistas.exists():
            # Generar formato legacy (plano) para compatibilidad
            legacy_data = []
            for accionista in accionistas:
                legacy_data.append({
                    'id': accionista.id,
                    'nombre': accionista.nombre,
                    'tipoIdentificacion': accionista.tipo_identificacion,
                    'numeroIdentificacion': accionista.numero_identificacion,
                    'porcentajeParticipacion': float(accionista.porcentaje_participacion),
                    # Campos adicionales para debugging
                    'nivel': accionista.nivel,
                    'empresaPadre': accionista.empresa_padre
                })
            
            logger.info(f"COMPLETE SERIALIZER - Accionistas legacy serializados: {len(legacy_data)} items")
            return legacy_data
        return []
    
    def get_accionistas(self, obj):
        """Obtener accionistas en estructura jerárquica nueva"""
        from terceros.utils.accionistas_utils import obtener_estructura_jerarquica
        
        try:
            estructura = obtener_estructura_jerarquica(obj)
            return estructura.get('accionistas', [])
        except Exception as e:
            logger = logging.getLogger('euro_terceros')
            logger.error(f"Error obteniendo estructura jerárquica: {str(e)}")
            return []
    
    def get_representantes(self, obj):
        """Obtener representantes legales asociados"""
        import logging
        logger = logging.getLogger('euro_terceros')
        
        representantes = obj.representantes_legales.all()
        logger.info(f"COMPLETE SERIALIZER - Representantes para tercero {obj.id}: {representantes.count()}")
        
        if representantes.exists():
            data = RepresentanteLegalSerializer(representantes, many=True).data
            logger.info(f"COMPLETE SERIALIZER - Representantes serializados: {data}")
            return data
        return []
    
    def create(self, validated_data):
        """
        Crear tercero básico con datos ya validados y convertidos
        """
        # Los datos ya vienen convertidos del método validate()
        # Crear el tercero con los datos básicos
        tercero = Tercero.objects.create(**validated_data)
        return tercero
    
    def to_internal_value(self, data):
        """
        Convertir datos camelCase del frontend a snake_case para el backend
        """
        # Mapear campos del frontend (camelCase) a backend (snake_case)
        field_mapping = {
            'tipoDocumento': 'tipo_documento',
            'numeroDocumento': 'numero_documento', 
            'tipoPersona': 'tipo_persona',
            'digitoVerificacion': 'digito_verificacion',
            'nombreRazonSocial': 'razon_social',
            'actividadEconomica': 'actividad_economica_principal',
            'codigoCIIU': 'codigo_ciiu',
            'correoElectronico': 'email',
            'responsableIVA': 'responsable_iva',
            'correoFacturacion': 'correo_facturacion_electronica',
            'granContribuyente': 'gran_contribuyente',
            'numeroResolucionGC': 'numero_resolucion_gc',
            'fechaResolucionGC': 'fecha_resolucion_gc',
            'numeroResolucionAutorretenedor': 'numero_resolucion_autorretenedor', 
            'fechaResolucionAutorretenedor': 'fecha_resolucion_autorretenedor',
            'exentoRenta': 'exento_renta',
            'condicionesExentoRenta': 'condiciones_exento_renta',
            'ingresoMensual': 'ingreso_mensual',
            'costosGastos': 'costos_gastos_mensuales',
            'otrosIngresos': 'otros_ingresos',
            'totalIngresos': 'total_ingresos',
            'detalleOtrosIngresos': 'detalle_otros_ingresos',
            'operacionesMonedaExtranjera': 'operaciones_moneda_extranjera',
            'tiposOperacionesMonedaExtranjera': 'tipos_operaciones_extranjera',
            'personaExpuestaPolitica': 'persona_expuesta_politica',
            'detallesPEP': 'detalles_pep',
            'origenFondos': 'origen_fondos',
            'fuentesFondos': 'fuentes_fondos',
            'tiposRecursos': 'tipos_recursos',
            'manejoAltoEfectivo': 'manejo_alto_efectivo',
            'constituyePatrimoniosAutonomos': 'constituye_patrimonios_autonomos',
            'declaracionTransparencia': 'declaracion_transparencia',
            'autorizacionTratamientoDatos': 'autorizacion_tratamiento_datos',
            'patrimonioFiducia': 'patrimonio_fiducia',
            'relacionesComerciales': 'relaciones_comerciales',
            'informacionPEP': 'informacionPEP',  # Mantener como JSONField, no convertir
            'tipoFormulario': 'tipo_formulario',
            'comercial_asignado': 'asignado_a',
            'comercialAsignado': 'asignado_a_id'  # Mapear camelCase del frontend directamente al ID
        }
        
        # Convertir campos camelCase a snake_case
        converted_data = {}
        for key, value in data.items():
            new_key = field_mapping.get(key, key)
            converted_data[new_key] = value
        
        # Convertir campos anidados de informacionPEP
        if 'informacionPEP' in converted_data and isinstance(converted_data['informacionPEP'], list):
            for pep_item in converted_data['informacionPEP']:
                if isinstance(pep_item, dict):
                    # Convertir numeroIdentificacion a numero_identificacion
                    if 'numeroIdentificacion' in pep_item:
                        pep_item['numero_identificacion'] = pep_item.pop('numeroIdentificacion')
                    # Convertir patrimonioFiducia a patrimonio_fiducia
                    if 'patrimonioFiducia' in pep_item:
                        pep_item['patrimonio_fiducia'] = pep_item.pop('patrimonioFiducia')
                    # Convertir relacionesComerciales a relaciones_comerciales
                    if 'relacionesComerciales' in pep_item:
                        pep_item['relaciones_comerciales'] = pep_item.pop('relacionesComerciales')
        
        # Limpiar fechas vacías (convertir strings vacíos a None)
        date_fields = ['fecha_resolucion_gc', 'fecha_resolucion_autorretenedor', 'fecha_nacimiento', 'fecha_creacion']
        for field in date_fields:
            if field in converted_data and converted_data[field] == '':
                converted_data[field] = None
                
        # Llamar al método padre con los datos convertidos
        return super().to_internal_value(converted_data)
    
    def to_representation(self, instance):
        """
        Personalizar la salida para incluir todos los campos correctamente
        """
        data = super().to_representation(instance)
        
        # Asegurar que campos relacionados se incluyan correctamente
        if hasattr(instance, 'asignado_a') and instance.asignado_a:
            data['asignado_a_nombre'] = instance.asignado_a.get_full_name()
            data['asignado_a_email'] = instance.asignado_a.email
        
        if hasattr(instance, 'asignado_a_procesos') and instance.asignado_a_procesos:
            data['asignado_a_procesos_nombre'] = instance.asignado_a_procesos.get_full_name()
            data['asignado_a_procesos_email'] = instance.asignado_a_procesos.email
        
        # Asegurar que arrays vacíos se devuelvan como arrays y no como strings
        array_fields = [
            'fuentesFondos', 'tiposRecursos', 'tiposOperacionesMonedaExtranjera',
            'representantes', 'accionistas_frontend', 'informacion_pep', 'informacionPEP'
        ]
        
        for field in array_fields:
            if field in data and data[field] is None:
                data[field] = []
            elif field in data and isinstance(data[field], str):
                # Si es un string, intentar parsearlo como JSON
                try:
                    import json
                    data[field] = json.loads(data[field]) if data[field] else []
                except (json.JSONDecodeError, TypeError):
                    data[field] = []
        
        # Asegurar compatibilidad entre versiones camelCase y snake_case de PEP
        if 'informacionPEP' in data and data['informacionPEP']:
            data['informacion_pep'] = data['informacionPEP']
        elif 'informacion_pep' in data and data['informacion_pep']:
            data['informacionPEP'] = data['informacion_pep']
        
        return data
    
    def validate(self, data):
        """
        Validaciones personalizadas adicionales
        """
        return data

class TerceroVinculacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tercero
        fields = [
            'id', 'tipo_formulario', 'tipo_persona', 'tipo_documento', 'numero_documento',
            'nombres', 'apellidos', 'razon_social', 'fecha_nacimiento', 'fecha_creacion',
            'actividad_economica_principal', 'codigo_ciiu', 'direccion', 'pais', 'departamento',
            'ciudad', 'telefono', 'celular', 'email', 'responsable_iva', 'correo_facturacion_electronica',
            'gran_contribuyente', 'numero_resolucion_gc', 'fecha_resolucion_gc', 'auto_retenedor',
            'exento_impuesto_renta', 'condiciones_exencion', 'operaciones_moneda_extranjera',
            'detalle_operaciones_extranjera', 'observaciones_adicionales', 'estado_aprobacion',
            'representantes_legales', 'composicion_accionaria', 'informacion_financiera', 'documentos',
            # Nuevos campos de contacto separados
            'nombre_persona_contacto', 'cargo_persona_contacto',
            # Nuevos campos de activos virtuales
            'manejo_activos_virtuales', 'detalle_activos_virtuales',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, data):
        """Validaciones personalizadas"""
        tipo_persona = data.get('tipo_persona')
        
        # Validaciones para persona jurídica
        if tipo_persona == 'juridica':
            if not data.get('razon_social'):
                raise serializers.ValidationError("Razón social es obligatoria para persona jurídica")
            if not data.get('fecha_creacion'):
                raise serializers.ValidationError("Fecha de creación es obligatoria para persona jurídica")
        
        # Validaciones para persona natural
        elif tipo_persona == 'natural':
            if not data.get('nombres') or not data.get('apellidos'):
                raise serializers.ValidationError("Nombres y apellidos son obligatorios para persona natural")
            if not data.get('fecha_nacimiento'):
                raise serializers.ValidationError("Fecha de nacimiento es obligatoria para persona natural")
        
        # Validaciones de campos obligatorios comunes
        required_fields = ['actividad_economica_principal', 'codigo_ciiu', 'direccion', 'telefono']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError(f"{field} es obligatorio")
        
        # Validar código CIIU (4 dígitos)
        codigo_ciiu = data.get('codigo_ciiu', '')
        if codigo_ciiu and (len(codigo_ciiu) != 4 or not codigo_ciiu.isdigit()):
            raise serializers.ValidationError("Código CIIU debe tener exactamente 4 dígitos")
        
        # Validaciones condicionales para IVA
        if data.get('responsable_iva') and not data.get('correo_facturacion_electronica'):
            raise serializers.ValidationError("Correo para facturación electrónica es obligatorio si es responsable de IVA")
        
        if data.get('gran_contribuyente'):
            if not data.get('numero_resolucion_gc'):
                raise serializers.ValidationError("Número de resolución es obligatorio para gran contribuyente")
            if not data.get('fecha_resolucion_gc'):
                raise serializers.ValidationError("Fecha de resolución es obligatoria para gran contribuyente")
        
        # Validaciones para nuevos campos de contacto
        if not data.get('nombre_persona_contacto'):
            raise serializers.ValidationError("El nombre de la persona de contacto es obligatorio")
        if not data.get('cargo_persona_contacto'):
            raise serializers.ValidationError("El cargo de la persona de contacto es obligatorio")
        
        # Validaciones para tipo de documento según tipo de persona
        if data.get('tipo_persona') in ['juridica', 'publica']:
            if data.get('tipo_documento') != 'NIT':
                raise serializers.ValidationError("Las personas jurídicas y públicas deben usar únicamente NIT como tipo de documento")
        
        # Validaciones para activos virtuales
        if data.get('manejo_activos_virtuales'):
            if not data.get('detalle_activos_virtuales', '').strip():
                raise serializers.ValidationError("Debe especificar el detalle de activos virtuales cuando indica que los maneja")
        
        return data

    def create(self, validated_data):
        # Extraer datos anidados
        representantes_data = validated_data.pop('representantes_legales', [])
        composicion_data = validated_data.pop('composicion_accionaria', [])
        informacion_financiera_data = validated_data.pop('informacion_financiera', None)
        
        # Crear tercero
        tercero = Tercero.objects.create(**validated_data)
        
        # Crear representantes legales
        for repr_data in representantes_data:
            RepresentanteLegal.objects.create(tercero=tercero, **repr_data)
        
        # Crear composición accionaria
        for comp_data in composicion_data:
            ComposicionAccionaria.objects.create(tercero=tercero, **comp_data)
        
        # Crear información financiera
        if informacion_financiera_data:
            InformacionFinanciera.objects.create(tercero=tercero, **informacion_financiera_data)
        
        return tercero

    def update(self, instance, validated_data):
        # Extraer datos anidados
        representantes_data = validated_data.pop('representantes_legales', [])
        composicion_data = validated_data.pop('composicion_accionaria', [])
        informacion_financiera_data = validated_data.pop('informacion_financiera', None)
        
        # Actualizar tercero
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar representantes legales
        if representantes_data:
            instance.representantes_legales.all().delete()
            for repr_data in representantes_data:
                RepresentanteLegal.objects.create(tercero=instance, **repr_data)
        
        # Actualizar composición accionaria
        if composicion_data:
            instance.composicion_accionaria.all().delete()
            for comp_data in composicion_data:
                ComposicionAccionaria.objects.create(tercero=instance, **comp_data)
        
        # Actualizar información financiera
        if informacion_financiera_data:
            if hasattr(instance, 'informacion_financiera'):
                for attr, value in informacion_financiera_data.items():
                    setattr(instance.informacion_financiera, attr, value)
                instance.informacion_financiera.save()
            else:
                InformacionFinanciera.objects.create(tercero=instance, **informacion_financiera_data)
        
        return instance


class TerceroWorkflowSerializer(serializers.ModelSerializer):
    """
    Serializer específico para workflow de terceros
    Incluye información completa de asignaciones y estados
    """
    # Información de asignaciones
    asignado_a_info = serializers.SerializerMethodField()
    asignado_a_procesos_info = serializers.SerializerMethodField()
    asignado_cumplimiento_info = serializers.SerializerMethodField()
    usuario_ultimo_cambio_info = serializers.SerializerMethodField()
    
    # Transiciones permitidas para el usuario actual
    transiciones_permitidas = serializers.SerializerMethodField()
    
    # Información de observaciones por departamento
    tiene_observaciones_procesos = serializers.SerializerMethodField()
    tiene_observaciones_cumplimiento = serializers.SerializerMethodField()
    
    class Meta:
        model = Tercero
        fields = [
            'id', 'numero_documento', 'nombres', 'apellidos', 'razon_social',
            'email', 'telefono', 'estado_aprobacion', 'tipo_persona',
            
            # Campos de workflow
            'fecha_ultimo_cambio_estado', 'fecha_asignacion_comercial',
            'observaciones', 'observaciones_procesos', 'observaciones_cumplimiento',
            
            # Información de asignaciones
            'asignado_a_info', 'asignado_a_procesos_info', 'asignado_cumplimiento_info',
            'usuario_ultimo_cambio_info',
            
            # Flags y utilidades
            'tiene_observaciones_procesos', 'tiene_observaciones_cumplimiento',
            'transiciones_permitidas',
            
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'fecha_ultimo_cambio_estado',
            'fecha_asignacion_comercial', 'asignado_a_info', 'asignado_a_procesos_info',
            'asignado_cumplimiento_info', 'usuario_ultimo_cambio_info',
            'transiciones_permitidas', 'tiene_observaciones_procesos',
            'tiene_observaciones_cumplimiento'
        ]
    
    def get_asignado_a_info(self, obj):
        """Información del comercial asignado"""
        if obj.asignado_a:
            return {
                'id': obj.asignado_a.id,
                'username': obj.asignado_a.username,
                'nombre_completo': obj.asignado_a.get_full_name(),
                'email': obj.asignado_a.email,
                'fecha_asignacion': obj.fecha_asignacion_comercial
            }
        return None
    
    def get_asignado_a_procesos_info(self, obj):
        """Información del usuario de procesos asignado"""
        if obj.asignado_a_procesos:
            return {
                'id': obj.asignado_a_procesos.id,
                'username': obj.asignado_a_procesos.username,
                'nombre_completo': obj.asignado_a_procesos.get_full_name(),
                'email': obj.asignado_a_procesos.email,
                'fecha_asignacion': obj.fecha_asignacion_procesos
            }
        return None
    
    def get_asignado_cumplimiento_info(self, obj):
        """Información del oficial de cumplimiento asignado"""
        if obj.asignado_cumplimiento:
            return {
                'id': obj.asignado_cumplimiento.id,
                'username': obj.asignado_cumplimiento.username,
                'nombre_completo': obj.asignado_cumplimiento.get_full_name(),
                'email': obj.asignado_cumplimiento.email
            }
        return None
    
    def get_usuario_ultimo_cambio_info(self, obj):
        """Información del último usuario que cambió el estado"""
        if obj.usuario_ultimo_cambio:
            return {
                'id': obj.usuario_ultimo_cambio.id,
                'username': obj.usuario_ultimo_cambio.username,
                'nombre_completo': obj.usuario_ultimo_cambio.get_full_name(),
                'role': getattr(obj.usuario_ultimo_cambio, 'role', 'sin_rol')
            }
        return None
    
    def get_transiciones_permitidas(self, obj):
        """Obtener transiciones permitidas para el usuario actual del contexto"""
        request = self.context.get('request')
        if request and request.user:
            return obj.obtener_transiciones_permitidas(request.user)
        return {}
    
    def get_tiene_observaciones_procesos(self, obj):
        """Verificar si tiene observaciones de procesos"""
        return bool(obj.observaciones_procesos and obj.observaciones_procesos.strip())
    
    def get_tiene_observaciones_cumplimiento(self, obj):
        """Verificar si tiene observaciones de cumplimiento"""
        return bool(obj.observaciones_cumplimiento and obj.observaciones_cumplimiento.strip())


# ============================================
# SERIALIZERS PARA HISTORIAL Y AUDITORÍA
# ============================================

class HistorialTerceroSerializer(serializers.ModelSerializer):
    """Serializer para el historial de cambios de terceros"""
    
    usuario_nombre = serializers.SerializerMethodField()
    usuario_asignado_anterior_nombre = serializers.SerializerMethodField()
    usuario_asignado_nuevo_nombre = serializers.SerializerMethodField()
    accion_display = serializers.CharField(source='get_accion_display', read_only=True)
    descripcion_completa = serializers.ReadOnlyField()
    fecha_accion_formateada = serializers.SerializerMethodField()
    
    class Meta:
        model = HistorialTercero
        fields = [
            'id',
            'accion',
            'accion_display',
            'estado_anterior', 
            'estado_nuevo',
            'usuario',
            'usuario_nombre',
            'usuario_asignado_anterior',
            'usuario_asignado_anterior_nombre',
            'usuario_asignado_nuevo',
            'usuario_asignado_nuevo_nombre',
            'departamento',
            'observaciones',
            'metadatos',
            'fecha_accion',
            'fecha_accion_formateada',
            'descripcion_completa',
            'ip_address',
            'user_agent'
        ]
        read_only_fields = fields  # Todo es de solo lectura
    
    def get_usuario_nombre(self, obj):
        """Nombre completo del usuario que realizó la acción"""
        if obj.usuario:
            return f"{obj.usuario.get_full_name()} ({obj.usuario.username})"
        return "Sistema"
    
    def get_usuario_asignado_anterior_nombre(self, obj):
        """Nombre del usuario asignado anterior"""
        if obj.usuario_asignado_anterior:
            return f"{obj.usuario_asignado_anterior.get_full_name()} ({obj.usuario_asignado_anterior.username})"
        return None
    
    def get_usuario_asignado_nuevo_nombre(self, obj):
        """Nombre del usuario asignado nuevo"""
        if obj.usuario_asignado_nuevo:
            return f"{obj.usuario_asignado_nuevo.get_full_name()} ({obj.usuario_asignado_nuevo.username})"
        return None
    
    def get_fecha_accion_formateada(self, obj):
        """Fecha formateada en español"""
        return obj.fecha_accion.strftime('%d/%m/%Y %H:%M:%S')


class TerceroConHistorialSerializer(TerceroSerializer):
    """Serializer del tercero que incluye historial completo"""
    
    historial = HistorialTerceroSerializer(many=True, read_only=True)
    asignacion_actual = serializers.SerializerMethodField()
    ultima_accion = serializers.SerializerMethodField()
    resumen_historial = serializers.SerializerMethodField()
    
    class Meta(TerceroSerializer.Meta):
        fields = TerceroSerializer.Meta.fields + [
            'historial',
            'asignacion_actual', 
            'ultima_accion',
            'resumen_historial'
        ]
    
    def get_asignacion_actual(self, obj):
        """Información detallada de asignación actual"""
        return obj.obtener_asignacion_actual()
    
    def get_ultima_accion(self, obj):
        """Última acción realizada"""
        ultima = obj.obtener_ultima_accion()
        if ultima:
            return HistorialTerceroSerializer(ultima).data
        return None
    
    def get_resumen_historial(self, obj):
        """Resumen estadístico del historial"""
        historial = obj.historial.all()
        
        # Contar acciones por tipo
        conteo_acciones = {}
        for entrada in historial:
            accion = entrada.get_accion_display()
            conteo_acciones[accion] = conteo_acciones.get(accion, 0) + 1
        
        # Contar usuarios únicos que han interactuado
        usuarios_unicos = set()
        for entrada in historial:
            if entrada.usuario:
                usuarios_unicos.add(entrada.usuario.get_full_name())
        
        # Tiempo total en proceso
        tiempo_total = None
        if historial.exists():
            primera_accion = historial.last().fecha_accion
            ultima_accion = historial.first().fecha_accion
            tiempo_total = (ultima_accion - primera_accion).days
        
        return {
            'total_acciones': historial.count(),
            'acciones_por_tipo': conteo_acciones,
            'usuarios_involucrados': list(usuarios_unicos),
            'tiempo_total_dias': tiempo_total,
            'fecha_creacion': historial.last().fecha_accion if historial.exists() else None,
            'ultima_modificacion': historial.first().fecha_accion if historial.exists() else None
        }
