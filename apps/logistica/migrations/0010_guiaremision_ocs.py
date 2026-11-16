from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistica', '0009_orden_compra_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='guiaremision',
            name='ocs',
            field=models.ManyToManyField(blank=True, related_name='guias_remision', to='logistica.ordencompralog'),
        ),
    ]
