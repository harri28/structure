from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0005_maquinaria_remove_tipo'),
        ('proyectos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Liquidacion',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero',     models.PositiveIntegerField()),
                ('periodo',    models.DateField()),
                ('estado',     models.CharField(choices=[('ABIERTA', 'Abierta'), ('CERRADA', 'Cerrada')], default='ABIERTA', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('maquinaria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liquidaciones', to='maquinaria.maquinaria')),
                ('proyecto',   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liquidaciones_maq', to='proyectos.proyecto')),
            ],
            options={
                'verbose_name': 'Liquidación',
                'verbose_name_plural': 'Liquidaciones',
                'ordering': ['-periodo', 'maquinaria__codigo'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='liquidacion',
            unique_together={('maquinaria', 'numero')},
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='liquidacion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partes', to='maquinaria.liquidacion', verbose_name='Liquidación'),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='numero_parte',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='N° de parte'),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='combustible',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Combustible (gal)'),
        ),
    ]
