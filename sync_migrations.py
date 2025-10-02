#!/usr/bin/env python
"""
Script para sincronizar migraciones entre diferentes bases de datos
Útil cuando se cambia entre entornos (local, staging, producción)
"""
import os
import sys
import django
from django.core.management import execute_from_command_line
from django.db import connection
from django.apps import apps

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'euro_terceros.settings')
django.setup()

def check_table_exists(table_name):
    """Verificar si una tabla existe en la base de datos"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, [table_name])
        return cursor.fetchone()[0]

def check_column_exists(table_name, column_name):
    """Verificar si una columna existe en una tabla"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            )
        """, [table_name, column_name])
        return cursor.fetchone()[0]

def get_applied_migrations():
    """Obtener migraciones aplicadas en la BD"""
    from django.db.migrations.recorder import MigrationRecorder
    recorder = MigrationRecorder(connection)
    return set(recorder.applied_migrations())

def sync_migrations():
    """Sincronizar el estado de migraciones con la BD actual"""
    print("🔍 Analizando estado de la base de datos...")
    
    # Verificar algunas columnas clave que sabemos que pueden causar conflictos
    problematic_checks = [
        ('accounts_user', 'cargo', 'accounts', '0002_add_cargo_field'),
        ('terceros_tercero', 'constituyePatrimoniosAutonomos', 'terceros', '0006_backup'),
        # Agregar más checks según sea necesario
    ]
    
    migrations_to_fake = []
    
    for table, column, app, migration in problematic_checks:
        if check_column_exists(table, column):
            print(f"✅ Columna {column} existe en {table}")
            migrations_to_fake.append((app, migration))
        else:
            print(f"❌ Columna {column} NO existe en {table}")
    
    # Marcar migraciones como fake si es necesario
    for app, migration in migrations_to_fake:
        print(f"🔄 Marcando {app}.{migration} como aplicada...")
        os.system(f'python manage.py migrate {app} {migration} --fake')
    
    print("\n🚀 Ejecutando migraciones restantes...")
    os.system('python manage.py migrate')
    
    print("\n✅ Sincronización completada!")

if __name__ == "__main__":
    sync_migrations()