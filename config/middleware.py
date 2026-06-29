from django.shortcuts import redirect
from django.conf import settings

# URLs que NO requieren login
_RUTAS_PUBLICAS = [
    '/login/',
    '/admin/',
    '/static/',
    '/media/',
]


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            path = request.path_info
            if not any(path.startswith(r) for r in _RUTAS_PUBLICAS):
                return redirect(f'{settings.LOGIN_URL}?next={path}')
        return self.get_response(request)
