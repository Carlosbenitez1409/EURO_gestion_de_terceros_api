"""
Validaciones de negocio para composición accionaria
"""
from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger('euro_terceros')


class ValidadorAccionistas:
    """
    Clase para validaciones específicas de accionistas
    """
    
    @staticmethod
    def validar_porcentajes_nivel(accionistas, nivel=0, padre_id=None):
        """
        Valida que la suma de porcentajes de un nivel no exceda 100%
        
        Args:
            accionistas: Lista de accionistas del mismo nivel
            nivel: Nivel de la jerarquía
            padre_id: ID del padre (None para principales)
        
        Returns:
            dict: Resultado de validación con total y status
        """
        total_porcentaje = Decimal('0')
        
        for accionista in accionistas:
            try:
                porcentaje = Decimal(str(accionista.get('porcentaje', 0)))
                total_porcentaje += porcentaje
            except (InvalidOperation, TypeError):
                raise ValidationError(f"Porcentaje inválido en accionista: {accionista.get('nombre', 'Sin nombre')}")
        
        resultado = {
            'total': float(total_porcentaje),
            'valido': total_porcentaje <= 100,
            'nivel': nivel,
            'padre_id': padre_id
        }
        
        if not resultado['valido']:
            nivel_desc = "principal" if nivel == 0 else f"nivel {nivel}"
            padre_desc = f" (padre: {padre_id})" if padre_id else ""
            raise ValidationError(f"Suma de porcentajes excede 100% en {nivel_desc}{padre_desc}: {total_porcentaje}%")
        
        return resultado
    
    @staticmethod
    def validar_tipos_documento():
        """Retorna tipos de documento válidos"""
        return ['CC', 'CE', 'NIT', 'OTRO']
    
    @staticmethod
    def validar_estructura_jerarquica(data, max_nivel=3):
        """
        Valida la estructura jerárquica completa
        
        Args:
            data: Estructura de accionistas
            max_nivel: Máximo nivel permitido
        
        Returns:
            dict: Resultado de validación
        """
        errores = []
        warnings = []
        
        def validar_nivel(accionistas, nivel_actual=0, empresa_padre_esperada=None):
            if nivel_actual > max_nivel:
                errores.append(f"Estructura excede máximo nivel permitido ({max_nivel})")
                return
            
            identificaciones_nivel = set()
            total_porcentaje = Decimal('0')
            
            for i, accionista in enumerate(accionistas):
                # Validar campos obligatorios
                ValidadorAccionistas._validar_campos_obligatorios(accionista, errores, f"posición {i}")
                
                # Validar identificación única en el nivel
                identificacion = accionista.get('identificacion', '')
                if identificacion in identificaciones_nivel:
                    errores.append(f"Identificación duplicada en nivel {nivel_actual}: {identificacion}")
                identificaciones_nivel.add(identificacion)
                
                # Validar empresa_padre
                if nivel_actual > 0:
                    empresa_padre = accionista.get('empresaPadre', '')
                    if empresa_padre != empresa_padre_esperada:
                        errores.append(f"empresaPadre inconsistente: esperado {empresa_padre_esperada}, recibido {empresa_padre}")
                
                # Validar tipo
                tipo = accionista.get('tipo', '')
                if tipo not in ValidadorAccionistas.validar_tipos_documento():
                    errores.append(f"Tipo de documento inválido: {tipo}")
                
                # Validar porcentaje
                try:
                    porcentaje = Decimal(str(accionista.get('porcentaje', 0)))
                    if porcentaje <= 0 or porcentaje > 100:
                        errores.append(f"Porcentaje fuera de rango (0.01-100): {porcentaje}")
                    total_porcentaje += porcentaje
                except (InvalidOperation, TypeError):
                    errores.append(f"Porcentaje inválido: {accionista.get('porcentaje')}")
                
                # Validar sub-accionistas
                sub_accionistas = accionista.get('subAccionistas', [])
                if sub_accionistas:
                    # Solo empresas (NIT) pueden tener sub-accionistas
                    if tipo != 'NIT':
                        errores.append(f"Solo empresas (NIT) pueden tener sub-accionistas: {accionista.get('nombre')}")
                    
                    # Validar recursivamente
                    validar_nivel(sub_accionistas, nivel_actual + 1, identificacion)
            
            # Validar suma total del nivel
            if total_porcentaje > 100:
                errores.append(f"Suma de porcentajes excede 100% en nivel {nivel_actual}: {total_porcentaje}%")
            elif total_porcentaje < 99.99 and nivel_actual == 0:
                warnings.append(f"Suma de porcentajes principales menor a 100%: {total_porcentaje}%")
        
        # Iniciar validación desde nivel 0
        validar_nivel(data)
        
        return {
            'valido': len(errores) == 0,
            'errores': errores,
            'warnings': warnings
        }
    
    @staticmethod
    def _validar_campos_obligatorios(accionista, errores, posicion):
        """Valida que los campos obligatorios estén presentes"""
        campos_obligatorios = ['nombre', 'identificacion', 'tipo', 'porcentaje']
        
        for campo in campos_obligatorios:
            if not accionista.get(campo):
                errores.append(f"Campo obligatorio faltante '{campo}' en {posicion}")
    
    @staticmethod
    def validar_excel_accionistas(data_excel, empresa_padre_id):
        """
        Valida datos de Excel para sub-accionistas
        
        Args:
            data_excel: Lista de filas del Excel
            empresa_padre_id: ID de la empresa padre
        
        Returns:
            dict: Resultado de validación
        """
        errores = []
        warnings = []
        
        if not data_excel:
            errores.append("El archivo Excel está vacío")
            return {'valido': False, 'errores': errores, 'warnings': warnings}
        
        # Validar estructura de columnas
        columnas_requeridas = ['empresa_padre', 'nombre', 'identificacion', 'tipo', 'porcentaje_participacion']
        primera_fila = data_excel[0] if data_excel else {}
        
        for columna in columnas_requeridas:
            if columna not in primera_fila:
                errores.append(f"Columna faltante: {columna}")
        
        if errores:
            return {'valido': False, 'errores': errores, 'warnings': warnings}
        
        identificaciones_usadas = set()
        total_porcentaje = Decimal('0')
        
        for i, fila in enumerate(data_excel):
            fila_num = i + 2  # +2 porque Excel empieza en 1 y tiene header
            
            # Validar empresa_padre
            empresa_padre = str(fila.get('empresa_padre', '')).strip()
            if empresa_padre != empresa_padre_id:
                errores.append(f"Fila {fila_num}: empresa_padre debe ser {empresa_padre_id}")
            
            # Validar nombre
            nombre = str(fila.get('nombre', '')).strip()
            if not nombre:
                errores.append(f"Fila {fila_num}: nombre es requerido")
            
            # Validar identificación
            identificacion = str(fila.get('identificacion', '')).strip()
            if not identificacion:
                errores.append(f"Fila {fila_num}: identificacion es requerido")
            elif identificacion in identificaciones_usadas:
                errores.append(f"Fila {fila_num}: identificación {identificacion} duplicada")
            else:
                identificaciones_usadas.add(identificacion)
            
            # Validar tipo
            tipo = str(fila.get('tipo', '')).strip().upper()
            if tipo not in ValidadorAccionistas.validar_tipos_documento():
                errores.append(f"Fila {fila_num}: tipo debe ser CC, CE, NIT o OTRO")
            
            # Validar porcentaje
            try:
                porcentaje = Decimal(str(fila.get('porcentaje_participacion', 0)))
                if porcentaje <= 0:
                    errores.append(f"Fila {fila_num}: porcentaje debe ser mayor a 0")
                elif porcentaje > 100:
                    errores.append(f"Fila {fila_num}: porcentaje no puede exceder 100")
                else:
                    total_porcentaje += porcentaje
                    
                    # Validar máximo 2 decimales
                    if porcentaje * 100 % 1 != 0:
                        warnings.append(f"Fila {fila_num}: porcentaje tiene más de 2 decimales")
                        
            except (InvalidOperation, ValueError, TypeError):
                errores.append(f"Fila {fila_num}: porcentaje_participacion debe ser un número válido")
        
        # Validar suma total
        if total_porcentaje > 100:
            errores.append(f"La suma total de porcentajes ({total_porcentaje}%) excede 100%")
        elif total_porcentaje < 99.99:
            warnings.append(f"La suma total ({total_porcentaje}%) es menor a 100%")
        
        return {
            'valido': len(errores) == 0,
            'errores': errores,
            'warnings': warnings,
            'total_porcentaje': float(total_porcentaje),
            'total_registros': len(data_excel)
        }
    
    @staticmethod
    def validar_integridad_post_creacion(tercero):
        """
        Valida la integridad después de crear los accionistas en BD
        
        Args:
            tercero: Instancia del modelo Tercero
        
        Returns:
            dict: Resultado de validación
        """
        errores = []
        warnings = []
        
        accionistas = tercero.accionistas.all()
        
        if not accionistas.exists():
            warnings.append("El tercero no tiene accionistas")
            return {'valido': True, 'errores': errores, 'warnings': warnings}
        
        # Validar que empresas con sub-accionistas sean NIT
        for accionista in accionistas:
            if accionista.sub_accionistas.exists() and accionista.tipo_identificacion != 'NIT':
                errores.append(f"Solo empresas (NIT) pueden tener sub-accionistas: {accionista.nombre}")
        
        # Validar límite de niveles
        max_nivel = accionistas.aggregate(models.Max('nivel'))['nivel__max'] or 0
        if max_nivel > 2:  # 0, 1, 2 = 3 niveles máximo
            errores.append(f"Estructura excede máximo de 3 niveles (encontrado: {max_nivel + 1})")
        
        # Validar referencias padre-hijo
        for accionista in accionistas.filter(nivel__gt=0):
            if not accionista.padre:
                errores.append(f"Sub-accionista sin padre válido: {accionista.nombre}")
            elif accionista.empresa_padre != accionista.padre.numero_identificacion:
                errores.append(f"Inconsistencia en empresaPadre: {accionista.nombre}")
        
        # Validar porcentajes por nivel
        from django.db.models import Sum
        niveles_porcentajes = {}
        
        # Agrupar por padre (None para principales)
        for accionista in accionistas:
            padre_key = accionista.padre_id or 'principal'
            if padre_key not in niveles_porcentajes:
                niveles_porcentajes[padre_key] = []
            niveles_porcentajes[padre_key].append(accionista.porcentaje_participacion)
        
        for padre_key, porcentajes in niveles_porcentajes.items():
            total = sum(porcentajes)
            if total > 100:
                if padre_key == 'principal':
                    errores.append(f"Suma de porcentajes principales excede 100%: {total}%")
                else:
                    padre = accionistas.get(id=padre_key)
                    errores.append(f"Suma de porcentajes de {padre.nombre} excede 100%: {total}%")
        
        return {
            'valido': len(errores) == 0,
            'errores': errores,
            'warnings': warnings,
            'total_accionistas': accionistas.count(),
            'max_nivel': max_nivel
        }


