from django import forms
from .models import Tercero

class TerceroForm(forms.ModelForm):
    documentos = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}), required=False)

    class Meta:
        model = Tercero
        fields = [
            'tipo_persona', 'tipo_documento', 'numero_documento', 
            'nombres', 'apellidos', 'razon_social', 'email', 'telefono', 
            'direccion', 'ciudad', 'departamento'
        ]
