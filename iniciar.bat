@echo off
chcp 65001 > nul
cd /d %~dp0
cls

echo.
echo  =========================================
echo    S^&S Gestion  ^|  Control de Obras v1.0
echo  =========================================
echo.

:: ── 1. Liberar puerto 8000 ────────────────────────────────────────
echo  [1/4] Liberando puerto 8000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F > nul 2>&1
)
echo        OK
echo.

:: ── 2. Verificar base de datos ────────────────────────────────────
echo  [2/4] Verificando base de datos PostgreSQL...
python -c "import psycopg2; conn = psycopg2.connect(dbname='ss_gestion', user='postgres', password='1234', host='localhost', port='5432'); conn.close()" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  =============================================
    echo   ERROR: No se puede conectar a PostgreSQL.
    echo   Verifica que el servicio este activo.
    echo  =============================================
    echo.
    pause
    exit /b 1
)
echo        Conectado a ss_gestion
echo.

:: ── 3. Migraciones + archivos estaticos ───────────────────────────
python manage.py migrate --check > nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Aplicando migraciones pendientes...
    python manage.py migrate
    echo.
)

echo  [3/4] Actualizando archivos estaticos...
python manage.py collectstatic --noinput > nul 2>&1
echo        OK
echo.

:: ── 4. Iniciar servidor ───────────────────────────────────────────
echo  [4/4] Iniciando servidor Django (Waitress)...
echo.
echo  =========================================
echo.
echo    PC:     http://localhost
echo    Red:    http://192.168.100.38
echo    Admin:  http://localhost/admin
echo.
echo    Ctrl+C para detener
echo.
echo  =========================================
echo.

:: Abrir navegador automaticamente
start /b cmd /c "timeout /t 2 > nul && start http://localhost"

:: Iniciar con Waitress (servidor de produccion, estable en Windows)
python servidor.py
echo.
pause
