from django.db import migrations, models


def _es_almacenero(user):
    """Devuelve True si el usuario tenía perfil de Almacenero cuando creó el REQ:
    puede crear requerimientos pero NO puede aprobarlos."""
    if user is None:
        return False
    try:
        rol = user.perfil.rol
    except AttributeError:
        return False
    if rol is None:
        return False
    return bool(getattr(rol, 'puede_crear_requerimientos', False)) and \
           not bool(getattr(rol, 'puede_aprobar_requerimientos', False))


def clasificar_y_renumerar(apps, schema_editor):
    """Clasifica cada Requerimiento existente como OBRA o ALMACEN y, para los
    de ALMACEN, los renumera con prefijo 'A' arrancando en 'A001' por proyecto
    (en orden cronológico de created_at). Los de OBRA conservan su número actual."""
    Requerimiento = apps.get_model('requerimientos', 'Requerimiento')

    # Paso 1: clasificar.
    for req in Requerimiento.objects.select_related('created_by').all():
        if _es_almacenero(req.created_by):
            req.origen = 'ALMACEN'
        elif req.created_by is None and req.estado == 'SOLICITADO':
            # Caso borde: REQ antiguo sin created_by que quedó en SOLICITADO.
            req.origen = 'ALMACEN'
        else:
            req.origen = 'OBRA'
        req.save(update_fields=['origen'])

    # Paso 2: renumerar los de ALMACEN por proyecto.
    # Primero movemos a números temporales ("TMPA001", ...) para no chocar con
    # el unique_together durante la renumeración, y luego al número definitivo.
    proyectos_con_almacen = set(
        Requerimiento.objects.filter(origen='ALMACEN')
        .values_list('proyecto_id', flat=True)
    )
    for pid in proyectos_con_almacen:
        reqs = list(
            Requerimiento.objects.filter(proyecto_id=pid, origen='ALMACEN')
            .order_by('created_at', 'pk')
        )
        # Fase intermedia
        for i, r in enumerate(reqs, start=1):
            r.numero = f'TMPA{i:03d}'
            r.save(update_fields=['numero'])
        # Fase definitiva
        for i, r in enumerate(reqs, start=1):
            r.numero = f'A{i:03d}'
            r.save(update_fields=['numero'])


def reverso_noop(apps, schema_editor):
    """No se puede recuperar la numeración original sin datos de auditoría;
    dejamos el reverso como no-op para no inventar datos."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0017_historial_insumo_original'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='origen',
            field=models.CharField(
                choices=[('OBRA', 'Jefe de Obra'), ('ALMACEN', 'Almacén')],
                default='OBRA',
                max_length=10,
            ),
        ),
        migrations.RunPython(clasificar_y_renumerar, reverse_code=reverso_noop),
    ]
