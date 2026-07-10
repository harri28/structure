from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import ConfigEmpresa, ConfigSunat, Rol, PerfilUsuario, UnidadMedida, CargoManoObra, GRUPOS_PERMISOS, TODOS_LOS_PERMISOS


# ── Hub ───────────────────────────────────────────────────────────

def hub(request):
    config = ConfigEmpresa.get()
    sunat  = ConfigSunat.get()
    return render(request, 'configuracion/hub.html', {
        'config':      config,
        'sunat':       sunat,
        'n_usuarios':  User.objects.filter(is_active=True).count(),
        'n_roles':     Rol.objects.count(),
        'n_unidades':  UnidadMedida.objects.filter(activo=True).count(),
        'n_cargos':    CargoManoObra.objects.filter(activo=True).count(),
    })


# ── Empresa ───────────────────────────────────────────────────────

class EmpresaForm(forms.ModelForm):
    class Meta:
        model  = ConfigEmpresa
        fields = ['razon_social', 'ruc', 'direccion', 'telefono', 'email', 'web', 'moneda', 'igv', 'logo']
        widgets = {
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'ruc':          forms.TextInput(attrs={'class': 'form-control', 'maxlength': 11}),
            'direccion':    forms.TextInput(attrs={'class': 'form-control'}),
            'telefono':     forms.TextInput(attrs={'class': 'form-control'}),
            'email':        forms.EmailInput(attrs={'class': 'form-control'}),
            'web':          forms.URLInput(attrs={'class': 'form-control'}),
            'moneda':       forms.TextInput(attrs={'class': 'form-control', 'style': 'width:100px'}),
            'igv':          forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'style': 'width:120px'}),
            'logo':         forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


def empresa(request):
    config = ConfigEmpresa.get()
    if request.method == 'POST':
        form = EmpresaForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada.')
            return redirect('configuracion:empresa')
    else:
        form = EmpresaForm(instance=config)
    return render(request, 'configuracion/empresa.html', {'form': form, 'config': config})



class SunatForm(forms.ModelForm):
    class Meta:
        model  = ConfigSunat
        fields = ['regimen_tributario', 'usuario_sol', 'clave_sol',
                  'tipo_comprobante', 'serie_factura', 'serie_boleta',
                  'numero_correlativo', 'ose']
        widgets = {
            'regimen_tributario': forms.Select(attrs={'class': 'form-select'}),
            'usuario_sol':        forms.TextInput(attrs={'class': 'form-control'}),
            'clave_sol':          forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'tipo_comprobante':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: FACTURA'}),
            'serie_factura':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: F001'}),
            'serie_boleta':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: B001'}),
            'numero_correlativo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 00000001'}),
            'ose':                forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: SUNAT, Efact, Nubefact…'}),
        }


def sunat(request):
    config_sunat = ConfigSunat.get()
    if request.method == 'POST':
        form = SunatForm(request.POST, instance=config_sunat)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración SUNAT guardada.')
            return redirect('configuracion:sunat')
    else:
        form = SunatForm(instance=config_sunat)
    return render(request, 'configuracion/sunat.html', {'form': form})




# ── Equipo (Usuarios + Roles combinados) ──────────────────────────

def equipo(request):
    from apps.proyectos.models import Proyecto

    tab = request.GET.get('tab', 'usuarios')

    # Usuarios agrupados por proyecto
    grupos = []
    ids_con_proyecto = set()
    for proyecto in Proyecto.objects.prefetch_related(
        'miembros__usuario__perfil__rol'
    ).order_by('codigo'):
        miembros = list(proyecto.miembros.select_related('usuario__perfil__rol').all())
        if miembros:
            usuarios_proy = [m.usuario for m in miembros]
            grupos.append({'proyecto': proyecto, 'usuarios': usuarios_proy})
            ids_con_proyecto.update(u.pk for u in usuarios_proy)

    sin_proyecto = User.objects.select_related('perfil__rol').exclude(
        pk__in=ids_con_proyecto
    ).order_by('username')

    roles_data = []
    for rol in Rol.objects.prefetch_related('usuarios').all():
        permisos_activos = [
            label
            for _, campos in GRUPOS_PERMISOS
            for campo, label in campos
            if getattr(rol, campo, False)
        ]
        roles_data.append({'rol': rol, 'permisos_activos': permisos_activos})

    total_usuarios = User.objects.count()

    return render(request, 'configuracion/equipo.html', {
        'grupos':          grupos,
        'sin_proyecto':    sin_proyecto,
        'total_usuarios':  total_usuarios,
        'roles_data':      roles_data,
        'tab_activo':      tab,
    })


