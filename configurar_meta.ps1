# Configura las credenciales de Meta WhatsApp Cloud API en el archivo .env.
#
# Los secretos se escriben con Read-Host -AsSecureString y nunca se muestran por
# pantalla, quedan en el log de PowerShell ni se pueden leer de vuelta: si te
# equivocas, vuelve a ejecutar este script. El .env está en .gitignore y en
# .dockerignore, así que las credenciales no se versionan ni llegan a la imagen.
#
# Uso:  powershell -ExecutionPolicy Bypass -File .\configurar_meta.ps1
#       powershell -ExecutionPolicy Bypass -File .\configurar_meta.ps1 -SinRecrear

param(
    [switch]$SinRecrear
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Leer-Secreto {
    param([string]$Prompt, [string]$Default = '')
    $value = Read-Host -Prompt $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($value)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
    if ([string]::IsNullOrWhiteSpace($plain) -and $Default) { return $Default }
    return $plain.Trim()
}

function Leer-Texto {
    param([string]$Prompt, [string]$Default = '')
    $value = Read-Host -Prompt "$Prompt (Enter = '$Default')"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

# Lee el valor actual de una variable del .env, para no perder lo ya escrito.
function Get-EnvActual {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path $Path)) { return '' }
    $line = Select-String -Path $Path -Pattern "^$Name=" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $line) { return '' }
    return ($line.Line -split '=', 2)[1].Trim()
}

$envPath = Join-Path $PSScriptRoot '.env'

Write-Host ''
Write-Host '  Credenciales de Meta WhatsApp Cloud API' -ForegroundColor Cyan
Write-Host '  -----------------------------------------' -ForegroundColor Cyan
Write-Host '  Solo tres valores vienen de Meta Developers. El verify token lo'
Write-Host '  eliges tu: se genera ahora si dejas el campo vacio.'
Write-Host ''

# 1. Verify token: lo define el operador, no Meta.
$existing = Get-EnvActual -Path $envPath -Name 'META_VERIFY_TOKEN'
$verifyToken = Leer-Secreto -Prompt 'Verify token (Enter para generar uno aleatorio)'
if ([string]::IsNullOrWhiteSpace($verifyToken)) {
    if ($existing) {
        $verifyToken = $existing
        Write-Host '  Se conserva el verify token existente.' -ForegroundColor DarkGray
    }
    else {
        $bytes = New-Object byte[] 24
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $verifyToken = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
        Write-Host "  Verify token generado: $verifyToken" -ForegroundColor Green
        Write-Host '  Copialo: es el mismo que debes registrar en Meta Developers.' -ForegroundColor Green
    }
}

# 2. Credenciales que entrega Meta.
$appId = Leer-Texto -Prompt 'App ID (opcional, solo informativo)' -Default (Get-EnvActual -Path $envPath -Name 'META_APP_ID')
$appSecret = Leer-Secreto -Prompt 'App secret'
$accessToken = Leer-Secreto -Prompt 'Access token permanente o de sistema'
$phoneNumberId = Leer-Texto -Prompt 'Phone Number ID del numero emisor'

$apiVersion = Leer-Texto -Prompt 'Version de la Graph API' -Default 'v21.0'
$graphUrl = Leer-Texto -Prompt 'Graph API URL' -Default 'https://graph.facebook.com'
$timeout = Leer-Texto -Prompt 'Timeout de las peticiones (s)' -Default '10'

if ([string]::IsNullOrWhiteSpace($appSecret) -or [string]::IsNullOrWhiteSpace($accessToken) -or
    [string]::IsNullOrWhiteSpace($phoneNumberId)) {
    Write-Host ''
    Write-Host '  Faltan App secret, Access token o Phone Number ID. No se escribio nada.' -ForegroundColor Red
    Write-Host '  Vuelve a ejecutar el script y completa los tres campos.' -ForegroundColor Red
    exit 1
}

# Se escribe con saltos de linea normales: docker compose lee este archivo tal cual.
$contenido = @(
    '# Meta WhatsApp Cloud API. Generado por configurar_meta.ps1. No versionar.'
    "META_VERIFY_TOKEN=$verifyToken"
    "META_APP_ID=$appId"
    "META_APP_SECRET=$appSecret"
    "META_ACCESS_TOKEN=$accessToken"
    "WHATSAPP_PHONE_NUMBER_ID=$phoneNumberId"
    "WHATSAPP_API_VERSION=$apiVersion"
    "META_GRAPH_API_URL=$graphUrl"
    "META_REQUEST_TIMEOUT=$timeout"
) -join "`n"

Set-Content -Path $envPath -Value $contenido -Encoding UTF8 -NoNewline
Write-Host ''
Write-Host "  .env escrito en $envPath" -ForegroundColor Green

if ($SinRecrear) {
    Write-Host '  No se recreo el contenedor (-SinRecrear).' -ForegroundColor Yellow
    exit 0
}

# Las credenciales llegan por variables de entorno: hay que recrear, no reiniciar.
Write-Host '  Recreando el servicio web para que lea las variables...' -ForegroundColor Cyan
docker compose up -d --force-recreate web
if ($LASTEXITCODE -ne 0) {
    Write-Host '  Docker compose fallo. Revisa que Docker Desktop este iniciado.' -ForegroundColor Red
    exit 1
}

Start-Sleep -Seconds 3
Write-Host ''
Write-Host '  Diagnostico:' -ForegroundColor Cyan
docker compose exec -T web python manage.py check_meta_whatsapp

Write-Host ''
Write-Host '  Listo. Abre http://localhost:8000/whatsapp-prueba/ para verificar' -ForegroundColor Green
Write-Host '  y pulsa «Validar credenciales contra Graph API».' -ForegroundColor Green
Write-Host '  Recuerda registrar en Meta Developers el callback:' -ForegroundColor Cyan
Write-Host '    https://TU-DOMINIO/api/whatsapp/webhook/' -ForegroundColor White
Write-Host '  Meta no alcanza localhost: necesitas un tunel HTTPS o un dominio.' -ForegroundColor Yellow
