"""
Servidor ASGI para S&S Gestion (reemplaza servidor.py cuando SSE está activo).
Usa Uvicorn en lugar de Waitress para soportar vistas async y Server-Sent Events.

Uso local (Windows):
    python servidor_asgi.py

En VPS (systemd):
    ExecStart=/ruta/venv/bin/uvicorn config.asgi:application \
        --host 0.0.0.0 --port 8000 --workers 2
"""
import os
import sys
import subprocess

PORT = 8000
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def _limpiar_puerto():
    try:
        resultado = subprocess.check_output(
            f'netstat -ano | findstr ":{PORT} "',
            shell=True, text=True, stderr=subprocess.DEVNULL
        )
        mi_pid = str(os.getpid())
        pids = set()
        for linea in resultado.splitlines():
            partes = linea.strip().split()
            if partes:
                pid = partes[-1]
                if pid.isdigit() and pid != '0' and pid != mi_pid:
                    pids.add(pid)
        for pid in pids:
            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
            print(f'  Puerto {PORT}: proceso {pid} terminado.')
    except subprocess.CalledProcessError:
        pass


if __name__ == '__main__':
    print(f'Limpiando puerto {PORT}...')
    _limpiar_puerto()

    import uvicorn
    print(f'S&S Gestion (ASGI) corriendo en http://0.0.0.0:{PORT}')
    uvicorn.run(
        'config.asgi:application',
        host='0.0.0.0',
        port=PORT,
        workers=2,
        log_level='info',
    )
