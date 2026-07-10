from django import forms
from .models import TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla, RegistroDiario, RegistroMaquinaria


class TipoPersonalForm(forms.ModelForm):
    class Meta:
        model  = TipoPersonal
        fields = ['codigo', 'nombre', 'costo_hora', 'activo']
        widgets = {
            'codigo':     forms.TextInput(attrs={'class': 'form-control'}),
            'nombre':     forms.TextInput(attrs={'class': 'form-control'}),
            'costo_hora': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'activo':     forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MaquinariaForm(forms.ModelForm):
    class Meta:
        model  = Maquinaria
        fields = [
            'codigo', 'nombre', 'tipo_equipo', 'marca', 'modelo', 'placa',
            'costo', 'modalidad_costo', 'costo_hora',
            'propietario', 'operador',
            'fecha_llegada', 'fecha_reinicio', 'fecha_salida_obra',
            'activo',
        ]
        widgets = {
            'codigo':          forms.TextInput(attrs={'class': 'form-control', 'readonly': True, 'style': 'background:#f8f9fa'}),
            'nombre':          forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_equipo':     forms.Select(attrs={'class': 'form-select'}),
            'marca':           forms.TextInput(attrs={'class': 'form-control'}),
            'modelo':          forms.TextInput(attrs={'class': 'form-control'}),
            'placa':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ABC-123'}),
            'costo':           forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'modalidad_costo': forms.Select(attrs={'class': 'form-select'}),
            'costo_hora':      forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001', 'min': '0'}),
            'propietario':     forms.TextInput(attrs={'class': 'form-control'}),
            'operador':        forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_llegada':   forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_reinicio':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_salida_obra': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'activo':          forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['tipo_equipo', 'modalidad_costo']:
            self.fields[f].required = False


class CuadrillaForm(forms.ModelForm):
    class Meta:
        model  = Cuadrilla
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre':      forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'activo':      forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class IntegranteCuadrillaForm(forms.ModelForm):
    class Meta:
        model  = IntegranteCuadrilla
        fields = ['tipo_personal', 'cantidad']
        widgets = {
            'tipo_personal': forms.Select(attrs={'class': 'form-select'}),
            'cantidad':      forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, cuadrilla=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if cuadrilla:
            ya = cuadrilla.integrantes.values_list('tipo_personal_id', flat=True)
            self.fields['tipo_personal'].queryset = TipoPersonal.objects.filter(activo=True).exclude(pk__in=ya)
        else:
            self.fields['tipo_personal'].queryset = TipoPersonal.objects.filter(activo=True)


class RegistroDiarioForm(forms.ModelForm):
    class Meta:
        model  = RegistroDiario
        fields = ['fecha', 'partida', 'cuadrilla', 'horas', 'observacion']
        widgets = {
            'fecha':       forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'partida':     forms.Select(attrs={'class': 'form-select'}),
            'cuadrilla':   forms.Select(attrs={'class': 'form-select'}),
            'horas':       forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, proyecto=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Count
        from apps.presupuesto.models import Partida
        if proyecto:
            self.fields['partida'].queryset = (
                Partida.objects
                .annotate(n_hijos=Count('hijos'))
                .filter(presupuesto__proyecto=proyecto, n_hijos=0)
                .order_by('orden')
            )
        self.fields['partida'].required  = False
        self.fields['partida'].empty_label = '— Sin partida —'
        self.fields['cuadrilla'].queryset = Cuadrilla.objects.filter(activo=True)


class RegistroMaquinariaForm(forms.ModelForm):
    class Meta:
        model  = RegistroMaquinaria
        fields = [
            'maquinaria', 'fecha', 'hora_entrada', 'hora_salida',
            'operador', 'insumo', 'partida', 'observacion',
        ]
        widgets = {
            'maquinaria':   forms.Select(attrs={'class': 'form-select'}),
            'fecha':        forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_entrada': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_salida':  forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'operador':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del operador / conductor'}),
            'insumo':       forms.Select(attrs={'class': 'form-select'}),
            'partida':      forms.Select(attrs={'class': 'form-select'}),
            'observacion':  forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, proyecto=None, maquinaria=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Count
        from apps.presupuesto.models import Partida, InsumoPresupuesto
        self.fields['maquinaria'].queryset    = Maquinaria.objects.filter(activo=True)
        self.fields['maquinaria'].empty_label = '— Seleccionar máquina —'
        if maquinaria:
            self.fields['maquinaria'].initial  = maquinaria
            self.fields['maquinaria'].required = True
        if proyecto:
            self.fields['partida'].queryset = (
                Partida.objects
                .annotate(n_hijos=Count('hijos'))
                .filter(presupuesto__proyecto=proyecto, n_hijos=0)
                .order_by('orden')
            )
            self.fields['insumo'].queryset = (
                InsumoPresupuesto.objects
                .filter(presupuesto__proyecto=proyecto)
                .order_by('codigo')
            )
        else:
            self.fields['insumo'].queryset = InsumoPresupuesto.objects.none()
        self.fields['partida'].required    = False
        self.fields['partida'].empty_label = '— Sin partida —'
        self.fields['insumo'].required     = False
        self.fields['insumo'].empty_label  = '— Sin insumo —'
        self.fields['hora_entrada'].required = False
        self.fields['hora_salida'].required  = False