def roles(request):
    from django.shortcuts import redirect as _redirect
    return _redirect('/configuracion/equipo/?tab=roles')


# ── Roles ─────────────────────────────────────────────────────────


def rol_crear(request):
    error = {}
    datos = {}
    superadmin_existe = Rol.objects.filter(es_superadmin=True).exists()
    if request.method == 'POST':
        datos   = request.POST
        nombre  = datos.get('nombre', '').strip()
        if not nombre:
            error['nombre'] = 'El nombre del rol es obligatorio.'
        elif Rol.objects.filter(nombre__iexact=nombre).exists():
            error['nombre'] = 'Ya existe un rol con ese nombre.'
        if datos.get('es_superadmin') == '1' and superadmin_existe:
            error['es_superadmin'] = 'Ya existe un rol Superadmin. Solo puede haber uno en el sistema.'

        if not error:
            rol = Rol(
                nombre=nombre,
                descripcion=datos.get('descripcion', '').strip(),
            )
            for campo in TODOS_LOS_PERMISOS:
                setattr(rol, campo, datos.get(campo) == '1')
            rol.save()
            messages.success(request, f'Rol "{rol.nombre}" creado.')
            return redirect('/configuracion/equipo/?tab=roles')

    permisos_checked = [c for c in TODOS_LOS_PERMISOS if datos.get(c) == '1']
    return render(request, 'configuracion/rol_form.html', {
        'titulo':             'Nuevo Rol',
        'accion':             'crear',
        'grupos':             GRUPOS_PERMISOS,
        'form_nombre':        datos.get('nombre', ''),
        'form_descripcion':   datos.get('descripcion', ''),
        'error':              error,
        'permisos_checked':   permisos_checked,
        'superadmin_existe':  superadmin_existe,
        'es_este_superadmin': False,
    })


def rol_editar(request, pk):
    rol   = get_object_or_404(Rol, pk=pk)
    error = {}
    es_este_superadmin = rol.es_superadmin
    superadmin_existe  = Rol.objects.filter(es_superadmin=True).exclude(pk=pk).exists()
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if not nombre:
            error['nombre'] = 'El nombre del rol es obligatorio.'
        elif Rol.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists():
            error['nombre'] = 'Ya existe otro rol con ese nombre.'
        if request.POST.get('es_superadmin') == '1' and superadmin_existe:
            error['es_superadmin'] = 'Ya existe un rol Superadmin. Solo puede haber uno en el sistema.'

        if not error:
            rol.nombre      = nombre
            rol.descripcion = request.POST.get('descripcion', '').strip()
            for campo in TODOS_LOS_PERMISOS:
                setattr(rol, campo, request.POST.get(campo) == '1')
            rol.save()
            messages.success(request, f'Rol "{rol.nombre}" actualizado.')
            return redirect('/configuracion/equipo/?tab=roles')

    permisos_checked = [c for c in TODOS_LOS_PERMISOS if getattr(rol, c, False)]
    return render(request, 'configuracion/rol_form.html', {
        'titulo':             f'Editar Rol — {rol.nombre}',
        'accion':             'editar',
        'rol':                rol,
        'grupos':             GRUPOS_PERMISOS,
        'form_nombre':        request.POST.get('nombre', rol.nombre) if request.method == 'POST' else rol.nombre,
        'form_descripcion':   request.POST.get('descripcion', rol.descripcion) if request.method == 'POST' else rol.descripcion,
        'error':              error,
        'permisos_checked':   permisos_checked,
        'superadmin_existe':  superadmin_existe,
        'es_este_superadmin': es_este_superadmin,
    })


