from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Notificaciones'
    
    def ready(self):
        # Importar señales cuando la app esté lista
        import notifications.signal_handlers
