# Configuración VPS — SS Gestión

## Servidor

| Campo | Valor |
|-------|-------|
| IP | `161.132.4.82` |
| Dominio | `corfiemsistem.com` / `www.corfiemsistem.com` |
| Ruta proyecto | `/var/www/ssgestion` |
| Web server | **nginx** (reverse proxy puerto 80/443) → **Uvicorn** (ASGI, puerto 8000) |
| Config nginx | `/etc/nginx/sites-enabled/ssgestion` |
| Servicio systemd | `ssgestion.service` |
| Python | `python3` global (sin virtualenv) |
| Repositorio | `https://github.com/harri28/structure.git` |
| SSL | Let's Encrypt (certbot) — pendiente de instalar |

## Deploy

```bash
cd /var/www/ssgestion
git pull origin main
python3 manage.py migrate
python3 manage.py collectstatic --noinput
sudo systemctl restart ssgestion
```

## Comandos útiles

```bash
sudo systemctl restart ssgestion       # reiniciar app
sudo systemctl restart nginx           # reiniciar nginx
sudo journalctl -u ssgestion -f        # logs en tiempo real
nginx -t                               # verificar config nginx
```

## SSL (Let's Encrypt)

```bash
apt install certbot python3-certbot-nginx -y
certbot --nginx -d corfiemsistem.com -d www.corfiemsistem.com
# Renovación automática ya incluida por certbot
```

## Paquetes Python (globales)

```bash
pip3 install django psycopg2-binary waitress whitenoise python-dotenv openpyxl xlrd xlwt pillow scikit-learn uvicorn
```

## Migración Waitress → Uvicorn (para SSE)

Hacer esto **una sola vez** después de hacer `git pull` del commit que incluye `servidor_asgi.py`:

```bash
# 1. Instalar uvicorn
pip3 install uvicorn

# 2. Ver cómo está configurado el servicio actual
sudo cat /etc/systemd/system/ssgestion.service

# 3. Editar el ExecStart — cambiar waitress por uvicorn
#    El campo ExecStart debe quedar así:
#    ExecStart=/usr/bin/python3 -m uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 2
sudo nano /etc/systemd/system/ssgestion.service

# 4. Aplicar cambios
sudo systemctl daemon-reload
sudo systemctl restart ssgestion
sudo journalctl -u ssgestion -f   # verificar que arrancó bien

# 5. Agregar proxy_buffering off en nginx (necesario para SSE)
#    En el bloque location / de /etc/nginx/sites-enabled/ssgestion, agregar:
#    proxy_buffering off;
#    proxy_cache off;
sudo nano /etc/nginx/sites-enabled/ssgestion
sudo nginx -t && sudo systemctl reload nginx
```

**Reversión:** Si falla, volver a Waitress:
```bash
# ExecStart=/usr/bin/python3 servidor.py   (o la ruta que tenía antes)
sudo systemctl daemon-reload && sudo systemctl restart ssgestion
```

## Notas

- Usar `python3`, no `python`
- Push desde máquina local → `git pull` en VPS
- Django 5.2.x instalado
- Último deploy: 2026-07-11 (commit `c3b3537`)

## Incidencias

### 2026-07-11 — Conflicto de migraciones `0010` en presupuesto

**Causa:** Se ejecutó `makemigrations` en el VPS antes de hacer `git push` desde local. El VPS generó `0010_alter_insumopresupuesto_tipo_and_more` y lo aplicó. Al hacer `git pull` llegó también `0010_insumo_cantidad_total` (que agrega el campo `cantidad_total`), creando dos hojas en el grafo de migraciones.

**Síntoma:** `500 Internal Server Error` con `column presupuesto_insumopresupuesto.cantidad_total does not exist`.

**Solución aplicada:**
```bash
# 1. Agregar la columna directamente a Postgres
python3 manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute('ALTER TABLE presupuesto_insumopresupuesto ADD COLUMN IF NOT EXISTS cantidad_total NUMERIC(18,4) NOT NULL DEFAULT 0')
    c.execute('UPDATE presupuesto_insumopresupuesto SET cantidad_total = CASE WHEN costo_unitario != 0 AND total != 0 THEN total / costo_unitario ELSE cantidad END')
"
# 2. Resolver conflicto y marcar migraciones como aplicadas
python3 manage.py makemigrations --merge presupuesto --no-input
python3 manage.py migrate presupuesto --fake
sudo systemctl restart ssgestion
```

**Prevención:** Nunca correr `makemigrations` en el VPS. Siempre generar migraciones en local, hacer `git push` y luego `git pull` + `migrate` en el VPS.

**Archivo merge generado en VPS:** `apps/presupuesto/migrations/0011_merge_20260711_0955.py` — debe traerse al repo local con `git pull` para mantener sincronía.
