from rest_framework import serializers

from apps.proyectos.models import Proyecto
from apps.presupuesto.models import InsumoPresupuesto
from apps.requerimientos.models import Requerimiento, DetalleRequerimiento


class ProyectoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Proyecto
        fields = ['id', 'codigo', 'nombre', 'sector', 'estado']


class InsumoSerializer(serializers.ModelSerializer):
    """Insumo + saldo global disponible calculado en el momento."""
    saldo_disponible = serializers.SerializerMethodField()

    class Meta:
        model  = InsumoPresupuesto
        fields = [
            'id', 'codigo', 'descripcion', 'unidad',
            'cantidad_total', 'cantidad',
            'saldo_disponible',
        ]

    def get_saldo_disponible(self, obj):
        from apps.presupuesto.services import saldo_disponible_insumo
        return str(saldo_disponible_insumo(obj))


class DetalleRequerimientoSerializer(serializers.ModelSerializer):
    insumo_id   = serializers.PrimaryKeyRelatedField(
        source='insumo', queryset=InsumoPresupuesto.objects.all(),
        allow_null=True, required=False,
    )
    insumo_descripcion = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = DetalleRequerimiento
        fields = [
            'id', 'insumo_id', 'insumo_descripcion',
            'codigo', 'descripcion', 'unidad',
            'cantidad', 'cantidad_requerida', 'cantidad_aprobada',
            'justificacion', 'observacion',
        ]

    def get_insumo_descripcion(self, obj):
        if obj.insumo:
            return obj.insumo.descripcion
        return obj.descripcion


class RequerimientoSerializer(serializers.ModelSerializer):
    detalles = DetalleRequerimientoSerializer(many=True, required=False)
    # Campo exclusivo de entrada — no se guarda en el modelo. Lo lee el view
    # para decidir si crear/enviar o idempotencia.
    client_uuid = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    accion      = serializers.ChoiceField(
        choices=['borrador', 'enviar'],
        write_only=True, required=False, default='borrador',
    )

    class Meta:
        model  = Requerimiento
        fields = [
            'id', 'numero', 'numero_global', 'fecha',
            'origen', 'tipo', 'obra', 'solicitante', 'cargo_solicitante',
            'sector_obra', 'estado', 'observaciones',
            'es_ajuste', 'created_at',
            'detalles',
            'client_uuid', 'accion',
        ]
        read_only_fields = [
            'id', 'numero', 'numero_global', 'origen',
            'estado', 'created_at',
        ]
