# euro_terceros/config.py
"""
Configuración del sistema de correos para terceros
"""
import os
from django.conf import settings

# Destinatarios que SIEMPRE reciben los correos (desde settings/env)
def get_destinatarios_predeterminados():
    """Obtiene destinatarios desde configuración de settings"""
    # Solo devolver la lista desde settings, SIN valores por defecto hardcodeados
    destinatarios = getattr(settings, 'EMAILS_PREDETERMINADOS', [])
    if not destinatarios:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "⚠️  DESTINATARIOS_CORREOS_TERCEROS no configurado en .env. "
            "Define esta variable para especificar los destinatarios de correos."
        )
    return destinatarios

DESTINATARIOS_PREDETERMINADOS = get_destinatarios_predeterminados()

# Estados válidos para envío de correos
ESTADOS_CORREO_PERMITIDOS = [
    'aprobado',
    'aprobado_final',
]

# Configuraciones de correo
EMAIL_CONFIG = {
    'DEFAULT_FROM_EMAIL': getattr(settings, 'DEFAULT_FROM_EMAIL', os.getenv('DEFAULT_FROM_EMAIL', 'EURO Sistema <noreply@euroterceros.com>')),
    'TEMPLATES_PATH': 'emails/',
    'ATTACHMENT_MAX_SIZE': int(os.getenv('MAX_FILE_SIZE', '10')) * 1024 * 1024,  # MB a bytes
}

# Plantillas disponibles
EMAIL_TEMPLATES = {
    'tercero_aprobado': {
        'html': 'emails/tercero_aprobado.html',
        'text': 'emails/tercero_aprobado.txt',
        'subject': 'Tercero Aprobado: {nombre_completo}',
    }
}

# Configuración de documentos adjuntos
DOCUMENTOS_CONFIG = {
    'tipos_incluir': [
        'rut',                         # ✅ RUT siempre incluido
        'certificacion_bancaria'       # ✅ Certificación bancaria siempre incluida
    ],
    'tipos_opcionales': [
        # No hay documentos opcionales - solo RUT y certificación bancaria
    ],
    # Mapeo de tipos de documento para mejorar búsqueda
    'mapeo_tipos': {
        'rut': ['rut', 'registro_unico_tributario'],
        'certificacion_bancaria': ['certificacion_bancaria', 'certificado_bancario', 'banco'],
    }
}
