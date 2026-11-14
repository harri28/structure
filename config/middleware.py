from django.shortcuts import redirect
from django.conf import settings

# URLs que NO requieren login
_RUTAS_PUBLICAS = [
    '/login/',
    '/admin/',
    '/static/',
    '/media/',
]

# Rutas que no necesitan los headers anti-caché (estáticos sirven por Apache/WhiteNoise)
_RUTAS_CACHEABLES = [
    '/static/',
    '/media/',
]


class LoginRequiredMiddleware:
    """
    Fuerza autenticación en todas las rutas salvo las listadas en
    `_RUTAS_PUBLICAS`. Además, inyecta cabeceras no-cache en las respuestas
    de usuarios autenticados para que el botón "Atrás" del navegador, tras
    un logout, no muestre la pantalla cacheada — el browser se ve forzado a
    revalidar contra el server, que redirige al login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            path = request.path_info
            if not any(path.startswith(r) for r in _RUTAS_PUBLICAS):
                return self._anti_cache(redirect(f'{settings.LOGIN_URL}?next={path}'), request)

        response = self.get_response(request)
        return self._anti_cache(response, request)

    @staticmethod
    def _anti_cache(response, request):
        """
        Inyecta cabeceras no-cache en respuestas dinámicas para evitar que el
        navegador muestre una pantalla autenticada tras logout usando el botón
        "Atrás" (bfcache). Los estáticos quedan fuera para no romper el caching
        de assets.
        """
        if any(request.path_info.startswith(r) for r in _RUTAS_CACHEABLES):
            return response
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response['Pragma']  = 'no-cache'
        response['Expires'] = '0'
        existing_vary = response.get('Vary', '')
        if 'Cookie' not in existing_vary:
            response['Vary'] = (existing_vary + ', Cookie').lstrip(', ') if existing_vary else 'Cookie'
        return response
