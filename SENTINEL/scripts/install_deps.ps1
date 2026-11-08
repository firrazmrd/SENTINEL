# Instalasi bertahap ke .venv yang sudah ada. TIDAK menyentuh Python global.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force D:\DevCache\pip, D:\DevCache\temp, D:\DevCache\deepface | Out-Null
$env:TEMP = "D:\DevCache\temp"; $env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = "D:\DevCache\pip"
$py = ".\.venv\Scripts\python.exe"
& $py -c "import sys; assert sys.version_info[:2]==(3,13), sys.version; print(sys.executable)"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
& $py -m pip check
& $py -m pip install -r requirements-dev.txt
Write-Host "Core + dev terpasang. Jalankan: .\.venv\Scripts\python.exe scripts\smoke_sentinel.py core"
Write-Host "Biometrik (bertahap): .\.venv\Scripts\python.exe -m pip install --dry-run --report D:\DevCache\temp\bio.json -r requirements-biometric.txt"
