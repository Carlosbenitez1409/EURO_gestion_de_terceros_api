"""
Comando para migrar terceros del flujo legacy al nuevo flujo
Uso: python manage.py migrar_flujo_terceros
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from terceros.models import Tercero
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migra todos los terceros del flujo legacy al nuevo flujo de estados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta en modo de prueba sin hacer cambios reales',
        )
        parser.add_argument(
            '--tercero-id',
            type=str,
            help='Migra solo un tercero específico por su ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tercero_id = options.get('tercero_id')
        
        self.stdout.write(
            self.style.SUCCESS('=== MIGRACIÓN DE FLUJO DE TERCEROS ===')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('MODO DRY-RUN: No se harán cambios reales')
            )
        
        try:
            if tercero_id:
                # Migrar un tercero específico
                self._migrar_tercero_especifico(tercero_id, dry_run)
            else:
                # Migrar todos los terceros
                self._migrar_todos_los_terceros(dry_run)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error durante la migración: {str(e)}')
            )
            logger.error(f'Error en migración: {str(e)}')
    
    def _migrar_tercero_especifico(self, tercero_id, dry_run):
        """Migra un tercero específico"""
        try:
            tercero = Tercero.objects.get(id=tercero_id)
            
            self.stdout.write(f'Migrando tercero {tercero_id}...')
            
            estado_anterior = tercero.estado_aprobacion
            
            if not dry_run:
                with transaction.atomic():
                    resultado = tercero.migrar_a_nuevo_flujo()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {resultado}')
                    )
            else:
                # Simular migración
                self.stdout.write(
                    f'DRY-RUN: {tercero_id} - {estado_anterior} → [nuevo estado]'
                )
                
        except Tercero.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tercero {tercero_id} no encontrado')
            )
    
    def _migrar_todos_los_terceros(self, dry_run):
        """Migra todos los terceros"""
        terceros = Tercero.objects.all()
        total = terceros.count()
        
        self.stdout.write(f'Encontrados {total} terceros para migrar')
        
        if total == 0:
            self.stdout.write('No hay terceros para migrar')
            return
        
        # Mostrar estadísticas previas
        self._mostrar_estadisticas_previas(terceros)
        
        if not dry_run:
            # Confirmar antes de proceder
            confirmar = input('¿Desea continuar con la migración? (s/N): ')
            if confirmar.lower() != 's':
                self.stdout.write('Migración cancelada')
                return
        
        # Ejecutar migración
        migraciones_exitosas = 0
        migraciones_fallidas = 0
        
        for i, tercero in enumerate(terceros, 1):
            try:
                estado_anterior = tercero.estado_aprobacion
                
                if not dry_run:
                    with transaction.atomic():
                        resultado = tercero.migrar_a_nuevo_flujo()
                        self.stdout.write(
                            f'[{i}/{total}] ✓ Tercero {tercero.id}: {resultado}'
                        )
                        migraciones_exitosas += 1
                else:
                    self.stdout.write(
                        f'[{i}/{total}] DRY-RUN: {tercero.id} - {estado_anterior} → [nuevo estado]'
                    )
                    migraciones_exitosas += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'[{i}/{total}] ✗ Error en tercero {tercero.id}: {str(e)}'
                    )
                )
                migraciones_fallidas += 1
                logger.error(f'Error migrando tercero {tercero.id}: {str(e)}')
        
        # Resumen final
        self.stdout.write('\n=== RESUMEN DE MIGRACIÓN ===')
        self.stdout.write(f'Total terceros: {total}')
        self.stdout.write(
            self.style.SUCCESS(f'Migraciones exitosas: {migraciones_exitosas}')
        )
        if migraciones_fallidas > 0:
            self.stdout.write(
                self.style.ERROR(f'Migraciones fallidas: {migraciones_fallidas}')
            )
        
        if not dry_run:
            # Mostrar estadísticas posteriores
            self._mostrar_estadisticas_posteriores()
    
    def _mostrar_estadisticas_previas(self, terceros):
        """Muestra estadísticas de estados antes de la migración"""
        from django.db.models import Count
        
        self.stdout.write('\n=== ESTADÍSTICAS PREVIAS ===')
        estadisticas = terceros.values('estado_aprobacion').annotate(
            count=Count('id')
        ).order_by('-count')
        
        for stat in estadisticas:
            self.stdout.write(
                f"{stat['estado_aprobacion']}: {stat['count']} terceros"
            )
    
    def _mostrar_estadisticas_posteriores(self):
        """Muestra estadísticas de estados después de la migración"""
        from django.db.models import Count
        
        self.stdout.write('\n=== ESTADÍSTICAS POSTERIORES ===')
        terceros = Tercero.objects.all()
        estadisticas = terceros.values('estado_aprobacion').annotate(
            count=Count('id')
        ).order_by('-count')
        
        for stat in estadisticas:
            self.stdout.write(
                f"{stat['estado_aprobacion']}: {stat['count']} terceros"
            )
