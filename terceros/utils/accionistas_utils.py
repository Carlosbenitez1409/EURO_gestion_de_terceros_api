"""
Utilidades para procesamiento de estructura jerárquica de accionistas
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from terceros.models import Accionista
import logging

logger = logging.getLogger('euro_terceros')


def process_accionistas_jerarquicos(tercero, accionistas_data):
    """
    Procesa la estructura jerárquica de accionistas recursivamente
    
    Args:
        tercero: Instancia del modelo Tercero
        accionistas_data: Lista de accionistas con estructura jerárquica
    
    Returns:
        List[Accionista]: Lista de accionistas creados
    """
    
    def save_accionistas_recursivo(accionistas, padre_id=None, nivel=0):
        """Función recursiva para guardar accionistas"""
        accionistas_guardados = []
        
        for acc_data in accionistas:
            # Crear accionista
            accionista = Accionista.objects.create(
                tercero=tercero,
                empresa_padre=acc_data.get('empresaPadre', ''),
                nombre=acc_data['nombre'],
                numero_identificacion=acc_data['identificacion'],
                tipo_identificacion=acc_data['tipo'],
                porcentaje_participacion=acc_data['porcentaje'],
                nivel=nivel,
                padre_id=padre_id
            )
            
            logger.info(f"Accionista creado: {accionista.nombre} (Nivel {nivel})")
            accionistas_guardados.append(accionista)
            
            # Procesar sub-accionistas recursivamente
            sub_accionistas = acc_data.get('subAccionistas', [])
            if sub_accionistas:
                sub_guardados = save_accionistas_recursivo(
                    sub_accionistas,
                    accionista.id,
                    nivel + 1
                )
                accionistas_guardados.extend(sub_guardados)
        
        return accionistas_guardados
    
    # Limpiar accionistas existentes
    tercero.accionistas.all().delete()
    logger.info(f"Accionistas existentes eliminados para tercero {tercero.id}")
    
    # Guardar nueva estructura
    accionistas_creados = save_accionistas_recursivo(accionistas_data)
    logger.info(f"Total accionistas creados: {len(accionistas_creados)}")
    
    return accionistas_creados


def process_accionistas_legacy(tercero, accionistas_frontend_data):
    """
    Procesa estructura legacy (plana) como respaldo
    
    Args:
        tercero: Instancia del modelo Tercero
        accionistas_frontend_data: Lista de accionistas en formato legacy
    
    Returns:
        List[Accionista]: Lista de accionistas creados
    """
    accionistas_guardados = []
    
    # Limpiar accionistas existentes
    tercero.accionistas.all().delete()
    logger.info(f"Accionistas existentes eliminados para tercero {tercero.id} (legacy)")
    
    for acc_data in accionistas_frontend_data:
        accionista = Accionista.objects.create(
            tercero=tercero,
            empresa_padre='',  # Legacy no tiene jerarquía
            nombre=acc_data['nombre'],
            numero_identificacion=acc_data['numeroIdentificacion'],
            tipo_identificacion=acc_data['tipoIdentificacion'],
            porcentaje_participacion=acc_data['porcentajeParticipacion'],
            nivel=0,
            padre_id=None
        )
        
        logger.info(f"Accionista legacy creado: {accionista.nombre}")
        accionistas_guardados.append(accionista)
    
    logger.info(f"Total accionistas legacy creados: {len(accionistas_guardados)}")
    return accionistas_guardados


def mapear_accionistas_a_legacy(accionistas_jerarquicos):
    """
    Convierte estructura jerárquica a formato legacy (plano)
    
    Args:
        accionistas_jerarquicos: Lista de accionistas con estructura jerárquica
    
    Returns:
        List[dict]: Lista plana de accionistas en formato legacy
    """
    
    def aplanar_accionistas(accionistas):
        """Función recursiva para aplanar la estructura"""
        result = []
        for accionista in accionistas:
            # Agregar accionista actual
            result.append({
                'nombre': accionista['nombre'],
                'tipoIdentificacion': accionista['tipo'],
                'numeroIdentificacion': accionista['identificacion'],
                'porcentajeParticipacion': accionista['porcentaje']
            })
            
            # Agregar sub-accionistas recursivamente
            sub_accionistas = accionista.get('subAccionistas', [])
            if sub_accionistas:
                result.extend(aplanar_accionistas(sub_accionistas))
        
        return result
    
    return aplanar_accionistas(accionistas_jerarquicos)


def validar_estructura_accionistas(accionistas_data):
    """
    Valida la estructura jerárquica de accionistas
    
    Args:
        accionistas_data: Lista de accionistas con estructura jerárquica
    
    Returns:
        List[str]: Lista de errores encontrados
    """
    errors = []
    
    def validar_recursivo(accionistas, nivel=0, path=""):
        """Función recursiva de validación"""
        
        # Límite de profundidad
        if nivel > 3:
            errors.append(f"Estructura muy profunda en {path} (máximo 3 niveles)")
            return
        
        total_porcentaje = 0
        identificaciones = set()
        
        for i, acc in enumerate(accionistas):
            current_path = f"{path}.{i}" if path else str(i)
            
            # Validaciones de campo
            if not acc.get('nombre'):
                errors.append(f"Nombre requerido en posición {current_path}")
            
            if not acc.get('identificacion'):
                errors.append(f"Identificación requerida en posición {current_path}")
            else:
                id_val = acc['identificacion']
                if id_val in identificaciones:
                    errors.append(f"Identificación duplicada ({id_val}) en {current_path}")
                identificaciones.add(id_val)
            
            # Validar tipo
            tipo = acc.get('tipo', '')
            if tipo not in ['CC', 'CE', 'NIT', 'OTRO']:
                errors.append(f"Tipo inválido ({tipo}) en {current_path}")
            
            # Validar porcentaje
            porcentaje = acc.get('porcentaje', 0)
            if porcentaje <= 0 or porcentaje > 100:
                errors.append(f"Porcentaje inválido ({porcentaje}) en {current_path}")
            total_porcentaje += porcentaje
            
            # Validar consistencia empresaPadre
            if nivel > 0:
                empresa_padre = acc.get('empresaPadre', '')
                if not empresa_padre:
                    errors.append(f"empresaPadre requerido para sub-accionista en {current_path}")
            
            # Validar que solo empresas (NIT) tengan sub-accionistas
            sub_accionistas = acc.get('subAccionistas', [])
            if sub_accionistas and acc.get('tipo') != 'NIT':
                errors.append(f"Solo empresas (NIT) pueden tener sub-accionistas en {current_path}")
            
            # Validar recursivamente
            if sub_accionistas:
                validar_recursivo(sub_accionistas, nivel + 1, current_path)
        
        # Validar suma de porcentajes por nivel
        if total_porcentaje > 100:
            nivel_desc = "principal" if nivel == 0 else f"nivel {nivel}"
            errors.append(f"Suma de porcentajes excede 100% en {nivel_desc} ({total_porcentaje}%)")
    
    validar_recursivo(accionistas_data)
    return errors


def validar_reglas_negocio_accionistas(accionistas):
    """
    Validaciones adicionales de reglas de negocio
    
    Args:
        accionistas: QuerySet de accionistas del tercero
    
    Raises:
        ValidationError: Si se encuentran violaciones de reglas de negocio
    """
    
    # Verificar que empresas con sub-accionistas sean tipo NIT
    for accionista in accionistas:
        if accionista.sub_accionistas.exists() and accionista.tipo_identificacion != 'NIT':
            raise ValidationError(
                f"Solo empresas (NIT) pueden tener sub-accionistas: {accionista.nombre}"
            )
    
    # Verificar límite de niveles
    max_nivel = max(acc.nivel for acc in accionistas) if accionistas else 0
    if max_nivel > 2:  # 0, 1, 2 = 3 niveles máximo
        raise ValidationError("Máximo 3 niveles de jerarquía permitidos")
    
    # Verificar integridad de referencias padre
    for accionista in [a for a in accionistas if a.nivel > 0]:
        if not accionista.padre:
            raise ValidationError(f"Sub-accionista sin padre válido: {accionista.nombre_razon_social}")
        
        if accionista.empresa_padre != accionista.padre.numero_identificacion:
            raise ValidationError(f"Inconsistencia en empresaPadre: {accionista.nombre_razon_social}")
    
    # Verificar porcentajes por nivel
    niveles = {}
    for accionista in accionistas:
        padre_key = accionista.padre_id or 'principal'
        if padre_key not in niveles:
            niveles[padre_key] = []
        niveles[padre_key].append(accionista.porcentaje_participacion)
    
    for padre_key, porcentajes in niveles.items():
        total = sum(porcentajes)
        if total > 100:
            padre_desc = "principal" if padre_key == 'principal' else f"padre {padre_key}"
            raise ValidationError(f"Suma de porcentajes excede 100% en nivel {padre_desc}: {total}%")


@transaction.atomic
def procesar_accionistas_completo(tercero, data_accionistas):
    """
    Función principal para procesar accionistas con manejo completo
    
    Args:
        tercero: Instancia del modelo Tercero
        data_accionistas: Dict con estructura de accionistas (nueva y/o legacy)
    
    Returns:
        List[Accionista]: Lista de accionistas procesados
    
    Raises:
        ValidationError: Si hay errores en la validación
    """
    
    accionistas = data_accionistas.get('accionistas', [])
    accionistas_frontend = data_accionistas.get('accionistas_frontend', [])
    
    # Determinar qué estructura usar
    if accionistas:
        logger.info(f"Procesando estructura jerárquica para tercero {tercero.id}")
        
        # Validar estructura jerárquica
        errores = validar_estructura_accionistas(accionistas)
        if errores:
            raise ValidationError(f"Errores en estructura jerárquica: {'; '.join(errores)}")
        
        # Procesar estructura jerárquica
        accionistas_creados = process_accionistas_jerarquicos(tercero, accionistas)
        
    elif accionistas_frontend:
        logger.info(f"Procesando estructura legacy para tercero {tercero.id}")
        
        # Validar suma de porcentajes legacy
        total_porcentaje = sum(float(acc.get('porcentajeParticipacion', 0)) for acc in accionistas_frontend)
        if total_porcentaje > 100:
            raise ValidationError(f"La suma de porcentajes excede 100%: {total_porcentaje}%")
        
        # Procesar estructura legacy
        accionistas_creados = process_accionistas_legacy(tercero, accionistas_frontend)
        
    else:
        logger.info(f"No hay accionistas para procesar en tercero {tercero.id}")
        return []
    
    # Validar reglas de negocio post-creación
    validar_reglas_negocio_accionistas(accionistas_creados)
    
    logger.info(f"Procesamiento de accionistas completado para tercero {tercero.id}")
    return accionistas_creados


def obtener_estructura_jerarquica(tercero):
    """
    Obtiene la estructura jerárquica completa de accionistas
    
    Args:
        tercero: Instancia del modelo Tercero
    
    Returns:
        dict: Estructura jerárquica de accionistas
    """
    
    def construir_estructura_recursiva(accionista):
        """Construir estructura recursiva"""
        sub_accionistas = []
        for sub in accionista.sub_accionistas.all().order_by('nombre'):
            sub_accionistas.append(construir_estructura_recursiva(sub))
        
        return {
            'id': accionista.id,
            'empresaPadre': accionista.empresa_padre,
            'nombre': accionista.nombre,
            'identificacion': accionista.numero_identificacion,
            'tipo': accionista.tipo_identificacion,
            'porcentaje': float(accionista.porcentaje_participacion),
            'nivel': accionista.nivel,
            'subAccionistas': sub_accionistas
        }
    
    # Obtener accionistas principales (nivel 0)
    accionistas_principales = tercero.accionistas.filter(nivel=0, padre__isnull=True).order_by('nombre')
    
    estructura = []
    for accionista in accionistas_principales:
        estructura.append(construir_estructura_recursiva(accionista))
    
    # También generar formato legacy para compatibilidad
    accionistas_legacy = []
    for accionista in tercero.accionistas.all().order_by('nivel', 'nombre'):
        accionistas_legacy.append({
            'nombre': accionista.nombre,
            'tipoIdentificacion': accionista.tipo_identificacion,
            'numeroIdentificacion': accionista.numero_identificacion,
            'porcentajeParticipacion': float(accionista.porcentaje_participacion)
        })
    
    return {
        'accionistas': estructura,
        'accionistas_frontend': accionistas_legacy
    }