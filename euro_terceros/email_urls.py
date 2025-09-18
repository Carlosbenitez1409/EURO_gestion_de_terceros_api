"""
URLs para el sistema de correos de terceros
"""
from django.urls import path
from . import email_views

urlpatterns = [
    # Configuración del sistema de correos
    path('configuracion/', email_views.configuracion_email, name='email-configuracion'),
    
    # Envío de correos de terceros
    path('tercero/<str:tercero_id>/enviar/', email_views.enviar_correo_tercero, name='email-tercero-enviar'),
    
    # Vista previa de correos
    path('tercero/<str:tercero_id>/preview/', email_views.preview_correo_tercero, name='email-tercero-preview'),
]
