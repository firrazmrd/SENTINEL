# Menjalankan SENTINEL di workstation pengembang (PowerShell, dari root proyek).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $env:SENTINEL_DATA_DIR) { $env:SENTINEL_DATA_DIR = "D:\SENTINEL_DATA" }
if (-not $env:DEEPFACE_HOME)     { $env:DEEPFACE_HOME     = "D:\DevCache\deepface" }
New-Item -ItemType Directory -Force $env:SENTINEL_DATA_DIR, $env:DEEPFACE_HOME | Out-Null
& .\.venv\Scripts\python.exe main.py
