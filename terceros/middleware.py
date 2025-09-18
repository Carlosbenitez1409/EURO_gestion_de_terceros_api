import time
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

class PublicTerceroRateLimitMiddleware:
    """
    Middleware para rate limiting en endpoints públicos de terceros
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Solo aplicar rate limiting al endpoint público de creación de terceros
        if request.path == '/api/terceros/' and request.method == 'POST':
            client_ip = self.get_client_ip(request)
            
            # Verificar rate limit
            if not self.check_rate_limit(client_ip, request):
                logger.warning(f"Rate limit exceeded for IP {client_ip} on public tercero creation")
                return JsonResponse({
                    'error': 'Demasiadas solicitudes. Por favor, intente nuevamente en unos minutos.',
                    'detail': 'Rate limit exceeded for public registration'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Log del intento de registro público
            logger.info(f"Public tercero registration attempt from IP: {client_ip}")

        response = self.get_response(request)
        return response

    def get_client_ip(self, request):
        """Obtener la IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def check_rate_limit(self, ip, request):
        """
        Rate limiting: máximo 5 intentos por IP cada 15 minutos
        """
        cache_key = f"tercero_public_rate_limit_{ip}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            return False
        
        # Incrementar contador
        cache.set(cache_key, attempts + 1, 15 * 60)  # 15 minutos
        return True
