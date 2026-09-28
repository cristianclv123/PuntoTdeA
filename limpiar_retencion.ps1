#Requires -Version 5.1
<#
.SYNOPSIS
  Limpia eventos antiguos del webhook de WhatsApp (retención).
.DESCRIPTION
  Ejecuta cleanup_whatsapp_events dentro del contenedor web: primero un ensayo
  (lo que borraría) y, salvo -Si, pide confirmación antes del borrado real.
  La salida se anexa a un log con marca de tiempo.
.PARAMETER Days
  Edad mínima en días a borrar (default 7).
.PARAMETER Si
  Ejecuta sin preguntar (útil para Programador de tareas / cron).
.EXAMPLE
  .\limpiar_retencion.ps1
  .\limpiar_retencion.ps1 -Days 30 -Si
#>
param(
    [int]$Days = 7,
    [switch]$Si
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("whatsapp-retention-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))

Set-Location $root

function Write-Log { param([string]$m) $m | Tee-Object -FilePath $log -Append }

Write-Log ('== Limpieza de eventos WhatsApp ==  fecha: {0:yyyy-MM-dd HH:mm} | umbral: {1} días' -f (Get-Date), $Days)

# 1) Ensayo: solo informa lo que borraría
Write-Log '--- Ensayo (lo que borraría) ---'
docker compose exec -T web python manage.py cleanup_whatsapp_events --days $Days 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    Write-Log "[ERROR] Falló el ensayo (código $LASTEXITCODE). No se borró nada."
    exit 1
}

if (-not $Si) {
    $r = Read-Host '¿Borrar de verdad? [s/N]'
    if ($r -notmatch '^(s|si|sí|y|yes)$') {
        Write-Log 'Cancelado por el usuario. Nada que borrar.'
        exit 0
    }
}

# 2) Borrado real
Write-Log '--- Ejecución (borrado real) ---'
docker compose exec -T web python manage.py cleanup_whatsapp_events --days $Days --ejecutar 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    Write-Log "[ERROR] Falló la ejecución (código $LASTEXITCODE)."
    exit 1
}
Write-Log ("Listo. Detalle en: {0}" -f $log)