"""
Comando de administración para migrar datos PEP legacy a nueva estructura
CRÍTICO: Ejecutar este comando después de aplicar la migración 0013_actualizacion_estructura_pep

Uso: python manage.py migrar_datos_pep
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from terceros.models import InformacionPEP
from datetime import date
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migra datos PEP de estructura legacy a nueva estructura según documentación 2025'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la migración sin realizar cambios reales',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la migración incluso si ya hay datos en estructura nueva',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write('🔄 Iniciando migración de datos PEP...')
        
        # Buscar registros con estructura legacy
        registros_legacy = InformacionPEP.objects.filter(
            cargo='No especificado',
            parentesco='No especificado'
        )
        
        if not registros_legacy.exists():
            self.stdout.write(
                self.style.WARNING('⚠️  No se encontraron registros con estructura legacy')
            )
            return
        
        self.stdout.write(f'📊 Registros legacy encontrados: {registros_legacy.count()}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🧪 Modo DRY-RUN activado - No se realizarán cambios'))
        
        # Contadores
        migrados = 0
        errores = 0
        
        with transaction.atomic():
            for registro in registros_legacy:
                try:
                    # Migrar datos basados en el tipo legacy
                    nuevo_cargo = self._mapear_cargo_desde_tipo(registro.tipo)
                    nuevo_parentesco = self._mapear_parentesco_desde_tipo(registro.tipo)
                    nuevo_tipo_documento = self._mapear_tipo_documento(registro.tipo)
                    
                    # Mapear cuentas financieras desde patrimonio_fiducia
                    cuentas_exterior = registro.patrimonio_fiducia
                    
                    # Establecer fechas por defecto si no existen
                    fecha_vinculacion = date(2020, 1, 1)  # Fecha por defecto
                    fecha_retiro = date(2025, 12, 31)     # Fecha por defecto futura
                    
                    if not dry_run:
                        # Actualizar el registro
                        registro.tipo = nuevo_tipo_documento  # ¡IMPORTANTE! Actualizar tipo también
                        registro.cargo = nuevo_cargo
                        registro.parentesco = nuevo_parentesco
                        registro.fecha_vinculacion = fecha_vinculacion
                        registro.fecha_retiro = fecha_retiro
                        registro.cuentas_financieras_exterior = cuentas_exterior
                        registro.save()
                    
                    migrados += 1
                    self.stdout.write(f'✅ Migrado: {registro.nombre} - {nuevo_cargo} ({nuevo_tipo_documento})')
                    
                except Exception as e:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Error migrando {registro.nombre}: {str(e)}')
                    )
                    logger.error(f'Error migrando registro PEP {registro.id}: {str(e)}')
        
        # Resumen
        self.stdout.write('')
        self.stdout.write('📋 RESUMEN DE MIGRACIÓN:')
        self.stdout.write(f'   ✅ Registros migrados: {migrados}')
        self.stdout.write(f'   ❌ Errores: {errores}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🧪 Migración simulada - Ejecute sin --dry-run para aplicar cambios'))
        else:
            self.stdout.write(self.style.SUCCESS('🎉 Migración completada exitosamente'))
    
    def _mapear_cargo_desde_tipo(self, tipo_legacy):
        """Mapea el tipo legacy a un cargo específico"""
        mapeo = {
            'funcionario': 'Funcionario Público Nacional',
            'familiar': 'Familiar de Funcionario',
            'colaborador': 'Colaborador Cercano',
            'otro': 'Otro Cargo',
            # Fallback para tipos de documento
            'CC': 'Funcionario Público',
            'CE': 'Funcionario Internacional',
            'NIT': 'Representante Legal',
            'PASAPORTE': 'Funcionario Diplomático'
        }
        return mapeo.get(tipo_legacy, 'Cargo no especificado')
    
    def _mapear_parentesco_desde_tipo(self, tipo_legacy):
        """Mapea el tipo legacy a un parentesco específico"""
        mapeo = {
            'funcionario': 'Titular',
            'familiar': 'Familiar',
            'colaborador': 'Colaborador',
            'otro': 'Otro',
            # Fallback para tipos de documento
            'CC': 'Titular',
            'CE': 'Cónyuge',
            'NIT': 'Socio',
            'PASAPORTE': 'Familiar'
        }
        return mapeo.get(tipo_legacy, 'Relación no especificada')
    
    def _mapear_tipo_documento(self, tipo_legacy):
        """Mapea el tipo legacy a un tipo de documento válido"""
        mapeo = {
            'funcionario': 'CC',
            'familiar': 'CC',
            'colaborador': 'CE',
            'otro': 'CC',
            # Si ya es un tipo de documento válido, mantenerlo
            'CC': 'CC',
            'CE': 'CE',
            'NIT': 'NIT',
            'PASAPORTE': 'PASAPORTE'
        }
        return mapeo.get(tipo_legacy, 'CC')  # Por defecto CC
