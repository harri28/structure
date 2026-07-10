from datetime import date
from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from .models import Requerimiento, DetalleRequerimiento


class RequerimientoForm(forms.ModelForm):
    class Meta:
        model = Requerimiento
        fields = ['fecha', 'obra', 'solicitante', 'cargo_solicitante', 'sector_obra']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        proyecto = kwargs.pop('proyecto', None)
        super().__init__(*args, **kwargs)
        if not self.data.get('fecha') and not (self.instance.pk and self.instance.fecha):
            self.initial.setdefault('fecha', date.today().strftime('%Y-%m-%d'))
        if proyecto is not None:
            user_ids = proyecto.miembros.values_list('usuario_id', flat=True)
            users = User.objects.filter(pk__in=user_ids, is_active=True).order_by('first_name', 'last_name', 'username')
        else:
            users = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        choices = [('', '— Seleccionar solicitante —')]
        for u in users:
            nombre = u.get_full_name() or u.username
            choices.append((nombre, nombre))
        self.fields['solicitante'] = forms.ChoiceField(
            choices=choices, required=False,
            widget=forms.Select(attrs={'class': 'form-select'}),
        )


class DetalleRequerimientoForm(forms.ModelForm):
    class Meta:
        model = DetalleRequerimiento
        fields = ['insumo', 'descripcion', 'cantidad', 'unidad', 'cantidad_requerida', 'justificacion', 'observacion']
        widgets = {
            'insumo': forms.HiddenInput(),
            'descripcion': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
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
        if cantidad and cant_req > cantidad:
            self.add_error(
                'cantidad_requerida',
                f'No puede superar la cantidad presupuestada ({cantidad}).',
            )
        return data


DetalleRequerimientoFormSet = inlineformset_factory(
    Requerimiento, DetalleRequerimiento,
    form=DetalleRequerimientoForm,
    extra=3, can_delete=True,
)
