from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0017_avance_mensual_incidencia_obra'),
    ]

    operations = [
        migrations.AlterField(
            model_name='avancemensual',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='incidenciaobra',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
