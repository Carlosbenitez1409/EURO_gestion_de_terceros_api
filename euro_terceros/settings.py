"""
Django settings for euro_terceros project.
"""
import django
import os
from pathlib import Path
from datetime import timedelta
from decouple import config

# Cargar variables de entorno desde archivo .env
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-8r!m@x^9k%s$w@n#e4p&5q)z*7c_v+u!h#k$m@x^9k%s$w@n')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'django_filters',  # Soporte para filtros avanzados
    'accounts',  # Agregar la app accounts
    'terceros',
    'dashboard',
    'validations',
    'notifications',  # Agregar la app de notificaciones
    'stradata_consulta',  # App para consultas Stradata
    'usuarios_consultas',  # App para Sistema de Usuarios GH
    # 'debida_diligencia',  # App eliminada - usar sistema de terceros en su lugar
    # 'documents',  # Comentar esta línea para evitar conflictos de related_name
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'terceros.middleware.PublicTerceroRateLimitMiddleware',
]

ROOT_URLCONF = 'euro_terceros.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'euro_terceros.wsgi.application'

# ==========================================
# DATABASE CONFIGURATION - COMPLETAMENTE DESDE .ENV
# ==========================================
USE_SQLITE = config('USE_SQLITE', default=False, cast=bool)

if USE_SQLITE:
    # Configuración para SQLite (desarrollo local)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Configuración para PostgreSQL - TODO desde variables de entorno
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DATABASE_NAME'),          
            'USER': config('DATABASE_USER'),          
            'PASSWORD': config('DATABASE_PASSWORD'),  
            'HOST': config('DATABASE_HOST'),          
            'PORT': config('DATABASE_PORT', default='5432'),  # Puerto tiene default común
        }
    }


    
# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
# settings.py

import os

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'accounts.backends.UsernameOrEmailBackend',  # Backend personalizado
    #'django.contrib.auth.backends.ModelBackend',  # Backend por defecto
]

# Django REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,  # Optimizado para frontend
    'PAGE_SIZE_QUERY_PARAM': 'page_size',
    'MAX_PAGE_SIZE': 100,  # Límite máximo para prevenir abuso
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
        'django_filters.rest_framework.DjangoFilterBackend',  # Soporte para filtros avanzados
    ],
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS configuration
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://66.23.233.50:8020",  # Backend
    "http://66.23.233.50:8080",  # Frontend producción
    "http://localhost:8080",     # Frontend local desarrollo
    "http://127.0.0.1:8080",     # Frontend local desarrollo (alternativo)
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Logging configuration
import os

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# For production, use console logging if file logging fails
LOGGING_HANDLERS = ['console']
if DEBUG or os.access(LOGS_DIR, os.W_OK):
    LOGGING_HANDLERS.append('file')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'euro_terceros.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': LOGGING_HANDLERS,
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': LOGGING_HANDLERS,
            'level': 'INFO',
            'propagate': False,
        },
        'euro_terceros': {
            'handlers': LOGGING_HANDLERS,
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# =========================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO
# =========================================
# Configuración segura usando variables de entorno
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'EURO Sistema <noreply@euroterceros.com>')

# Validación de configuración de correo
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        "⚠️  CONFIGURACIÓN DE CORREO INCOMPLETA: "
        "Asegúrate de definir EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en tu archivo .env"
    )

# =========================================
# DESTINATARIOS DE CORREOS DE TERCEROS
# =========================================
# Obtener destinatarios desde variables de entorno
_destinatarios_env = os.getenv('DESTINATARIOS_CORREOS_TERCEROS', '')
if _destinatarios_env:
    EMAILS_PREDETERMINADOS = [email.strip() for email in _destinatarios_env.split(',') if email.strip()]
else:
    # ⚠️ No hay valores por defecto - DEBE configurarse en .env
    EMAILS_PREDETERMINADOS = []
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        "⚠️  DESTINATARIOS_CORREOS_TERCEROS no configurado en .env. "
        "Los correos no se enviarán hasta configurar esta variable."
    )

# Opcional: Destinatarios para notificaciones
_notificaciones_env = os.getenv('DESTINATARIOS_NOTIFICACIONES', '')
if _notificaciones_env:
    EMAILS_NOTIFICACIONES = [email.strip() for email in _notificaciones_env.split(',') if email.strip()]
else:
    EMAILS_NOTIFICACIONES = []

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_SECONDS = 3600
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
