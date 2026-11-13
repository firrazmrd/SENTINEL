# Instalasi bertahap ke .venv yang sudah ada. TIDAK menyentuh Python global.
# Pemakaian:  .\scripts\install_deps.ps1            (core + dev)
#             .\scripts\install_deps.ps1 -Biometric (core + dev + DeepFace untuk verifikasi wajah)
# Cache pip/temp diarahkan ke <drive>\DevCache. Drive = D: bila ada, selain itu drive sistem (mis. C:).
param([switch]$Biometric)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$drive = if (Test-Path "D:\") { "D:" } else { $env:SystemDrive }
$cache = "$drive\DevCache"
New-Item -ItemType Directory -Force "$cache\pip", "$cache\temp", "$cache\deepface" | Out-Null
$env:TEMP = "$cache\temp"; $env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = "$cache\pip"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Belum ada .venv. Jalankan dulu:  py -3.13 -m venv .venv" }
& $py -c "import sys; assert sys.version_info[:2]==(3,13), sys.version; print(sys.executable)"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
& $py -m pip check
& $py -m pip install -r requirements-dev.txt
if ($Biometric) {
    $env:DEEPFACE_HOME = "$cache\deepface"
    & $py -m pip install -r requirements-biometric.txt
    Write-Host "Biometrik terpasang. Lanjut:  $py scripts\prefetch_models.py"
}
Write-Host "Core + dev terpasang. Cek:  $py scripts\smoke_sentinel.py core"
