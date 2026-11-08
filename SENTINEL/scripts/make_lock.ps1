# Jalankan SETELAH smoke test + pytest lulus di Windows. Hasilnya adalah requirements-lock.txt yang sah untuk mesin ini.
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\python.exe -m pip freeze | Out-File -Encoding ascii requirements-lock.txt
Write-Host "requirements-lock.txt dibuat dari .venv Windows Anda."
