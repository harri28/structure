from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import ConfigEmpresa, Rol, PerfilUsuario, GRUPOS_PERMISOS, TODOS_LOS_PERMISOS


# ── Empresa ───────────────────────────────────────────────────────

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = ConfigEmpresa
        fields = ['razon_social', 'ruc', 'direccion', 'telefono', 'email', 'web', 'moneda', 'igv']
        widgets = {
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'ruc':          forms.TextInput(attrs={'class': 'form-control', 'maxlength': 11}),
            'direccion':    forms.TextInput(attrs={'class': 'form-control'}),
            'telefono':     forms.TextInput(attrs={'class': 'form-control'}),
            'email':        forms.EmailInput(attrs={'class': 'form-control'}),
            'web':          forms.URLInput(attrs={'class': 'form-control'}),
            'moneda':       forms.TextInput(attrs={'class': 'form-control', 'style': 'width:100px'}),
            'igv':          forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'style': 'width:120px'}),
        }


def empresa(request):
    config = ConfigEmpresa.get()
    if request.method == 'POST':
        form = EmpresaForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada.')
            return redirect('configuracion:empresa')
    else:
        form = EmpresaForm(instance=config)
    return render(request, 'configuracion/empresa.html', {'form': form, 'config': config})


# ── Equipo (Usuarios + Roles combinados) ──────────────────────────

def equipo(request):
    tab = request.GET.get('tab', 'usuarios')
    users = User.objects.select_related('perfil__rol').order_by('username')
    roles_data = []
    for rol in Rol.objects.prefetch_related('usuarios').all():
        permisos_activos = [
            label
            for _, campos in GRUPOS_PERMISOS
            for campo, label in campos
            if getattr(rol, campo, False)
        ]
        roles_data.append({'rol': rol, 'permisos_activos': permisos_activos})
    return render(request, 'configuracion/equipo.html', {
        'users':      users,
        'roles_data': roles_data,
        'tab_activo': tab,
    })


def roles(request):
    from django.shortcuts import redirect as _redirect
    return _redirect('/configuracion/equipo/?tab=roles')


# ── Roles ─────────────────────────────────────────────────────────


def rol_crear(request):
    error = {}
    datos = {}
    if request.method == 'POST':
        datos   = request.POST
        nombre  = datos.get('nombre', '').strip()
        if not nombre:
            error['nombre'] = 'El nombre del rol es obligatorio.'
        elif Rol.objects.filter(nombre__iexact=nombre).exists():
            error['nombre'] = 'Ya existe un rol con ese nombre.'

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
        'titulo':           'Nuevo Rol',
        'accion':           'crear',
        'grupos':           GRUPOS_PERMISOS,
        'form_nombre':      datos.get('nombre', ''),
        'form_descripcion': datos.get('descripcion', ''),
        'error':            error,
        'permisos_checked': permisos_checked,
    })


def rol_editar(request, pk):
    rol   = get_object_or_404(Rol, pk=pk)
    error = {}
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if not nombre:
            error['nombre'] = 'El nombre del rol es obligatorio.'
        elif Rol.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists():
            error['nombre'] = 'Ya existe otro rol con ese nombre.'

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
        'titulo':           f'Editar Rol — {rol.nombre}',
        'accion':           'editar',
        'rol':              rol,
        'grupos':           GRUPOS_PERMISOS,
        'form_nombre':      request.POST.get('nombre', rol.nombre) if request.method == 'POST' else rol.nombre,
        'form_descripcion': request.POST.get('descripcion', rol.descripcion) if request.method == 'POST' else rol.descripcion,
        'error':            error,
        'permisos_checked': permisos_checked,
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
            messages.success(request, f'Usuario "{u.username}" creado.')
            return redirect('configuracion:equipo')

    return render(request, 'configuracion/usuario_form.html', {
        'titulo':           'Nuevo Usuario',
        'accion':           'crear',
        'error':            error,
        'roles_list':       roles_list,
        'form_username':    datos.get('username', ''),
        'form_first_name':  datos.get('first_name', ''),
        'form_last_name':   datos.get('last_name', ''),
        'form_email':       datos.get('email', ''),
        'form_nivel':       datos.get('nivel', 'usuario'),
        'form_rol_id':      datos.get('rol_id', ''),
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
