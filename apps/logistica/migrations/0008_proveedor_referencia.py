from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistica', '0007_proveedor_sunat_campos'),
    ]

    operations = [
        migrations.AddField(
            model_name='proveedor',
            name='referencia',
            field=models.CharField(blank=True, max_length=300, verbose_name='Referencia'),
        ),
    ]
