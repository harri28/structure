from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0015_cambio_nombre_insumo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='presupuesto',
            name='igv_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('0'), max_digits=6,
                verbose_name='IGV (%)',
            ),
        ),
    ]
