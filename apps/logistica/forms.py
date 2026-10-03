from django import forms
from django.forms import inlineformset_factory
from datetime import date
from .models import GuiaRemision, DetalleGuia, Transportista

_ctrl  = {'class': 'form-control form-control-sm'}
_sel   = {'class': 'form-select form-select-sm'}
_date  = {'class': 'form-control form-control-sm', 'type': 'date'}
_num   = {'class': 'form-control form-control-sm text-end'}
_area  = {'class': 'form-control form-control-sm', 'rows': '2'}


class TransportistaForm(forms.ModelForm):
    class Meta:
        model  = Transportista
        fields = ['ruc', 'razon_social', 'contacto', 'telefono', 'email', 'activo']
        widgets = {
            'ruc':          forms.TextInput(attrs={**_ctrl, 'placeholder': '20XXXXXXXXX'}),
            'razon_social': forms.TextInput(attrs=_ctrl),
            'contacto':     forms.TextInput(attrs=_ctrl),
            'telefono':     forms.TextInput(attrs=_ctrl),
            'email':        forms.EmailInput(attrs=_ctrl),
            'activo':       forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GuiaRemisionForm(forms.ModelForm):
    class Meta:
        model  = GuiaRemision
        fields = [
            'numero', 'fecha_emision', 'fecha_traslado', 'motivo', 'motivo_otro',
            'origen', 'destino',
            'transportista', 'placa', 'conductor', 'licencia',
            'peso_kg', 'observaciones',
        ]
        widgets = {
            'numero':        forms.TextInput(attrs={**_ctrl, 'placeholder': 'T001-000001'}),
            'fecha_emision': forms.DateInput(attrs=_date, format='%Y-%m-%d'),
            'fecha_traslado':forms.DateInput(attrs=_date, format='%Y-%m-%d'),
            'motivo':        forms.Select(attrs=_sel),
            'motivo_otro':   forms.TextInput(attrs={**_ctrl, 'placeholder': 'Escribe el motivo del traslado', 'maxlength': 200}),
            'origen':        forms.TextInput(attrs={**_ctrl, 'placeholder': 'Almacén central, Av. …'}),
            'destino':       forms.TextInput(attrs={**_ctrl, 'placeholder': 'Obra / destino'}),
            'transportista': forms.Select(attrs=_sel),
            'placa':         forms.TextInput(attrs={**_ctrl, 'placeholder': 'ABC-123'}),
            'conductor':     forms.TextInput(attrs=_ctrl),
            'licencia':      forms.TextInput(attrs=_ctrl),
            'peso_kg':       forms.NumberInput(attrs={**_num, 'step': '0.01'}),
            'observaciones': forms.Textarea(attrs=_area),
        }

    def clean(self):
        data = super().clean()
        if data.get('motivo') == 'OTRO':
            otro = (data.get('motivo_otro') or '').strip()
            if not otro:
                self.add_error('motivo_otro', 'Escribe el motivo del traslado.')
            data['motivo_otro'] = otro
        else:
            data['motivo_otro'] = ''
        return data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            hoy = date.today().strftime('%Y-%m-%d')
            self.initial.setdefault('fecha_emision',  hoy)
            self.initial.setdefault('fecha_traslado', hoy)
        self.fields['transportista'].queryset    = Transportista.objects.filter(activo=True)
        self.fields['transportista'].empty_label = '— Sin transportista —'


DetalleGuiaFormSet = inlineformset_factory(
    GuiaRemision, DetalleGuia,
    fields    = ['descripcion', 'unidad', 'cantidad'],
    extra     = 4,
    can_delete= True,
    widgets   = {
        'descripcion': forms.TextInput(attrs={**_ctrl, 'placeholder': 'Material / bien'}),
        'unidad':      forms.TextInput(attrs={**_ctrl, 'placeholder': 'und'}),
        'cantidad':    forms.NumberInput(attrs={**_num, 'step': '0.001'}),
    },
)
