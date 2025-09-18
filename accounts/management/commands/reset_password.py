from django.core.management.base import BaseCommand
from accounts.models import User

class Command(BaseCommand):
    help = 'Resetea la contraseña de un usuario'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Nombre de usuario')
        parser.add_argument('password', type=str, help='Nueva contraseña')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        
        try:
            user = User.objects.get(username=username)
            user.set_password(password)
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Contraseña actualizada para usuario: {username}')
            )
            
            # Verificar que funcione
            from django.contrib.auth import authenticate
            test_user = authenticate(username=username, password=password)
            if test_user:
                self.stdout.write('✅ Autenticación verificada exitosamente')
            else:
                self.stdout.write('❌ Error en la verificación')
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Usuario no encontrado: {username}')
            )
