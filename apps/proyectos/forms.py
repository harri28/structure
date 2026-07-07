from django import forms
from .models import Proyecto


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['codigo', 'nombre', 'cliente', 'ubicacion', 'responsable',
                  'fecha_inicio', 'fecha_fin', 'plazo_dias', 'estado', 'descripcion']
        widgets = {
            'codigo':      forms.TextInput(attrs={'class': 'form-control', 'readonly': True, 'style': 'background:#f8f9fa'}),
            'nombre':      forms.TextInput(attrs={'class': 'form-control'}),
            'cliente':     forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion':   forms.TextInput(attrs={'class': 'form-control'}),
            'responsable': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_fecha_inicio'}, format='%Y-%m-%d'),
            'fecha_fin':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_fecha_fin'}, format='%Y-%m-%d'),
            'plazo_dias':  forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_plazo_dias', 'min': '1', 'placeholder': 'Días'}),
            'estado':      forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plazo_dias'].required = False
