# SENTINEL v1.2 — Secure Communication & Digital Evidence Management

Prototipe akademik desktop (Windows 11 x64, CPython 3.13, CustomTkinter). Satu aplikasi yang mengintegrasikan
autentikasi berlapis, manajemen kasus & bukti digital terenkripsi, pesan super-enkripsi, steganografi LSB PNG,
dan hash chain lokal. **Gunakan data dummy saja.**

## Status pengujian (jujur)

| Area | Status |
|---|---|
| Unit + integrasi + GUI (50 test, `pytest`) | **PASS** di sandbox Linux/Python 3.12 (GUI lewat Xvfb), coverage 85% |
| SQLCipher nyata (`sqlcipher3==0.6.5`), Argon2id, AES-GCM, ChaCha20-Poly1305, Vigenère, LSB | **PASS** di sandbox |
| DeepFace 0.0.102 + ArcFace + detector OpenCV + ONNX Runtime CPU | **PASS** di sandbox dengan gambar publik (dim 512, threshold 0.68 dari DeepFace) |
| Windows 11 + Python 3.13.12 (wheel, import, GUI) | **BELUM dijalankan** — jalankan smoke test di bawah |
| Windows Credential Manager (keyring) | **BELUM** (sandbox memakai backend memori untuk test) |
| Deteksi USB flash drive Windows (`usb_windows.py`, ctypes) | **BELUM** — butuh flash drive fisik |
| Webcam (`camera.py`) dan Face Verification dengan wajah nyata | **BELUM** — butuh webcam |

## Instalasi (PowerShell, `.venv` yang sudah ada)

```powershell
Set-Location D:\Projects\SENTINEL
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_deps.ps1                       # core + dev, hanya ke .venv, cache ke D:\DevCache
.\.venv\Scripts\python.exe scripts\smoke_sentinel.py core
.\.venv\Scripts\python.exe -m pytest             # test GUI otomatis dilewati bila tidak ada display
```

Biometrik (bertahap, setelah core lulus):

```powershell
$env:DEEPFACE_HOME = "D:\DevCache\deepface"
.\.venv\Scripts\python.exe -m pip install --dry-run --report D:\DevCache\temp\bio.json -r requirements-biometric.txt
Select-String -Path D:\DevCache\temp\bio.json -Pattern '"name": "(tensorflow|torch|keras|onnxruntime-gpu)"'   # harus kosong
.\.venv\Scripts\python.exe -m pip install -r requirements-biometric.txt
.\.venv\Scripts\python.exe scripts\prefetch_models.py        # unduh bobot ArcFace sekali (butuh internet)
.\.venv\Scripts\python.exe scripts\smoke_sentinel.py camera      # sengaja dijalankan pengguna; frame tidak disimpan
.\.venv\Scripts\python.exe scripts\smoke_sentinel.py deepface    # atau tambahkan --image foto_sendiri.jpg
```

Setelah semua lulus **di Windows**: `.\scripts\make_lock.ps1` membuat `requirements-lock.txt` yang sah untuk mesin Anda.

## Menjalankan

```powershell
.\scripts\run_app.ps1      # set SENTINEL_DATA_DIR=D:\SENTINEL_DATA dan DEEPFACE_HOME bila belum diset, lalu main.py
```

First-run: buat Admin → pasang satu flash drive → aplikasi menulis marker `.sentinel-token` dan mendaftarkannya.
Key (db, pesan, file, biometrik; masing-masing 256-bit acak) dibuat otomatis dan **hanya** disimpan di Windows Credential Manager.

## Halaman Settings

Menu **Settings** (semua role) menggantikan halaman Profile: pendaftaran wajah dengan pratinjau webcam langsung, pencarian/pembuatan USB dongle, checkbox wajib wajah/USB + **Terapkan**, **Ganti Password**, dan **Buat Ulang Kode Pemulihan**. Database v1.2 dimigrasi otomatis saat dibuka (kolom `require_face`, `require_usb`, `recovery_code_hash`, `recovery_code_created_at`; akun yang sudah punya template wajah diberi `require_face=1`).

## Konfigurasi non-secret (environment variable, lihat `.env.example`)

`SENTINEL_DATA_DIR` (default `%LOCALAPPDATA%\SENTINEL`), `DEEPFACE_HOME` (default `<data>\models`),
`SENTINEL_MAX_FILE_MB` (100), `SENTINEL_CAMERA_INDEX` (0), `SENTINEL_THEME` (dark),
`SENTINEL_USB_INCLUDE_FIXED` (0; isi 1 bila Windows melaporkan flash drive Anda sebagai "fixed disk").
Tidak ada drive yang di-hard-code; semua path diturunkan dari konfigurasi.

