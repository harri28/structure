"""
Servidor de produccion para S&S Gestion.
Reemplaza 'python manage.py runserver' con Waitress (WSGI estable para Windows).
Uso: python servidor.py
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from waitress import serve
from django.core.wsgi import get_wsgi_application

if __name__ == '__main__':
    app = get_wsgi_application()
    print('S&S Gestion corriendo en http://0.0.0.0:8000')
    serve(app, host='0.0.0.0', port=8000, threads=8)
