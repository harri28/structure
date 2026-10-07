from django.db import migrations, models


def wipe_trabajadores(apps, schema_editor):
    """Empezar limpio: borra trabajadores y sus documentos antes de alterar el esquema."""
    DocumentoTrabajador = apps.get_model('maquinaria', 'DocumentoTrabajador')
    Trabajador          = apps.get_model('maquinaria', 'Trabajador')
    DocumentoTrabajador.objects.all().delete()
    Trabajador.objects.all().delete()


SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino')]
ESTADO_CIVIL_CHOICES = [
    ('SOLTERO', 'Soltero/a'), ('CASADO', 'Casado/a'), ('CONVIVIENTE', 'Conviviente'),
    ('DIVORCIADO', 'Divorciado/a'), ('VIUDO', 'Viudo/a'),
]
LICENCIA_CATEGORIAS = [
    ('A-I', 'A-I  (Autos particulares)'),
    ('A-IIA', 'A-IIa (Taxi)'),
    ('A-IIB', 'A-IIb (Transporte interurbano)'),
    ('A-IIIA', 'A-IIIa (Transporte interprovincial)'),
    ('A-IIIB', 'A-IIIb (Transporte mercancías pesado)'),
    ('A-IIIC', 'A-IIIc (Carga especial)'),
    ('B-I', 'B-I (Motos lineales)'),
    ('B-IIA', 'B-IIa (Mototaxi)'),
    ('B-IIB', 'B-IIb (Motocarga)'),
    ('B-IIC', 'B-IIc (Motocicleta carga)'),
]
REGIMEN_PENSION_CHOICES = [
    ('NINGUNO', 'No afiliado'), ('ONP', 'ONP'),
    ('INTEGRA', 'AFP Integra'), ('PRIMA', 'AFP Prima'),
    ('HABITAT', 'AFP Habitat'), ('PROFUTURO', 'AFP Profuturo'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0010_trabajador_documentotrabajador'),
    ]

    operations = [
        migrations.RunPython(wipe_trabajadores, reverse_code=migrations.RunPython.noop),

        # Datos personales
        migrations.AddField(model_name='trabajador', name='sexo',
            field=models.CharField(blank=True, choices=SEXO_CHOICES, max_length=1, verbose_name='Sexo')),
        migrations.AddField(model_name='trabajador', name='estado_civil',
            field=models.CharField(blank=True, choices=ESTADO_CIVIL_CHOICES, max_length=15, verbose_name='Estado civil')),
        migrations.AddField(model_name='trabajador', name='lugar_nacimiento',
            field=models.CharField(blank=True, max_length=150, verbose_name='Lugar de nacimiento')),

        # Contacto
        migrations.AddField(model_name='trabajador', name='telefono2',
            field=models.CharField(blank=True, max_length=20, verbose_name='Teléfono alternativo')),
        migrations.AddField(model_name='trabajador', name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Correo electrónico')),
        migrations.AddField(model_name='trabajador', name='distrito',
            field=models.CharField(blank=True, max_length=80, verbose_name='Distrito')),
        migrations.AddField(model_name='trabajador', name='provincia',
            field=models.CharField(blank=True, max_length=80, verbose_name='Provincia')),
        migrations.AddField(model_name='trabajador', name='departamento',
            field=models.CharField(blank=True, max_length=80, verbose_name='Departamento')),

        # Emergencia
        migrations.AddField(model_name='trabajador', name='emergencia_nombre',
            field=models.CharField(blank=True, max_length=150, verbose_name='Contacto de emergencia')),
        migrations.AddField(model_name='trabajador', name='emergencia_parentesco',
            field=models.CharField(blank=True, max_length=50, verbose_name='Parentesco')),
        migrations.AddField(model_name='trabajador', name='emergencia_telefono',
            field=models.CharField(blank=True, max_length=20, verbose_name='Teléfono de emergencia')),

        # Laboral / experiencia
        migrations.AddField(model_name='trabajador', name='anios_experiencia',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Años de experiencia')),
        migrations.AddField(model_name='trabajador', name='experiencia_descripcion',
            field=models.TextField(blank=True, verbose_name='Experiencia laboral (empresas, obras, cargos)')),

        # Habilidades
        migrations.AddField(model_name='trabajador', name='habilidades',
            field=models.TextField(blank=True,
                help_text='Albañilería, carpintería, encofrado, fierrería, soldadura, electricidad, gasfitería, etc.',
                verbose_name='Habilidades y oficios')),

        # Licencia
        migrations.AddField(model_name='trabajador', name='tiene_licencia',
            field=models.BooleanField(default=False, verbose_name='¿Tiene licencia de conducir?')),
        migrations.AddField(model_name='trabajador', name='licencia_categoria',
            field=models.CharField(blank=True, choices=LICENCIA_CATEGORIAS, max_length=10, verbose_name='Categoría')),
        migrations.AddField(model_name='trabajador', name='licencia_numero',
            field=models.CharField(blank=True, max_length=30, verbose_name='N° de licencia')),
        migrations.AddField(model_name='trabajador', name='licencia_vencimiento',
            field=models.DateField(blank=True, null=True, verbose_name='Vencimiento de licencia')),

        # Maquinaria pesada
        migrations.AddField(model_name='trabajador', name='opera_maquinaria_pesada',
            field=models.BooleanField(default=False, verbose_name='¿Opera maquinaria pesada?')),
        migrations.AddField(model_name='trabajador', name='maquinas_opera',
            field=models.TextField(blank=True,
                help_text='Ej: retroexcavadora, cargador frontal, volquete, rodillo, grúa.',
                verbose_name='Maquinaria que opera')),

        # Seguridad social
        migrations.AddField(model_name='trabajador', name='regimen_pension',
            field=models.CharField(blank=True, choices=REGIMEN_PENSION_CHOICES, max_length=15, verbose_name='Régimen de pensiones')),
        migrations.AddField(model_name='trabajador', name='cuspp',
            field=models.CharField(blank=True, max_length=20, verbose_name='CUSPP')),
        migrations.AddField(model_name='trabajador', name='tiene_essalud',
            field=models.BooleanField(default=False, verbose_name='EsSalud')),
        migrations.AddField(model_name='trabajador', name='tiene_sctr',
            field=models.BooleanField(default=False, verbose_name='SCTR vigente')),
        migrations.AddField(model_name='trabajador', name='banco',
            field=models.CharField(blank=True, max_length=50, verbose_name='Banco')),
        migrations.AddField(model_name='trabajador', name='cuenta_cci',
            field=models.CharField(blank=True, max_length=25, verbose_name='CCI (20 dígitos)')),

        # Archivos
        migrations.AddField(model_name='trabajador', name='cv',
            field=models.FileField(blank=True, upload_to='trabajadores/cv/', verbose_name='CV')),

        # Observaciones
        migrations.AddField(model_name='trabajador', name='observaciones',
            field=models.TextField(blank=True, verbose_name='Observaciones')),

        # Timestamp
        migrations.AddField(model_name='trabajador', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