## Role dan izin (SRS 4.2)

| | Admin | Investigator | Analyst | Auditor |
|---|:-:|:-:|:-:|:-:|
| Kasus: lihat | semua | milik sendiri | yang ditugaskan | semua (metadata) |
| Buat / ubah kasus | ya / administratif | ya / milik sendiri saat OPEN | – | – |
| Tugaskan Analyst | ya | – | – | – |
| Upload bukti | – | ya | – | – |
| Dekripsi/ekspor + verifikasi plaintext | – | – | kasus ditugaskan | – |
| Verifikasi hash ciphertext | ya | milik sendiri | ditugaskan | ya |
| Pesan (kirim / baca) | ya / miliknya | ya / miliknya | ya / miliknya | – |
| Steganografi | ya | ya | ya | – |
| Akun & USB | ya | – | – | – |
| Audit log | semua | aktivitas sendiri + kasus terkait | idem | semua |
| Verifikasi ledger | ya | ya | ya | ya |

Otorisasi ditegakkan di service (membaca ulang role/status akun dari DB pada setiap aksi); menu GUI hanya kosmetik.

## Batasan yang harus dijelaskan saat demo (SRS 18)

- USB flash drive biasa = faktor kepemilikan sederhana; **dapat dikloning**. Bukan hardware token.
- Face verification = pencocokan 1:1; **tanpa liveness/anti-spoofing**.
- Faktor login diatur **per akun** di Settings → Faktor Autentikasi (bukan lagi switch di layar login). Password selalu wajib; USB dan wajah wajib hanya jika dicentang akun tersebut (default akun baru: USB wajib, wajah tidak). Mode tiap faktor dicatat di audit `LOGIN_SUCCESS`. Menonaktifkan faktor menuntut password saat ini.
- USB dongle tetap **satu USB global**; hanya Admin yang dapat membuat/mengganti. Akun lain hanya memilih mewajibkannya atau tidak.
- Kode pemulihan (Settings → Akun Pemulihan): 80-bit acak, hanya hash Argon2id yang disimpan, sekali pakai (setelah dipakai pada *Lupa Password* otomatis diganti kode baru), percobaan salah ikut lockout. Kode dibuat otomatis saat akun dibuat (Admin pertama: layar setup; pengguna lain: ditampilkan ke Admin yang membuatnya, pemilik dapat membuat ulang sendiri di Settings). Akun hasil migrasi v1.2 belum punya kode dan harus membuatnya di Settings. Reset password tidak melewati USB/wajah saat login.
- Vigenère = demonstrasi cipher klasik; perlindungan nyata dari AES-256-GCM / ChaCha20-Poly1305.
- SQLCipher + keyring melindungi data di disk, **bukan** dari proses lain pada akun Windows yang sama; login bukan faktor kriptografis atas key.
- LSB menyamarkan keberadaan data, bukan enkripsi dan bukan anti-deteksi.
- Hash chain lokal mendeteksi perubahan/penghapusan di tengah rantai; **pemotongan di ujung rantai tidak terdeteksi** (tanpa anchor eksternal).
- Pesan hanya antar akun dalam satu instalasi (bukan E2E lintas perangkat).
- Kehilangan entri keyring = data terenkripsi tidak dapat dibuka. SENTINEL menolak menimpa database dan memberi pesan jelas.

## Struktur

```
main.py  config.py  requirements*.txt  pyproject.toml
sentinel/{bootstrap.py, ui/, services/, security/, database/, devices/, utils/}
tests/{unit, integration, gui}   scripts/   docs/
```

Dokumen: `docs/architecture.md`, `docs/database.md`, `docs/demo_guide.md`.

## Troubleshooting

- **"Keyring OS tidak tersedia"**: pastikan berjalan sebagai pengguna Windows biasa dengan Credential Manager aktif; `scripts\smoke_sentinel.py keyring` menunjukkan backend.
- **USB tidak terdeteksi**: cek dengan `smoke_sentinel.py`/aplikasi bahwa drive bertipe removable; bila dilaporkan "fixed", set `SENTINEL_USB_INCLUDE_FIXED=1`.
- **Kamera tidak terbuka**: Windows Settings → Privacy → Camera; coba `SENTINEL_CAMERA_INDEX=1`. Aplikasi mencoba DirectShow lebih dulu.
- **DeepFace lambat pertama kali**: bobot (~137 MB) diunduh dari GitHub; jalankan `prefetch_models.py` sekali.
- Log aplikasi: `<SENTINEL_DATA_DIR>\logs\sentinel.log` (tanpa password/key/plaintext).
