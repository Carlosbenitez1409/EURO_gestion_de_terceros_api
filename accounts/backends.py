from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class UsernameOrEmailBackend(ModelBackend):
    """
    Backend de autenticación que permite login SOLO con username (no email)
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        try:
            # Buscar usuario por username o email (case insensitive)
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            # Ejecutar el default password hasher para evitar timing attacks
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Si hay múltiples usuarios, usar el primero que coincida
            user = User.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()
        
        # Verificar contraseña y que el usuario pueda autenticarse
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
    
    def get_user(self, user_id):
        """
        Obtiene un usuario por su ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
    
    def user_can_authenticate(self, user):
        """
        Verifica si el usuario puede autenticarse
        """
        is_active = getattr(user, 'is_active', None)
        return is_active or is_active is None