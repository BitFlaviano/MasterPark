# build_exe.ps1 - empacota o MasterPark com PyInstaller (onedir) e gera o instalador Inno Setup.
# Pré-requisitos:
#   - Python 3.12 com as dependências de requirements.txt instaladas
#   - PyInstaller instalado (pip install pyinstaller)
#   - Inno Setup 6+ em C:\Program Files (x86)\Inno Setup 6\ISCC.exe
param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root    = Split-Path -Parent $PSScriptRoot
$Py      = "C:\Users\sousa\AppData\Local\Programs\Python\Python312\python.exe"
$Icc     = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$Dist    = Join-Path $Root "dist"
$Build   = Join-Path $Root "build"
$Schema  = Join-Path $Root "app\core\schema.sql"
$DataArg = "$Schema;app\core"

if (-not (Test-Path $Py)) { throw "Python não encontrado em $Py" }

Write-Host "==> Rodando testes (pré-empacotamento)..." -ForegroundColor Cyan
& $Py -m pytest (Join-Path $Root "tests") -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "Testes falharam — abortando build." }

Write-Host "==> PyInstaller (onedir, windowed)..." -ForegroundColor Cyan
& $Py -m PyInstaller `
    --noconfirm --clean `
    --name MasterPark `
    --onedir --windowed `
    --icon (Join-Path $Root "assets\masterpark.ico") `
    --hidden-import win32print `
    --hidden-import win32ui `
    --hidden-import win32con `
    --hidden-import PIL `
    --hidden-import PIL.ImageWin `
    --collect-all pymupdf `
    --hidden-import qrcode `
    --hidden-import barcode `
    --hidden-import barcode.code128 `
    --collect-data barcode `
    --hidden-import reportlab.graphics.barcode.common `
    --add-data $DataArg `
    --collect-submodules PySide6 `
    (Join-Path $Root "run.py")

if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }

if ($SkipInstaller) { Write-Host "Build OK. Instrução: dist\MasterPark\MasterPark.exe"; exit 0 }

$Icc = $null
foreach ($p in @(
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)) { if (-not $Icc -and (Test-Path $p)) { $Icc = $p } }
if (-not $Icc) { throw "Inno Setup não encontrado (procurei versões 6/7 em 4 caminhos). Use -SkipInstaller ou instale o Inno Setup." }

Write-Host "==> Inno Setup (instalador)" -ForegroundColor Cyan
& $Icc (Join-Path $Root "installer\masterpark.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou." }

Write-Host "==> Concluído: dist\MasterParkSetup.exe" -ForegroundColor Green
