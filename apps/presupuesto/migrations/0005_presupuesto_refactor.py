import django.db.models.deletion
from django.db import migrations, models


def migrate_presupuestos(apps, schema_editor):
    """Convert ADICIONAL/DEDUCTIVO Presupuesto records to Modificacion+PartidaModificacion.
    Keep only one CONTRACTUAL per project (latest wins).
    """
    Presupuesto = apps.get_model('presupuesto', 'Presupuesto')
    Modificacion = apps.get_model('presupuesto', 'Modificacion')
    PartidaModificacion = apps.get_model('presupuesto', 'PartidaModificacion')
    Partida = apps.get_model('presupuesto', 'Partida')

    proyecto_ids = list(Presupuesto.objects.values_list('proyecto_id', flat=True).distinct())

    for proyecto_id in proyecto_ids:
        num_adicional = 0
        num_deductivo = 0
        to_delete = []

        pres_list = list(Presupuesto.objects.filter(proyecto_id=proyecto_id))

        for pres in pres_list:
            if pres.tipo not in ('ADICIONAL', 'DEDUCTIVO'):
                continue

            if pres.tipo == 'ADICIONAL':
                num_adicional += 1
                subtipo = 'ADICIONAL'
                num = num_adicional
            else:
                num_deductivo += 1
                subtipo = 'DEDUCTIVO'
                num = num_deductivo

            mod = Modificacion.objects.create(
                proyecto_id=proyecto_id,
                tipo=pres.tipo,
                numero=num,
                nombre=pres.nombre,
                estado='APROBADO',
            )

            for partida in Partida.objects.filter(presupuesto=pres):
                PartidaModificacion.objects.create(
                    modificacion=mod,
                    subtipo=subtipo,
                    partida_origen_id=partida.partida_origen_id,
                    codigo=partida.codigo,
                    nombre=partida.nombre,
                    unidad=partida.unidad,
                    cantidad=partida.cantidad,
                    precio_unitario=partida.precio_unitario,
                    orden=partida.orden,
                )
            to_delete.append(pres.pk)

        Presupuesto.objects.filter(pk__in=to_delete).delete()

        # If multiple CONTRACTUALes exist, keep only the latest
        contractuales = list(
            Presupuesto.objects.filter(proyecto_id=proyecto_id).order_by('-created_at')
        )
        for old in contractuales[1:]:
            old.delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    # RunPython + DDL on the same table cannot share a transaction in PostgreSQL
    # (pending trigger events block ALTER TABLE). We run non-atomically so each
    # operation commits independently.
    atomic = False

    dependencies = [
        ('presupuesto', '0004_add_modificacion'),
    ]

    operations = [
        migrations.RunPython(migrate_presupuestos, noop),
        migrations.RemoveField(model_name='presupuesto', name='activo'),
        migrations.RemoveField(model_name='presupuesto', name='presupuesto_base'),
        migrations.RemoveField(model_name='presupuesto', name='tipo'),
        migrations.RemoveField(model_name='partida', name='partida_origen'),
        migrations.AlterField(
            model_name='presupuesto',
            name='proyecto',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='presupuesto',
                to='proyectos.proyecto',
            ),
        ),
    ]
