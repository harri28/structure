# reiniciar.ps1
# Uso: cd c:\xampp\htdocs\structure && .\reiniciar.ps1
#
# - Mata cualquier proceso previo en el puerto 8000
# - Arranca Django runserver (auto-recarga al guardar .py)
# - CSS/JS se sirven directamente, sin collectstatic ni Apache
# - Acceso: http://127.0.0.1:8000/

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "  S&S Gestion — Django dev server" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8000/" -ForegroundColor White
Write-Host ""

# ── 1. Liberar puerto 8000 ────────────────────────────────────────
$lineas = netstat -ano | Select-String ":8000\s"
$pids   = $lineas | ForEach-Object { ($_ -split '\s+')[-1] } |
           Where-Object { $_ -match '^\d+$' -and [int]$_ -gt 0 } |
           Sort-Object -Unique

if ($pids) {
    foreach ($p in $pids) {
        try {
            Stop-Process -Id ([int]$p) -Force -ErrorAction Stop
            Write-Host "  Puerto 8000 liberado (PID $p)" -ForegroundColor Yellow
        } catch {
            Write-Host "  No se pudo terminar PID $p" -ForegroundColor Red
        }
    }
    Start-Sleep -Milliseconds 800
} else {
    Write-Host "  Puerto 8000 ya libre" -ForegroundColor Green
}

# ── 2. Arrancar runserver ─────────────────────────────────────────
Write-Host ""
Write-Host "  Iniciando... (Ctrl+C para detener)" -ForegroundColor DarkGray
Write-Host ""

python manage.py runserver 127.0.0.1:8000