class ValidadorCompatibilidad:
    """
    Validaciones para compatibilidad entre estructuras nueva y legacy
    """
    
    @staticmethod
    def validar_mapeo_legacy_a_nueva(accionistas_legacy):
        """
        Valida que los accionistas legacy se puedan mapear a estructura nueva
        
        Args:
            accionistas_legacy: Lista de accionistas en formato legacy
        
        Returns:
            dict: Resultado de validación y mapeo sugerido
        """
        errores = []
        warnings = []
        mapeo_sugerido = []
        
        total_porcentaje = Decimal('0')
        identificaciones = set()
        
        for i, acc in enumerate(accionistas_legacy):
            # Validar campos obligatorios legacy
            campos_requeridos = ['nombre', 'tipoIdentificacion', 'numeroIdentificacion', 'porcentajeParticipacion']
            for campo in campos_requeridos:
                if not acc.get(campo):
                    errores.append(f"Campo legacy faltante '{campo}' en posición {i}")
            
            # Validar identificación única
            identificacion = acc.get('numeroIdentificacion', '')
            if identificacion in identificaciones:
                errores.append(f"Identificación duplicada: {identificacion}")
            identificaciones.add(identificacion)
            
            # Validar tipo
            tipo = acc.get('tipoIdentificacion', '')
            if tipo not in ValidadorAccionistas.validar_tipos_documento():
                # Intentar mapear tipos legacy comunes
                mapeo_tipos = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE',
                    'nit': 'NIT',
                    'pasaporte': 'OTRO'
                }
                tipo_mapeado = mapeo_tipos.get(tipo.lower(), tipo)
                if tipo_mapeado in ValidadorAccionistas.validar_tipos_documento():
                    warnings.append(f"Tipo '{tipo}' mapeado a '{tipo_mapeado}' en posición {i}")
                    tipo = tipo_mapeado
                else:
                    errores.append(f"Tipo de documento inválido: {tipo}")
            
            # Validar porcentaje
            try:
                porcentaje = Decimal(str(acc.get('porcentajeParticipacion', 0)))
                if porcentaje <= 0 or porcentaje > 100:
                    errores.append(f"Porcentaje fuera de rango: {porcentaje}")
                total_porcentaje += porcentaje
            except (InvalidOperation, TypeError):
                errores.append(f"Porcentaje legacy inválido: {acc.get('porcentajeParticipacion')}")
                continue
            
            # Crear mapeo a estructura nueva
            mapeo_sugerido.append({
                'empresaPadre': '',  # Legacy no tiene jerarquía
                'nombre': acc.get('nombre', ''),
                'identificacion': identificacion,
                'tipo': tipo,
                'porcentaje': float(porcentaje),
                'subAccionistas': []
            })
        
        # Validar suma total
        if total_porcentaje > 100:
            errores.append(f"Suma total de porcentajes legacy excede 100%: {total_porcentaje}%")
        
        return {
            'valido': len(errores) == 0,
            'errores': errores,
            'warnings': warnings,
            'mapeo_sugerido': mapeo_sugerido,
            'total_porcentaje': float(total_porcentaje)
        }
    
    @staticmethod
    def generar_estructura_legacy(estructura_nueva):
        """
        Genera estructura legacy desde estructura jerárquica
        
        Args:
            estructura_nueva: Lista de accionistas jerárquicos
        
        Returns:
            list: Estructura legacy (plana)
        """
        
        def aplanar(accionistas):
            resultado = []
            for acc in accionistas:
                # Agregar accionista actual
                resultado.append({
                    'nombre': acc['nombre'],
                    'tipoIdentificacion': acc['tipo'],
                    'numeroIdentificacion': acc['identificacion'],
                    'porcentajeParticipacion': acc['porcentaje']
                })
                
                # Agregar sub-accionistas recursivamente
                sub_accionistas = acc.get('subAccionistas', [])
                if sub_accionistas:
                    resultado.extend(aplanar(sub_accionistas))
            
            return resultado
        
        return aplanar(estructura_nueva)