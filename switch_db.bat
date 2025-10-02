@echo off
REM =====================================
REM Script de Cambio de Base de Datos
REM EURO Terceros - Automatización Completa
REM =====================================

echo.
echo ========================================
echo   🚀 EURO TERCEROS - CAMBIO DE BD
echo ========================================
echo.

REM Activar virtual environment
call venv\Scripts\activate.bat

REM Backup del .env actual
echo 📋 Creando backup de configuración actual...
copy .env .env.backup.%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
echo ✅ Backup creado

echo.
echo 🔍 Estado actual de migraciones:
echo =====================================
python manage.py showmigrations | findstr "\[ \]" | find /c "[ ]" > temp_count.txt
set /p pending_count=<temp_count.txt
del temp_count.txt

if %pending_count% gtr 0 (
    echo ⚠️  Tienes %pending_count% migraciones pendientes
    echo.
    echo 🔧 Ejecutando sincronización automática...
    python manage.py sync_db
) else (
    echo ✅ Todas las migraciones están aplicadas
)

echo.
echo 🧪 Probando conexión a la base de datos...
python -c "from django.db import connection; connection.cursor().execute('SELECT 1'); print('✅ Conexión exitosa')"

echo.
echo 🚀 Iniciando servidor de desarrollo...
echo =====================================
echo.
echo Servidor corriendo en: http://127.0.0.1:8000
echo Para detener: Ctrl+C
echo.
python manage.py runserver

pause