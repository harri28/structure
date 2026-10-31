from django.core.management.base import BaseCommand, CommandError
from apps.proyectos.models import Proyecto
from apps.maquinaria.models import TipoPersonal, Trabajador


PERSONAL_DEMO = [
    # (apellidos, nombres, dni, cargo_codigo, telefono)
    ('GARCÍA LÓPEZ',       'JUAN CARLOS',     '70123456', 'OPER',    '987111222'),
    ('RODRÍGUEZ PÉREZ',    'MARÍA ELENA',     '71234567', 'MAESTRO', '987222333'),
    ('QUISPE HUAMÁN',      'LUIS ALBERTO',    '72345678', 'PEON',    '987333444'),
    ('MAMANI CONDORI',     'JOSÉ ANTONIO',    '73456789', 'OFIC',    '987444555'),
    ('TORRES VARGAS',      'ROSA MERCEDES',   '74567890', 'MAESTRO', '987555666'),
]


class Command(BaseCommand):
    help = 'Crea 5 trabajadores demo en un proyecto (idempotente por DNI).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--proyecto', type=int, default=None,
            help='PK del proyecto. Si no se pasa, usa el primero disponible.',
        )

    def handle(self, *args, **opts):
        proyecto_id = opts.get('proyecto')
        if proyecto_id:
            try:
                proyecto = Proyecto.objects.get(pk=proyecto_id)
            except Proyecto.DoesNotExist:
                raise CommandError(f'No existe proyecto con pk={proyecto_id}.')
        else:
            proyecto = Proyecto.objects.order_by('pk').first()
            if not proyecto:
                raise CommandError('No hay ningún proyecto cargado.')

        tipos_por_codigo = {tp.codigo: tp for tp in TipoPersonal.objects.all()}
        creados, existentes = 0, 0
        for apellidos, nombres, dni, cargo_codigo, telefono in PERSONAL_DEMO:
            if Trabajador.objects.filter(proyecto=proyecto, dni=dni).exists():
                existentes += 1
                continue
            Trabajador.objects.create(
                proyecto=proyecto,
                apellidos=apellidos,
                nombres=nombres,
                dni=dni,
                telefono=telefono,
                tipo_personal=tipos_por_codigo.get(cargo_codigo),
                activo=True,
            )
            creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Proyecto "{proyecto.codigo}" — creados: {creados}, ya existían: {existentes}.'
        ))
