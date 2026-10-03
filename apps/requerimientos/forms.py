from datetime import date
from django import forms
from django.forms import inlineformset_factory
from .models import Requerimiento, DetalleRequerimiento


class RequerimientoForm(forms.ModelForm):
    class Meta:
        model = Requerimiento
        fields = ['fecha', 'obra', 'solicitante', 'cargo_solicitante', 'sector_obra']
        widgets = {
            'fecha':             forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'obra':              forms.TextInput(attrs={'class': 'form-control'}),
            'solicitante':       forms.TextInput(attrs={'class': 'form-control'}),
            'cargo_solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'sector_obra':       forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones':     forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # `proyecto` kwarg se acepta por compatibilidad con las vistas (crear/solicitar/editar)
        # aunque ya no filtre choices — el solicitante ahora es texto libre pre-cargado.
        kwargs.pop('proyecto', None)
        super().__init__(*args, **kwargs)
        if not self.data.get('fecha') and not (self.instance.pk and self.instance.fecha):
            self.initial.setdefault('fecha', date.today().strftime('%Y-%m-%d'))


class DetalleRequerimientoForm(forms.ModelForm):
    class Meta:
        model = DetalleRequerimiento
        fields = ['insumo', 'descripcion', 'cantidad', 'unidad', 'cantidad_requerida', 'justificacion', 'observacion']
        widgets = {
            'insumo': forms.HiddenInput(),
            'descripcion': forms.HiddenInput(),
        }

    def __init__(self, *args, modo_ajuste=False, **kwargs):
        self.modo_ajuste = modo_ajuste
        super().__init__(*args, **kwargs)
        self.fields['cantidad'].required = False
        self.fields['cantidad_requerida'].required = False
        self.fields['justificacion'].required = False
        self.fields['unidad'].required = False

    def clean_cantidad(self):
        val = self.cleaned_data.get('cantidad')
        return val if val is not None else 0

    def clean_cantidad_requerida(self):
        val = self.cleaned_data.get('cantidad_requerida')
        return val if val is not None else 0

    def clean(self):
        data = super().clean()
        if self.cleaned_data.get('DELETE'):
            return data
        cantidad = data.get('cantidad') or 0
        cant_req = data.get('cantidad_requerida') or 0
        # Un ítem sin cantidad a solicitar llegaría a Logística como 0: se exige > 0.
        if cant_req <= 0:
            self.add_error('cantidad_requerida', 'Ingresa la cantidad a solicitar (mayor a 0).')
            return data
        # En modo ajuste (adicional) se permite exceder lo presupuestado.
        if not self.modo_ajuste and cantidad and cant_req > cantidad:
            self.add_error(
                'cantidad_requerida',
                f'No puede superar la cantidad presupuestada ({cantidad}).',
            )
        return data


DetalleRequerimientoFormSet = inlineformset_factory(
    Requerimiento, DetalleRequerimiento,
    form=DetalleRequerimientoForm,
    extra=1, can_delete=True,
)
