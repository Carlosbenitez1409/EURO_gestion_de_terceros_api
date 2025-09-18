from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def api_root(request):
    """
    Vista principal de la API que muestra información sobre los endpoints disponibles
    """
    return Response({
        "message": "EURO Sistema de Gestión de Terceros - API REST",
        "version": "1.0.0",
        "status": "operativo",
        "endpoints": {
            "authentication": {
                "login": "/api/auth/login/",
                "refresh": "/api/auth/refresh/",
                "verify": "/api/auth/verify/",
                "me": "/api/auth/me/"
            },
            "terceros": {
                "list": "/api/terceros/ (AUTH REQUIRED)",
                "create_public": "/api/terceros/ (PUBLIC - NO AUTH)",
                "create_authenticated": "/api/terceros/ (AUTH REQUIRED)",
                "detail": "/api/terceros/{id}/ (AUTH REQUIRED)",
                "update": "/api/terceros/{id}/ (AUTH REQUIRED)",
                "delete": "/api/terceros/{id}/ (AUTH REQUIRED)",
                "stats": "/api/terceros/stats/ (AUTH REQUIRED)",
                "aprobar": "/api/terceros/{id}/aprobar/ (AUTH REQUIRED)",
                "rechazar": "/api/terceros/{id}/rechazar/ (AUTH REQUIRED)"
            },
            "dashboard": {
                "metrics": "/api/dashboard/metrics/ (AUTH REQUIRED)",
                "main": "/api/dashboard/main/ (AUTH REQUIRED)"
            },
            "admin": "/admin/"
        },
        "documentation": {
            "authentication": "Utiliza JWT tokens. Obtén tu token en /api/auth/login/ con username y password",
            "authorization": "Incluye el header: Authorization: Bearer <tu_token>",
            "roles": ["procesos", "comercial", "gestion_humana"],
            "public_registration": {
                "endpoint": "POST /api/terceros/",
                "description": "Registro público para proveedores externos (sin autenticación)",
                "required_fields": ["tipo_documento", "numero_documento", "tipo_persona", "nombres", "email"],
                "security": "Rate limited: máximo 5 registros por IP cada 15 minutos",
                "response": "Información de confirmación y pasos siguientes"
            },
            "documentation_url": "/docs/"
        }
    })
