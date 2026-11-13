# Menjalankan SENTINEL (PowerShell, dari folder mana pun).
# Bila belum diatur, data disimpan di <drive>\SENTINEL_DATA dan model DeepFace di <drive>\DevCache\deepface.
# Drive = D: bila ada, selain itu drive sistem (mis. C:). Atur SENTINEL_DATA_DIR / DEEPFACE_HOME untuk lokasi lain.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$drive = if (Test-Path "D:\") { "D:" } else { $env:SystemDrive }
if (-not $env:SENTINEL_DATA_DIR) { $env:SENTINEL_DATA_DIR = "$drive\SENTINEL_DATA" }
if (-not $env:DEEPFACE_HOME)     { $env:DEEPFACE_HOME     = "$drive\DevCache\deepface" }
New-Item -ItemType Directory -Force $env:SENTINEL_DATA_DIR, $env:DEEPFACE_HOME | Out-Null
Write-Host "Data   : $env:SENTINEL_DATA_DIR"
Write-Host "Model  : $env:DEEPFACE_HOME"
& .\.venv\Scripts\python.exe main.py