def rol_eliminar(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == 'POST':
        if rol.usuarios.exists():
            messages.error(request, f'No se puede eliminar "{rol.nombre}": hay usuarios asignados.')
            return redirect('/configuracion/equipo/?tab=roles')
        nombre = rol.nombre
        rol.delete()
        messages.success(request, f'Rol "{nombre}" eliminado.')
        return redirect('/configuracion/equipo/?tab=roles')
    return render(request, 'configuracion/rol_confirmar_eliminar.html', {'rol': rol})


# ── Usuarios ──────────────────────────────────────────────────────

def usuarios(request):
    from django.shortcuts import redirect as _redirect
    return _redirect('/configuracion/equipo/')


def _guardar_perfil(usuario, rol_id):
    """Crea o actualiza el PerfilUsuario con el rol seleccionado."""
    rol = Rol.objects.filter(pk=rol_id).first() if rol_id else None
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=usuario)
    perfil.rol = rol
    perfil.save()


def usuario_crear(request):
    from apps.proyectos.models import Proyecto, ProyectoMiembro

    # Proyecto al que se asignará el usuario: parámetro GET/POST tiene prioridad, luego sesión
    proyecto_pk = (request.POST.get('proyecto_pk') or
                   request.GET.get('proyecto') or
                   request.session.get('proyecto_id'))
    proyecto_destino = None
    if proyecto_pk:
        proyecto_destino = Proyecto.objects.filter(pk=proyecto_pk).first()

    error = {}
    datos = {}
    roles_list = Rol.objects.all()
    if request.method == 'POST':
        datos      = request.POST
        username   = datos.get('username', '').strip()
        first_name = datos.get('first_name', '').strip()
        last_name  = datos.get('last_name', '').strip()
        email      = datos.get('email', '').strip()
        password1  = datos.get('password1', '')
        password2  = datos.get('password2', '')
        rol_id     = datos.get('rol_id') or None
        nivel      = datos.get('nivel', 'usuario')

        if not username:
            error['username'] = 'El nombre de usuario es obligatorio.'
        elif User.objects.filter(username=username).exists():
            error['username'] = 'Ya existe un usuario con ese nombre.'
        if not password1:
            error['password1'] = 'La contraseña es obligatoria.'
        elif len(password1) < 6:
            error['password1'] = 'Mínimo 6 caracteres.'
        elif password1 != password2:
            error['password2'] = 'Las contraseñas no coinciden.'

        if not error:
            u = User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=make_password(password1),
                is_staff=nivel in ('staff', 'superadmin'),
                is_superuser=nivel == 'superadmin',
                is_active=True,
            )
            _guardar_perfil(u, rol_id)

            if proyecto_destino:
                ProyectoMiembro.objects.get_or_create(proyecto=proyecto_destino, usuario=u)
                messages.success(request, f'Usuario "{u.username}" creado y asignado a {proyecto_destino.codigo}.')
                return redirect('proyectos:detalle', pk=proyecto_destino.pk)

            messages.success(request, f'Usuario "{u.username}" creado.')
            return redirect('configuracion:equipo')

    return render(request, 'configuracion/usuario_form.html', {
        'titulo':             'Nuevo Usuario',
        'accion':             'crear',
        'error':              error,
        'roles_list':         roles_list,
        'proyecto_destino':   proyecto_destino,
        'form_username':      datos.get('username', ''),
        'form_first_name':    datos.get('first_name', ''),
        'form_last_name':     datos.get('last_name', ''),
        'form_email':         datos.get('email', ''),
        'form_nivel':         datos.get('nivel', 'usuario'),
        'form_rol_id':        datos.get('rol_id', ''),
    })


