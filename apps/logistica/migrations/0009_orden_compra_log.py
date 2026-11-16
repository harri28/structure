from decimal import Decimal
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistica', '0008_proveedor_referencia'),
        ('proyectos', '0001_initial'),
        ('presupuesto', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrdenCompraLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=30, verbose_name='N° Orden')),
                ('fecha_entrega', models.DateField(verbose_name='Fecha de entrega esperada')),
                ('tipo_pago', models.CharField(
                    choices=[('EFECTIVO', 'Efectivo'), ('TRANSFERENCIA', 'Transferencia'), ('CREDITO', 'Crédito')],
                    default='EFECTIVO', max_length=20, verbose_name='Tipo de pago',
                )),
                ('numero_factura', models.CharField(blank=True, max_length=50, verbose_name='N° de factura')),
                ('costo_envio', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12, verbose_name='Costo de envío')),
                ('observaciones', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ordenes_compra_creadas',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('proveedor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ordenes_compra',
                    to='logistica.proveedor',
                )),
                ('proyecto', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ordenes_compra_log',
                    to='proyectos.proyecto',
                )),
            ],
            options={
                'verbose_name': 'Orden de Compra',
                'verbose_name_plural': 'Órdenes de Compra',
                'ordering': ['-created_at'],
                'unique_together': {('proyecto', 'numero')},
            },
        ),
        migrations.CreateModel(
            name='DetalleOrdenCompraLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descripcion', models.CharField(max_length=400)),
                ('unidad', models.CharField(blank=True, max_length=20)),
                ('cantidad', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=12)),
                ('precio_unitario', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=12)),
                ('insumo', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='en_ordenes_compra',
                    to='presupuesto.insumopresupuesto',
                )),
                ('orden', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detalles',
                    to='logistica.ordencompralog',
                )),
            ],
            options={'ordering': ['id']},
        ),
    ]
