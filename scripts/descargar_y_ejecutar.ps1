<#
.SYNOPSIS
  Descarga una versión publicada de BottiMint desde GitHub, verifica su SHA256 y la ejecuta.

.EJEMPLO (PowerShell)
  powershell -ExecutionPolicy Bypass -File descargar_y_ejecutar.ps1 -Repo shadoowww/bottimint-optimizer

  Para fijar una versión concreta (recomendado si querés repetibilidad):
  powershell -ExecutionPolicy Bypass -File descargar_y_ejecutar.ps1 -Repo shadoowww/bottimint-optimizer -Tag v1.1.0

  Solo descargar y verificar, sin ejecutar:
  powershell -ExecutionPolicy Bypass -File descargar_y_ejecutar.ps1 -Repo shadoowww/bottimint-optimizer -SoloDescargar

  LEÉ este script antes de ejecutarlo: es corto a propósito.
  Si tenés la CLI de GitHub (gh), además podés verificar el origen del .exe:  gh attestation verify BottiMint.exe -R shadoowww/bottimint-optimizer
#>
param(
  [Parameter(Mandatory = $true)][string]$Repo,   # formato usuario/repositorio
  [string]$Tag = "",                             # vacío = última versión publicada
  [switch]$SoloDescargar                         # descarga y verifica, pero no ejecuta
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Validación estricta de lo que se interpola en las URL (nada de rutas ni parámetros colados)
if ($Repo -notmatch '^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$') { throw "Repo inválido. Usá el formato usuario/repositorio." }
if ($Tag -and $Tag -notmatch '^v?[0-9A-Za-z._-]{1,40}$') { throw "Tag inválido." }

$api = if ($Tag) { "https://api.github.com/repos/$Repo/releases/tags/$Tag" } else { "https://api.github.com/repos/$Repo/releases/latest" }
Write-Host "Buscando la versión en $Repo ..."
$rel = Invoke-RestMethod $api -Headers @{ "User-Agent" = "BottiMint" }
$exe = $rel.assets | Where-Object { $_.name -eq "BottiMint.exe" } | Select-Object -First 1
$sha = $rel.assets | Where-Object { $_.name -eq "BottiMint.exe.sha256" } | Select-Object -First 1
if (-not $exe -or -not $sha) { throw "La versión $($rel.tag_name) no tiene BottiMint.exe y su .sha256." }

# Solo se aceptan descargas desde github.com (nunca desde otro dominio que venga en la respuesta)
foreach ($u in @($exe.browser_download_url, $sha.browser_download_url)) {
  if ($u -notmatch '^https://github\.com/') { throw "URL de descarga inesperada: $u" }
}

# Carpeta nueva con nombre aleatorio dentro de TEMP del usuario (no compartida con otros usuarios)
$dir = Join-Path $env:TEMP ("BottiMint_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $dir | Out-Null
$ruta = Join-Path $dir "BottiMint.exe"

Write-Host "Descargando $($rel.tag_name) ..."
Invoke-WebRequest $exe.browser_download_url -OutFile $ruta -UseBasicParsing
$esperado = ((Invoke-RestMethod $sha.browser_download_url) -split '\s+')[0].Trim().ToLower()
if ($esperado -notmatch '^[0-9a-f]{64}$') { Remove-Item $dir -Recurse -Force; throw "El archivo .sha256 publicado no es válido." }

# Se abre el archivo BLOQUEANDO la escritura (FileShare.Read) y se calcula el hash sobre ese mismo manejador:
# nadie puede cambiar el .exe entre la verificación y la ejecución.
$fs = [System.IO.File]::Open($ruta, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
try {
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  $real = ([BitConverter]::ToString($sha256.ComputeHash($fs)) -replace '-', '').ToLower()
  if ($esperado -ne $real) {
    $fs.Dispose(); Remove-Item $dir -Recurse -Force
    throw "SHA256 NO coincide (esperado $esperado, obtenido $real). No se ejecuta."
  }
  Write-Host "SHA256 verificado: $real"
  if ($SoloDescargar) { Write-Host "Archivo en: $ruta"; return }
  Start-Process -FilePath $ruta -Verb RunAs
} finally {
  $fs.Dispose()
}