def usuario_editar(request, pk):
    u = get_object_or_404(User, pk=pk)
    error = {}
    roles_list = Rol.objects.all()

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        nivel      = request.POST.get('nivel', 'usuario')
        is_active  = request.POST.get('is_active') == '1'
        rol_id     = request.POST.get('rol_id') or None

        u.first_name   = first_name
        u.last_name    = last_name
        u.email        = email
        u.is_staff     = nivel in ('staff', 'superadmin')
        u.is_superuser = nivel == 'superadmin'
        if u.pk != request.user.pk:
            u.is_active = is_active
        u.save()
        _guardar_perfil(u, rol_id)
        messages.success(request, f'Usuario "{u.username}" actualizado.')
        return redirect('configuracion:equipo')

    nivel_actual = 'superadmin' if u.is_superuser else ('staff' if u.is_staff else 'usuario')
    rol_actual_id = None
    try:
        rol_actual_id = u.perfil.rol_id
    except AttributeError:
        pass

    return render(request, 'configuracion/usuario_form.html', {
        'titulo':          f'Editar — {u.username}',
        'accion':          'editar',
        'usuario':         u,
        'error':           error,
        'roles_list':      roles_list,
        'form_first_name': u.first_name,
        'form_last_name':  u.last_name,
        'form_email':      u.email,
        'form_nivel':      nivel_actual,
        'form_rol_id':     str(rol_actual_id) if rol_actual_id else '',
    })


def usuario_password(request, pk):
    u = get_object_or_404(User, pk=pk)
    error = {}
    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if not password1:
            error['password1'] = 'Ingresa la nueva contraseña.'
        elif len(password1) < 6:
            error['password1'] = 'Mínimo 6 caracteres.'
        elif password1 != password2:
            error['password2'] = 'Las contraseñas no coinciden.'

        if not error:
            u.password = make_password(password1)
            u.save()
            messages.success(request, f'Contraseña de "{u.username}" actualizada.')
            return redirect('configuracion:equipo')

    return render(request, 'configuracion/usuario_password.html', {
        'usuario': u,
        'error':   error,
    })


