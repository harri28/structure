from datetime import date
from django import forms
from .models import (
    TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla,
    RegistroMaquinaria, Liquidacion,
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
            'codigo':          forms.TextInput(attrs={'class': 'form-control form-control-sm', 'readonly': True, 'style': 'background:#f8f9fa'}),
            'nombre':          forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'tipo_equipo':     forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'marca':           forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'modelo':          forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'placa':           forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: ABC-123'}),
            'costo':           forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0'}),
            'modalidad_costo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'costo_hora':      forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001', 'min': '0'}),
            'propietario_documento':    forms.TextInput(attrs={'class': 'form-control form-control-sm', 'inputmode': 'numeric', 'maxlength': '11', 'placeholder': 'DNI (8) o RUC (11)'}),
            'propietario_razon_social': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nombre o razón social'}),
            'propietario_celular':      forms.TextInput(attrs={'class': 'form-control form-control-sm', 'inputmode': 'numeric', 'placeholder': 'Ej: 987654321'}),
            'propietario_direccion':    forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: Jr. Los Pinos 123'}),
            'operador':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'fecha_llegada':   forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_reinicio':  forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_salida_obra': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'),
            'activo':          forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['tipo_equipo', 'modalidad_costo']:
            self.fields[f].required = False
        # Permitir valores libres (no limitados a las choices hardcodeadas) para
        # que el usuario pueda crear nuevos valores desde el modal (botón "Nueva").
        self.fields['tipo_equipo']     = forms.CharField(required=False, max_length=50,
            widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'list': 'dl-tipo-equipo'}))
        self.fields['modalidad_costo'] = forms.CharField(required=False, max_length=50,
            widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'list': 'dl-modalidad'}))
        self.fields['marca'] = forms.CharField(required=False, max_length=100,
            widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'list': 'dl-marca'}))


class CuadrillaForm(forms.ModelForm):
    class Meta:
        model  = Cuadrilla
        fields = ['nombre', 'descripcion', 'capataz', 'ubicacion',
                  'fecha_inicio', 'fecha_fin', 'activo']
        widgets = {
            'nombre':       forms.TextInput(attrs={'class': 'form-control',
                                'placeholder': 'Ej: Frente A - Movimiento de tierras'}),
            'descripcion':  forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                'placeholder': 'Alcance, tareas, notas del frente'}),
            'capataz':      forms.Select(attrs={'class': 'form-select'}),
            'ubicacion':    forms.TextInput(attrs={'class': 'form-control',
                                'placeholder': 'Ej: Torre A nivel 3, acceso norte'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'activo':       forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, proyecto=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Trabajador.objects.filter(activo=True)
        if proyecto:
            qs = qs.filter(proyecto=proyecto)
        self.fields['capataz'].queryset    = qs
        self.fields['capataz'].empty_label = '— Sin capataz asignado —'
        self.fields['capataz'].required    = False
        for name in ['descripcion', 'ubicacion', 'fecha_inicio', 'fecha_fin']:
            self.fields[name].required = False


class AgregarIntegranteForm(forms.Form):
    """Form para añadir un Trabajador a una Cuadrilla."""
    trabajador = forms.ModelChoiceField(
        queryset=Trabajador.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Trabajador',
        empty_label='— Selecciona un trabajador —',
    )

    def __init__(self, cuadrilla, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ya_asignados = cuadrilla.integrantes.values_list('trabajador_id', flat=True)
        self.fields['trabajador'].queryset = (
            Trabajador.objects
            .filter(proyecto=cuadrilla.proyecto, activo=True)
            .exclude(pk__in=ya_asignados)
            .order_by('apellidos', 'nombres')
        )


class TrabajadorForm(forms.ModelForm):
    class Meta:
        model  = Trabajador
        fields = [
            # Datos personales
            'nombres', 'apellidos', 'dni', 'fecha_nacimiento',
            'sexo', 'estado_civil', 'lugar_nacimiento',
            # Contacto
            'telefono', 'telefono2', 'email',
            'direccion', 'distrito', 'provincia', 'departamento',
            # Emergencia
            'emergencia_nombre', 'emergencia_parentesco', 'emergencia_telefono',
            # Laboral
            'tipo_personal', 'fecha_ingreso',
            'anios_experiencia', 'experiencia_descripcion',
            # Habilidades
            'habilidades',
            # Licencia
            'tiene_licencia', 'licencia_categoria', 'licencia_numero', 'licencia_vencimiento',
            # Maquinaria pesada
            'opera_maquinaria_pesada', 'maquinas_opera',
            # Seguridad social
            'regimen_pension', 'cuspp', 'tiene_essalud', 'tiene_sctr',
            'banco', 'cuenta_cci',
            # Archivos
            'foto', 'cv',
            # Observaciones
            'observaciones',
            # Control
            'activo',
        ]
        widgets = {
            # Datos personales
            'nombres':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan Carlos'}),
            'apellidos':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Pérez García'}),
            'dni':               forms.TextInput(attrs={'class': 'form-control', 'maxlength': 15, 'inputmode': 'numeric', 'placeholder': '8 dígitos'}),
            'fecha_nacimiento':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'sexo':              forms.Select(attrs={'class': 'form-select'}),
            'estado_civil':      forms.Select(attrs={'class': 'form-select'}),
            'lugar_nacimiento':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cajamarca'}),
            # Contacto
            'telefono':          forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'tel', 'placeholder': '9XXXXXXXX'}),
            'telefono2':         forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'tel', 'placeholder': 'Opcional'}),
            'email':             forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'direccion':         forms.TextInput(attrs={'class': 'form-control'}),
            'distrito':          forms.TextInput(attrs={'class': 'form-control'}),
            'provincia':         forms.TextInput(attrs={'class': 'form-control'}),
            'departamento':      forms.TextInput(attrs={'class': 'form-control'}),
            # Emergencia
            'emergencia_nombre':     forms.TextInput(attrs={'class': 'form-control'}),
            'emergencia_parentesco': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Esposa, hermano, madre...'}),
            'emergencia_telefono':   forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'tel'}),
            # Laboral
            'tipo_personal':         forms.Select(attrs={'class': 'form-select'}),
            'fecha_ingreso':         forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'anios_experiencia':     forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 70, 'placeholder': 'Ej: 5'}),
            'experiencia_descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                        'placeholder': 'Empresas, obras, cargos anteriores...'}),
            # Habilidades
            'habilidades':           forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                        'placeholder': 'Ej: albañilería, encofrado, soldadura 6G, operador grúa torre...'}),
            # Licencia
            'tiene_licencia':        forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'licencia_categoria':    forms.Select(attrs={'class': 'form-select'}),
            'licencia_numero':       forms.TextInput(attrs={'class': 'form-control'}),
            'licencia_vencimiento':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            # Maquinaria pesada
            'opera_maquinaria_pesada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'maquinas_opera':          forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                          'placeholder': 'Ej: retroexcavadora, cargador frontal, volquete...'}),
            # Seguridad social
            'regimen_pension':       forms.Select(attrs={'class': 'form-select'}),
            'cuspp':                 forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Si aplica (AFP)'}),
            'tiene_essalud':         forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tiene_sctr':            forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'banco':                 forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'BCP, BBVA, Interbank...'}),
            'cuenta_cci':            forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'maxlength': 25,
                                       'placeholder': '20 dígitos'}),
            # Archivos
            'foto':                  forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'cv':                    forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            # Observaciones
            'observaciones':         forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # Control
            'activo':                forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo nombres y apellidos son obligatorios; el resto es opcional
        obligatorios = {'nombres', 'apellidos'}
        for name, field in self.fields.items():
            if name not in obligatorios:
                field.required = False
        self.fields['tipo_personal'].queryset    = TipoPersonal.objects.filter(activo=True)
        self.fields['tipo_personal'].empty_label = '— Sin cargo asignado —'
        # Mostrar solo el nombre en el dropdown (sin el código técnico)
        self.fields['tipo_personal'].label_from_instance = lambda tp: tp.nombre


class DocumentoTrabajadorForm(forms.ModelForm):
    class Meta:
        model  = DocumentoTrabajador
        fields = ['nombre', 'archivo']
        widgets = {
            'nombre':  forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: CV, DNI, Certificado SCTR, Antecedentes...'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
        }


class RegistroMaquinariaForm(forms.ModelForm):
    class Meta:
        model  = RegistroMaquinaria
        fields = [
            'maquinaria', 'fecha', 'numero_parte', 'hora_inicio', 'hora_fin',
            'combustible', 'observacion',
        ]
        widgets = {
            'maquinaria':   forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'fecha':        forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'),
            'numero_parte': forms.NumberInput(attrs={'class': 'form-control form-control-sm fw-semibold', 'min': '1', 'style': 'color:#1d4ed8'}),
            'hora_inicio':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0', 'inputmode': 'numeric', 'placeholder': 'Ej: 20000'}),
            'hora_fin':     forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0', 'inputmode': 'numeric', 'placeholder': 'Ej: 20020'}),
            'combustible':  forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'observacion':  forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
        }

    def __init__(self, proyecto=None, maquinaria=None, validar_horometro=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial.setdefault('fecha', date.today().strftime('%Y-%m-%d'))
        self.validar_horometro = validar_horometro
        self._maquinaria_ctx   = maquinaria
        self.fields['maquinaria'].queryset    = Maquinaria.objects.filter(activo=True)
        self.fields['maquinaria'].empty_label = '— Seleccionar máquina —'
        if maquinaria:
            self.fields['maquinaria'].initial  = maquinaria
            self.fields['maquinaria'].required = True
            # Máquina fija por contexto (se entró desde la ficha): oculta.
            self.fields['maquinaria'].widget = forms.HiddenInput()
        self.fields['hora_inicio'].required = False
        self.fields['hora_fin'].required    = False
        self.fields['combustible'].required = False
        self.fields['numero_parte'].required = False  # si viene vacío, save() autocalcula

    def clean(self):
        cleaned = super().clean()
        if not self.validar_horometro:
            return cleaned
        ini = cleaned.get('hora_inicio')
        fin = cleaned.get('hora_fin')
        if ini is not None and fin is not None and fin < ini:
            self.add_error('hora_fin', 'El horómetro final no puede ser menor al inicial.')
        # El horómetro de la máquina nunca retrocede: el inicio del turno N
        # debe ser ≥ al horómetro final del turno N−1 (misma máquina).
        maq = cleaned.get('maquinaria') or self._maquinaria_ctx
        if maq and ini is not None:
            qs = (RegistroMaquinaria.objects
                  .filter(maquinaria=maq, hora_fin__isnull=False)
                  .order_by('-numero_turno', '-pk'))
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            previo = qs.first()
            if previo and previo.hora_fin is not None and ini < previo.hora_fin:
                self.add_error(
                    'hora_inicio',
                    f'El horómetro inicial debe ser ≥ {previo.hora_fin} '
                    f'(horómetro final del Turno {previo.numero_turno}).'
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
        if not self.instance.pk:
            self.initial.setdefault('fecha', date.today().strftime('%Y-%m-%d'))
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

    def clean(self):
        cleaned = super().clean()
        entrada = cleaned.get('hora_entrada')
        salida  = cleaned.get('hora_salida')
        if entrada is not None and salida is not None and salida < entrada:
            self.add_error('hora_salida', 'El horómetro de salida no puede ser menor al de entrada.')
        return cleaned
