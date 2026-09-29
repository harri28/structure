from django import forms
from .models import (
    TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla,
    RegistroDiario, RegistroMaquinaria, Liquidacion,
    Trabajador, DocumentoTrabajador,
)


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
            'propietario_documento', 'propietario_razon_social',
            'propietario_celular', 'propietario_direccion',
            'operador',
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
            'propietario_documento':    forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'maxlength': '11', 'placeholder': 'DNI (8) o RUC (11)'}),
            'propietario_razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre o razón social'}),
            'propietario_celular':      forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'placeholder': 'Ej: 987654321'}),
            'propietario_direccion':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Jr. Los Pinos 123'}),
            'operador':        forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_llegada':   forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_reinicio':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_salida_obra': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
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


class TrabajadorForm(forms.ModelForm):
    class Meta:
        model  = Trabajador
        fields = [
            'nombres', 'apellidos', 'dni', 'tipo_personal',
            'telefono', 'direccion', 'fecha_nacimiento', 'fecha_ingreso',
            'foto', 'activo',
        ]
        widgets = {
            'nombres':           forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos':         forms.TextInput(attrs={'class': 'form-control'}),
            'dni':               forms.TextInput(attrs={'class': 'form-control', 'maxlength': 15, 'inputmode': 'numeric', 'placeholder': 'DNI'}),
            'tipo_personal':     forms.Select(attrs={'class': 'form-select'}),
            'telefono':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 987654321'}),
            'direccion':         forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_ingreso':     forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'foto':              forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'activo':            forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_personal'].queryset    = TipoPersonal.objects.filter(activo=True)
        self.fields['tipo_personal'].required    = False
        self.fields['tipo_personal'].empty_label = '— Sin cargo asignado —'
        for f in ['dni', 'telefono', 'direccion', 'fecha_nacimiento', 'fecha_ingreso', 'foto']:
            self.fields[f].required = False


class DocumentoTrabajadorForm(forms.ModelForm):
    class Meta:
        model  = DocumentoTrabajador
        fields = ['nombre', 'archivo']
        widgets = {
            'nombre':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: CV, DNI, Certificado SCTR, Antecedentes...'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class RegistroDiarioForm(forms.ModelForm):
    class Meta:
        model  = RegistroDiario
        fields = ['fecha', 'partida', 'cuadrilla', 'horas', 'observacion']
        widgets = {
            'fecha':       forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
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
            'fecha':        forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'hora_entrada': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'placeholder': 'Ej: 14015.4'}),
            'hora_salida':  forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'placeholder': 'Ej: 14022.4'}),
            'operador':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del operador / conductor'}),
            'insumo':       forms.Select(attrs={'class': 'form-select'}),
            'partida':      forms.Select(attrs={'class': 'form-select'}),
            'observacion':  forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, proyecto=None, maquinaria=None, validar_horometro=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Count
        from apps.presupuesto.models import Partida, InsumoPresupuesto
        self.validar_horometro = validar_horometro
        self.fields['maquinaria'].queryset    = Maquinaria.objects.filter(activo=True)
        self.fields['maquinaria'].empty_label = '— Seleccionar máquina —'
        if maquinaria:
            self.fields['maquinaria'].initial  = maquinaria
            self.fields['maquinaria'].required = True
            # Máquina fija por contexto (se entró desde la ficha de esa máquina): ya no
            # se elige por dropdown, viaja oculta y se muestra como texto de solo lectura.
            self.fields['maquinaria'].widget = forms.HiddenInput()
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

    def clean(self):
        cleaned = super().clean()
        if self.validar_horometro:
            maq     = cleaned.get('maquinaria')
            entrada = cleaned.get('hora_entrada')
            salida  = cleaned.get('hora_salida')

            # Dentro del mismo turno: la salida nunca puede ser menor a la entrada
            # (igual sí es válido — turno de 0 horas).
            if entrada is not None and salida is not None and salida < entrada:
                self.add_error('hora_salida', 'El horómetro de salida no puede ser menor al de entrada.')

            if maq and entrada is not None:
                from django.db.models import Max
                qs = RegistroMaquinaria.objects.filter(maquinaria=maq)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                ultimo_salida = qs.aggregate(m=Max('hora_salida'))['m']
                if ultimo_salida is not None and entrada <= ultimo_salida:
                    self.add_error(
                        'hora_entrada',
                        f'El horómetro de entrada debe ser mayor a {ultimo_salida} '
                        f'(último horómetro de salida registrado para esta máquina).'
                    )
        return cleaned


class ParteForm(forms.ModelForm):
    """Formulario simplificado para registrar un parte diario dentro de una liquidación."""
    class Meta:
        model  = RegistroMaquinaria
        fields = ['fecha', 'hora_entrada', 'hora_salida', 'horas', 'combustible', 'insumo', 'partida', 'observacion']
        widgets = {
            'fecha':        forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'),
            'hora_entrada': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.1', 'min': '0', 'placeholder': 'Horómetro ini'}),
            'hora_salida':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.1', 'min': '0', 'placeholder': 'Horómetro fin'}),
            'horas':        forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.5', 'min': '0'}),
            'combustible':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0', 'placeholder': 'gal'}),
            'insumo':       forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'partida':      forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'observacion':  forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Opcional'}),
        }

    def __init__(self, proyecto=None, maquinaria=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Count
        from apps.presupuesto.models import Partida, InsumoPresupuesto
        self.fields['hora_entrada'].required = False
        self.fields['hora_salida'].required  = False
        self.fields['horas'].required        = False
        self.fields['combustible'].required  = False
        self.fields['insumo'].required       = False
        self.fields['insumo'].empty_label    = '— Sin insumo —'
        self.fields['partida'].required      = False
        self.fields['partida'].empty_label   = '— Sin partida —'
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
            self.fields['insumo'].queryset  = InsumoPresupuesto.objects.none()
            self.fields['partida'].queryset = Partida.objects.none()
