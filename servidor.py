"""
Servidor de produccion para S&S Gestion.
Reemplaza 'python manage.py runserver' con Waitress (WSGI estable para Windows).
Uso: python servidor.py

Auto-limpia procesos zombie en el puerto 8000 antes de arrancar.
Se reinicia automaticamente si Waitress falla.
"""
import os
import sys
import subprocess
import time

PORT = 8000


def _limpiar_puerto():
    """Mata cualquier proceso que esté ocupando PORT antes de arrancar."""
    try:
        resultado = subprocess.check_output(
            f'netstat -ano | findstr ":{PORT} "',
            shell=True, text=True, stderr=subprocess.DEVNULL
        )
        pids = set()
        for linea in resultado.splitlines():
            partes = linea.strip().split()
            if partes:
                pid = partes[-1]
                if pid.isdigit() and pid != '0':
                    pids.add(pid)

        mi_pid = str(os.getpid())
        for pid in pids:
            if pid == mi_pid:
                continue
            try:
                subprocess.run(
                    ['taskkill', '/F', '/PID', pid],
                    capture_output=True
                )
                print(f'  Puerto {PORT}: proceso {pid} terminado.')
            except Exception:
                pass
    except subprocess.CalledProcessError:
        pass  # ningún proceso en el puerto — OK


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

if __name__ == '__main__':
    print(f'Limpiando puerto {PORT}...')
    _limpiar_puerto()

    from waitress import serve
    from django.core.wsgi import get_wsgi_application

    app = get_wsgi_application()

    while True:
        try:
            print(f'S&S Gestion corriendo en http://0.0.0.0:{PORT}')
            serve(app, host='0.0.0.0', port=PORT, threads=8)
        except Exception as e:
            print(f'[ERROR] Servidor caido: {e}. Reiniciando en 3s...')
            time.sleep(3)
            _limpiar_puerto()
