from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.models import User

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def form_options(request):
    """
    Endpoint para obtener las opciones de los campos select del formulario
    """
    options = {
        'roles': [
            {'value': choice[0], 'label': str(choice[1])} 
            for choice in User.RoleChoices.choices
        ],
        'tipos_documento': [
            {'value': choice[0], 'label': str(choice[1])} 
            for choice in User.DocumentTypeChoices.choices
        ],
        'estados_empleado': [
            {'value': choice[0], 'label': str(choice[1])} 
            for choice in User.EstadoEmpleadoChoices.choices
        ]
    }
    
    return Response(options)
