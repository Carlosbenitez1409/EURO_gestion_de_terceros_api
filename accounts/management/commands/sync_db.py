from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command
import os

class Command(BaseCommand):
    help = 'Sincroniza migraciones con el estado actual de la base de datos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS('🔍 Iniciando sincronización de migraciones...')
        )

        # Definir migraciones problemáticas conocidas
        problematic_migrations = [
            {
                'app': 'accounts',
                'migration': '0002_add_cargo_field',
                'table': 'accounts_user',
                'column': 'cargo',
                'description': 'Campo cargo en usuarios'
            },
            {
                'app': 'accounts', 
                'migration': '0003_alter_user_cargo',
                'table': 'accounts_user',
                'column': 'cargo',
                'description': 'Alteración campo cargo'
            },
            {
                'app': 'accounts',
                'migration': '0004_alter_user_role', 
                'table': 'accounts_user',
                'column': 'role',
                'description': 'Campo role en usuarios'
            },
            {
                'app': 'terceros',
                'migration': '0006_backup',
                'table': 'terceros_tercero', 
                'column': 'constituyePatrimoniosAutonomos',
                'description': 'Campos patrimonios autónomos'
            }
        ]

        migrations_to_fake = []

        # Verificar cada migración problemática
        for migration_info in problematic_migrations:
            if self.column_exists(migration_info['table'], migration_info['column']):
                self.stdout.write(
                    f"✅ {migration_info['description']}: Columna existe, "
                    f"marcando {migration_info['app']}.{migration_info['migration']} como fake"
                )
                migrations_to_fake.append(migration_info)
            else:
                self.stdout.write(
                    f"❌ {migration_info['description']}: Columna NO existe, "
                    f"la migración se ejecutará normalmente"
                )

        # Ejecutar fake migrations si no es dry-run
        if not dry_run:
            for migration_info in migrations_to_fake:
                try:
                    call_command(
                        'migrate', 
                        migration_info['app'], 
                        migration_info['migration'], 
                        fake=True,
                        verbosity=0
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"🔄 Migración {migration_info['app']}.{migration_info['migration']} "
                            f"marcada como aplicada (FAKE)"
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"❌ Error al marcar {migration_info['app']}.{migration_info['migration']}: {e}"
                        )
                    )

            # Ejecutar migraciones restantes
            self.stdout.write(
                self.style.SUCCESS('🚀 Ejecutando migraciones restantes...')
            )
            try:
                call_command('migrate', verbosity=2)
                self.stdout.write(
                    self.style.SUCCESS('✅ Todas las migraciones aplicadas correctamente!')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error en migraciones: {e}')
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '🔍 DRY-RUN: No se ejecutaron cambios. '
                    'Usa sin --dry-run para aplicar los cambios.'
                )
            )

    def column_exists(self, table_name, column_name):
        """Verificar si una columna existe en una tabla"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                )
            """, [table_name, column_name])
            return cursor.fetchone()[0]