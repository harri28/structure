from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistica', '0011_oc_soft_delete'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detalleordencompralog',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='ordencompralog',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