def usuario_eliminar(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.pk == request.user.pk:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('configuracion:equipo')
    if request.method == 'POST':
        nombre = u.username
        u.delete()
        messages.success(request, f'Usuario "{nombre}" eliminado.')
        return redirect('configuracion:equipo')
    return render(request, 'configuracion/usuario_confirmar_eliminar.html', {'usuario': u})


def usuario_toggle(request, pk):
    if request.method == 'POST':
        u = get_object_or_404(User, pk=pk)
        if u.pk != request.user.pk:
            u.is_active = not u.is_active
            u.save()
            estado = 'activado' if u.is_active else 'desactivado'
            messages.success(request, f'Usuario {u.username} {estado}.')
    return redirect('configuracion:equipo')


# ── Perfil del usuario ────────────────────────────────────────────

def perfil(request):
    perfil_obj, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        cargo      = request.POST.get('cargo', '').strip()
        telefono   = request.POST.get('telefono', '').strip()
        email      = request.POST.get('email', '').strip()

        request.user.first_name = first_name
        request.user.last_name  = last_name
        request.user.email      = email
        request.user.save()

        perfil_obj.cargo    = cargo
        perfil_obj.telefono = telefono
        perfil_obj.save()

        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('configuracion:perfil')

    return render(request, 'configuracion/perfil.html', {'perfil': perfil_obj})


# ── Unidades de Medida ────────────────────────────────────────────

_UNIDADES_DEFAULT = [
    # (codigo, nombre, descripcion, aliases)
    ('hh',  'Hora Hombre',    'Mano de obra directa',   'HH, hora hombre, horas hombre'),
    ('hm',  'Hora Máquina',   'Equipos y maquinaria',   'HM, hora máquina, horas máquina, hora maquina, horas maquina'),
    ('he',  'Hora Equipo',    'Equipos varios',          'HE, hora equipo, horas equipo'),
    ('m2',  'Metro Cuadrado', '',                        'M2, m², metro cuadrado, metros cuadrados'),
    ('m3',  'Metro Cúbico',   '',                        'M3, m³, metro cúbico, metros cúbicos, metro cubico'),
    ('ml',  'Metro Lineal',   '',                        'ML, mll, metro lineal, metros lineales'),
    ('m',   'Metro',          '',                        'MT, mt, metro, metros'),
    ('kg',  'Kilogramo',      '',                        'KG, Kg, kilogramo, kilogramos'),
    ('tn',  'Tonelada',       '',                        'TN, ton, TON, tonelada, toneladas'),
    ('g',   'Gramo',          '',                        'GR, gr, gramo, gramos'),
    ('lt',  'Litro',          '',                        'LT, lts, LTS, l, L, litro, litros'),
    ('gal', 'Galón',          '',                        'GAL, Gal, galón, galon, galones'),
    ('glb', 'Global',         '',                        'GLB, gb, GL, gl, global, globales'),
    ('und', 'Unidad',         '',                        'UND, un, UN, u, U, unidad, unidades'),
    ('pza', 'Pieza',          '',                        'PZA, Pza, pieza, piezas'),
    ('par', 'Par',            '',                        'PAR, pares'),
    ('jgo', 'Juego',          '',                        'JGO, Jgo, juego, juegos'),
    ('set', 'Set',            '',                        'SET, sets'),
    ('bls', 'Bolsa',          '',                        'BLS, Bls, bolsa, bolsas'),
    ('caj', 'Caja',           '',                        'CAJ, Caj, caja, cajas'),
    ('rll', 'Rollo',          '',                        'RLL, Rll, rollo, rollos'),
    ('plg', 'Pulgada',        '',                        'PLG, Plg, pulgada, pulgadas'),
    ('p2',  'Pie Cuadrado',   '',                        'P2, pie2, pie cuadrado, pies cuadrados'),
    ('p3',  'Pie Cúbico',     '',                        'P3, pie3, pie cúbico, pie cubico, pies cúbicos'),
    ('dia', 'Día',            '',                        'DIA, Dia, día, d'),
    ('mes', 'Mes',            '',                        'MES, Mes'),
    ('sem', 'Semana',         '',                        'SEM, Sem, semana, semanas'),
]


def unidad_lista(request):
    unidades = UnidadMedida.objects.all()
    return render(request, 'configuracion/unidad_lista.html', {'unidades': unidades})


def unidad_crear(request):
    error = {}
    codigo_inicial = request.GET.get('codigo', '')
    if request.method == 'POST':
        codigo      = request.POST.get('codigo', '').strip()
        nombre      = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        aliases     = request.POST.get('aliases', '').strip()
        activo      = request.POST.get('activo') == '1'

        if not codigo:
            error['codigo'] = 'El código es obligatorio.'
        elif UnidadMedida.objects.filter(codigo__iexact=codigo).exists():
            error['codigo'] = 'Ya existe una unidad con ese código.'
        if not nombre:
            error['nombre'] = 'El nombre es obligatorio.'

        if not error:
            UnidadMedida.objects.create(
                codigo=codigo, nombre=nombre,
                descripcion=descripcion, aliases=aliases, activo=activo,
            )
            messages.success(request, f'Unidad "{codigo}" creada.')
            return redirect('configuracion:unidad_lista')

    unidades_existentes = list(UnidadMedida.objects.values('codigo', 'nombre'))
    return render(request, 'configuracion/unidad_form.html', {
        'titulo':              'Nueva Unidad de Medida',
        'accion':              'crear',
        'error':               error,
        'form_codigo':         request.POST.get('codigo', codigo_inicial),
        'form_nombre':         request.POST.get('nombre', ''),
        'form_descripcion':    request.POST.get('descripcion', ''),
        'form_aliases':        request.POST.get('aliases', ''),
        'form_activo':         request.POST.get('activo', '1'),
        'unidades_existentes': unidades_existentes,
    })


def unidad_editar(request, pk):
    unidad = get_object_or_404(UnidadMedida, pk=pk)
    error  = {}
    if request.method == 'POST':
        codigo      = request.POST.get('codigo', '').strip()
        nombre      = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        aliases     = request.POST.get('aliases', '').strip()
        activo      = request.POST.get('activo') == '1'

        if not codigo:
            error['codigo'] = 'El código es obligatorio.'
        elif UnidadMedida.objects.filter(codigo__iexact=codigo).exclude(pk=pk).exists():
            error['codigo'] = 'Ya existe otra unidad con ese código.'
        if not nombre:
            error['nombre'] = 'El nombre es obligatorio.'

        if not error:
            unidad.codigo      = codigo
            unidad.nombre      = nombre
            unidad.descripcion = descripcion
            unidad.aliases     = aliases
            unidad.activo      = activo
            unidad.save()
            messages.success(request, f'Unidad "{codigo}" actualizada.')
            return redirect('configuracion:unidad_lista')

    unidades_existentes = list(UnidadMedida.objects.exclude(pk=pk).values('codigo', 'nombre'))
    return render(request, 'configuracion/unidad_form.html', {
        'titulo':              f'Editar — {unidad.codigo}',
        'accion':              'editar',
        'unidad':              unidad,
        'error':               error,
        'form_codigo':         request.POST.get('codigo', unidad.codigo),
        'form_nombre':         request.POST.get('nombre', unidad.nombre),
        'form_descripcion':    request.POST.get('descripcion', unidad.descripcion),
        'form_aliases':        request.POST.get('aliases', unidad.aliases),
        'form_activo':         '1' if (request.POST.get('activo', '1') == '1' if request.method == 'POST' else unidad.activo) else '0',
        'unidades_existentes': unidades_existentes,
    })


def unidad_eliminar(request, pk):
    unidad = get_object_or_404(UnidadMedida, pk=pk)
    if request.method == 'POST':
        codigo = unidad.codigo
        unidad.delete()
        messages.success(request, f'Unidad "{codigo}" eliminada.')
        return redirect('configuracion:unidad_lista')
    return render(request, 'configuracion/unidad_confirmar_eliminar.html', {'unidad': unidad})




def unidad_cargar_defaults(request):
    if request.method == 'POST':
        creadas = actualizadas = 0
        for codigo, nombre, descripcion, aliases in _UNIDADES_DEFAULT:
            obj, created = UnidadMedida.objects.get_or_create(
                codigo__iexact=codigo,
                defaults={'codigo': codigo, 'nombre': nombre, 'descripcion': descripcion, 'aliases': aliases},
            )
            if created:
                creadas += 1
            elif not obj.aliases:
                obj.aliases = aliases
                obj.save(update_fields=['aliases'])
                actualizadas += 1
        partes = []
        if creadas:
            partes.append(f'{creadas} unidad(es) creadas')
        if actualizadas:
            partes.append(f'{actualizadas} actualizadas con aliases')
        if partes:
            messages.success(request, ', '.join(partes) + '.')
        else:
            messages.info(request, 'Todas las unidades por defecto ya estaban al día.')
    return redirect('configuracion:unidad_lista')


# ── Cargos de Mano de Obra ────────────────────────────────────────

_CARGOS_DEFAULT = [
    # (codigo, nombre, variantes, orden)
    ('1', 'CAPATAZ',  'capataz, maestro, maestro de obra, capataz de obra', 1),
    ('2', 'OPERARIO', 'operario', 2),
    ('3', 'OFICIAL',  'oficial', 3),
    ('4', 'PEÓN',     'peon, peón, piones, peon cuadrilla', 4),
]


def cargo_lista(request):
    cargos = CargoManoObra.objects.all()
    return render(request, 'configuracion/cargo_lista.html', {'cargos': cargos})


def cargo_crear(request):
    error = {}
    if request.method == 'POST':
        codigo    = request.POST.get('codigo', '').strip()
        nombre    = request.POST.get('nombre', '').strip().upper()
        variantes = request.POST.get('variantes', '').strip()
        orden     = request.POST.get('orden', '0').strip()
        activo    = request.POST.get('activo') == '1'

        if not codigo:
            error['codigo'] = 'El código es obligatorio.'
        elif CargoManoObra.objects.filter(codigo__iexact=codigo).exists():
            error['codigo'] = 'Ya existe un cargo con ese código.'
        if not nombre:
            error['nombre'] = 'El nombre es obligatorio.'

        try:
            orden_int = int(orden)
        except (ValueError, TypeError):
            orden_int = 0

        if not error:
            CargoManoObra.objects.create(
                codigo=codigo, nombre=nombre, variantes=variantes,
                orden=orden_int, activo=activo,
            )
            messages.success(request, f'Cargo "{nombre}" creado.')
            return redirect('configuracion:cargo_lista')

    cargos_existentes = list(CargoManoObra.objects.values('codigo', 'nombre'))
    return render(request, 'configuracion/cargo_form.html', {
        'titulo':            'Nuevo Cargo de Mano de Obra',
        'accion':            'crear',
        'error':             error,
        'form_codigo':       request.POST.get('codigo', ''),
        'form_nombre':       request.POST.get('nombre', ''),
        'form_variantes':    request.POST.get('variantes', ''),
        'form_orden':        request.POST.get('orden', ''),
        'form_activo':       request.POST.get('activo', '1'),
        'cargos_existentes': cargos_existentes,
    })


def cargo_editar(request, pk):
    cargo = get_object_or_404(CargoManoObra, pk=pk)
    error = {}
    if request.method == 'POST':
        codigo    = request.POST.get('codigo', '').strip()
        nombre    = request.POST.get('nombre', '').strip().upper()
        variantes = request.POST.get('variantes', '').strip()
        orden     = request.POST.get('orden', '0').strip()
        activo    = request.POST.get('activo') == '1'

        if not codigo:
            error['codigo'] = 'El código es obligatorio.'
        elif CargoManoObra.objects.filter(codigo__iexact=codigo).exclude(pk=pk).exists():
            error['codigo'] = 'Ya existe otro cargo con ese código.'
        if not nombre:
            error['nombre'] = 'El nombre es obligatorio.'

        try:
            orden_int = int(orden)
        except (ValueError, TypeError):
            orden_int = cargo.orden

        if not error:
            cargo.codigo    = codigo
            cargo.nombre    = nombre
            cargo.variantes = variantes
            cargo.orden     = orden_int
            cargo.activo    = activo
            cargo.save()
            messages.success(request, f'Cargo "{nombre}" actualizado.')
            return redirect('configuracion:cargo_lista')

    cargos_existentes = list(CargoManoObra.objects.exclude(pk=pk).values('codigo', 'nombre'))
    return render(request, 'configuracion/cargo_form.html', {
        'titulo':            f'Editar — {cargo.nombre}',
        'accion':            'editar',
        'cargo':             cargo,
        'error':             error,
        'form_codigo':       request.POST.get('codigo', cargo.codigo),
        'form_nombre':       request.POST.get('nombre', cargo.nombre),
        'form_variantes':    request.POST.get('variantes', cargo.variantes),
        'form_orden':        request.POST.get('orden', str(cargo.orden)),
        'form_activo':       '1' if (request.POST.get('activo', '1') == '1' if request.method == 'POST' else cargo.activo) else '0',
        'cargos_existentes': cargos_existentes,
    })


def cargo_cargar_defaults(request):
    if request.method == 'POST':
        creados = 0
        for codigo, nombre, variantes, orden in _CARGOS_DEFAULT:
            obj, created = CargoManoObra.objects.get_or_create(
                codigo=codigo,
                defaults={'nombre': nombre, 'variantes': variantes, 'orden': orden},
            )
            if created:
                creados += 1
            elif not obj.variantes:
                obj.variantes = variantes
                obj.save(update_fields=['variantes'])
        if creados:
            messages.success(request, f'{creados} cargo(s) por defecto cargados.')
        else:
            messages.info(request, 'Los cargos por defecto ya estaban al día.')
    return redirect('configuracion:cargo_lista')
