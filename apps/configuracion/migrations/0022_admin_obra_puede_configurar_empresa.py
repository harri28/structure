"""
Data migration — otorga `puede_configurar_empresa` al rol sembrado
"Administrador de Obra" (ver migración 0019).

Motivo: el residente de obra necesita poder cambiar el color/logo/nombre
de la empresa desde Configuración → Empresa. La migración 0019 lo dejó
fuera a propósito (rol pensado como "no es admin del sistema"), pero se
decidió ampliarlo a este único permiso adicional. Usuarios & Roles sigue
siendo exclusivo de Superadmin.

Idempotente: si el rol no existe no hace nada.
"""
from django.db import migrations


def activar_config_empresa(apps, schema_editor):
    Rol = apps.get_model('configuracion', 'Rol')
    Rol.objects.filter(nombre='Administrador de Obra').update(puede_configurar_empresa=True)


def revertir(apps, schema_editor):
    Rol = apps.get_model('configuracion', 'Rol')
    Rol.objects.filter(nombre='Administrador de Obra').update(puede_configurar_empresa=False)


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0021_configempresa_imagen_marca'),
    ]

    operations = [
        migrations.RunPython(activar_config_empresa, revertir),
    ]
