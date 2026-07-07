from datetime import date
from django import forms
from django.forms import inlineformset_factory
from .models import (
    Entrada, DetalleEntrada,
    Salida, DetalleSalida,
    Cotizacion, DetalleCotizacion,
    OrdenCompra, DetalleOrdenCompra,
)
from apps.requerimientos.models import Requerimiento


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
        fields = ['insumo', 'descripcion', 'cantidad', 'precio_unitario', 'unidad']
        widgets = {
            'insumo': forms.HiddenInput(),
            'descripcion': forms.HiddenInput(),
        }


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
        fields = ['insumo', 'descripcion', 'cantidad', 'precio_unitario', 'unidad']
        widgets = {
            'insumo': forms.HiddenInput(),
            'descripcion': forms.HiddenInput(),
        }


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
        fields = ['insumo', 'descripcion', 'cantidad', 'precio_unitario', 'unidad']
        widgets = {
            'insumo': forms.HiddenInput(),
            'descripcion': forms.HiddenInput(),
        }


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
        fields = ['insumo', 'descripcion', 'cantidad', 'precio_unitario', 'unidad']
        widgets = {
            'insumo': forms.HiddenInput(),
            'descripcion': forms.HiddenInput(),
        }


DetalleOrdenCompraFormSet = inlineformset_factory(
    OrdenCompra, DetalleOrdenCompra,
    form=DetalleOrdenCompraForm,
    extra=3, can_delete=True,
)
