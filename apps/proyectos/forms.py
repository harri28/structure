from django import forms
from .models import Proyecto


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['codigo', 'nombre', 'cliente', 'ubicacion', 'responsable',
                  'fecha_inicio', 'fecha_fin', 'estado', 'descripcion']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }
