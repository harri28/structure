from django import forms
from django.forms import inlineformset_factory
from .models import (
    Requerimiento, DetalleRequerimiento,
    Entrada, DetalleEntrada,
    Salida, DetalleSalida,
    Cotizacion, DetalleCotizacion,
    OrdenCompra, DetalleOrdenCompra,
)


class RequerimientoForm(forms.ModelForm):
    class Meta:
        model = Requerimiento
        fields = ['numero', 'fecha', 'tipo', 'solicitante', 'estado', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }


class DetalleRequerimientoForm(forms.ModelForm):
    class Meta:
        model = DetalleRequerimiento
        fields = ['producto', 'cantidad', 'unidad', 'observacion']
        widgets = {
            'producto': forms.Select(attrs={'class': 'producto-select'}),
        }


DetalleRequerimientoFormSet = inlineformset_factory(
    Requerimiento, DetalleRequerimiento,
    form=DetalleRequerimientoForm,
    extra=3, can_delete=True,
)


class EntradaForm(forms.ModelForm):
    class Meta:
        model = Entrada
        fields = ['requerimiento', 'serie', 'numero_guia', 'fecha', 'proveedor', 'descripcion', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, proyecto=None, **kwargs):
        super().__init__(*args, **kwargs)
        if proyecto:
            self.fields['requerimiento'].queryset = proyecto.requerimientos.all()
        self.fields['requerimiento'].required = False


class DetalleEntradaForm(forms.ModelForm):
    class Meta:
        model = DetalleEntrada
        fields = ['producto', 'cantidad', 'precio_unitario', 'unidad']


DetalleEntradaFormSet = inlineformset_factory(
    Entrada, DetalleEntrada,
    form=DetalleEntradaForm,
    extra=3, can_delete=True,
)


class SalidaForm(forms.ModelForm):
    class Meta:
        model = Salida
        fields = ['numero', 'fecha', 'destino', 'responsable', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }


class DetalleSalidaForm(forms.ModelForm):
    class Meta:
        model = DetalleSalida
        fields = ['producto', 'cantidad', 'precio_unitario', 'unidad']


DetalleSalidaFormSet = inlineformset_factory(
    Salida, DetalleSalida,
    form=DetalleSalidaForm,
    extra=3, can_delete=True,
)


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ['numero', 'fecha', 'proveedor', 'estado', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }


class DetalleCotizacionForm(forms.ModelForm):
    class Meta:
        model = DetalleCotizacion
        fields = ['producto', 'cantidad', 'precio_unitario', 'unidad']


DetalleCotizacionFormSet = inlineformset_factory(
    Cotizacion, DetalleCotizacion,
    form=DetalleCotizacionForm,
    extra=3, can_delete=True,
)


class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = ['numero', 'fecha', 'proveedor', 'requerimiento', 'cotizacion',
                  'estado', 'plazo_entrega', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, proyecto=None, **kwargs):
        super().__init__(*args, **kwargs)
        if proyecto:
            self.fields['requerimiento'].queryset = proyecto.requerimientos.all()
            self.fields['cotizacion'].queryset = proyecto.cotizaciones.all()
        self.fields['requerimiento'].required = False
        self.fields['cotizacion'].required = False


class DetalleOrdenCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleOrdenCompra
        fields = ['producto', 'cantidad', 'precio_unitario', 'unidad']


DetalleOrdenCompraFormSet = inlineformset_factory(
    OrdenCompra, DetalleOrdenCompra,
    form=DetalleOrdenCompraForm,
    extra=3, can_delete=True,
)
