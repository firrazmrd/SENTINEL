# SENTINEL v1.3 — Secure Communication & Digital Evidence Management

## 1. Deskripsi
SENTINEL adalah aplikasi desktop (Windows 11 x64, CPython 3.13, CustomTkinter) untuk manajemen kasus dan bukti digital
dengan autentikasi berlapis. Identitas visual: **Tactical Security + Industrial Premium** (navy gelap, aksen biru listrik,
cyan hanya untuk data teknis/live). Prototipe akademik: **gunakan data dummy saja.**

## 2. Tujuan
Menunjukkan satu sistem terpadu yang mengamankan alur kerja forensik digital: siapa yang masuk (password, USB dongle,
wajah), apa yang disimpan (bukti terenkripsi), apakah masih utuh (hash + hash chain), dan siapa melakukan apa (audit log).

## 3. Fitur utama
- **Login split-screen**: kiri kamera live + status autentikasi, kanan kredensial. Status kamera: `CAMERA INITIALIZING`,
  `CAMERA ACTIVE`, `SCANNING`, `VERIFYING`, `VERIFIED`, `FAILED`, `CAMERA UNAVAILABLE`.
- **Faktor login per akun** (Settings): password selalu wajib; USB dongle dan verifikasi wajah dapat diwajibkan sendiri-sendiri atau bersamaan.
- **Pemantauan USB selama sesi**: bila akun mewajibkan USB dan dongle dicabut → overlay penguncian + hitung mundur 10 detik;
  dipasang kembali = lanjut, tidak = aplikasi ditutup otomatis (resource dibersihkan, tercatat di audit).
- **Akun pemulihan**: Ganti Password, kode pemulihan sekali pakai (80-bit, hanya hash Argon2id tersimpan), Lupa Password di layar login.
- **Dashboard padat informasi**: status keamanan, autentikasi, USB, wajah, ledger, ringkasan angka, aktivitas, integritas file, event keamanan.
- Kasus & bukti terenkripsi (ChaCha20-Poly1305), verifikasi integritas, dekripsi/ekspor, pesan super-enkripsi, steganografi LSB PNG, audit log, Integrity Ledger (hash chain lokal), manajemen pengguna (4 role).

## 4. Teknologi
CPython 3.13 · CustomTkinter + Pillow (UI) · SQLCipher (`sqlcipher3==0.6.5`) · `cryptography` (ChaCha20-Poly1305 untuk file,
AES-GCM untuk pesan & embedding wajah) · `argon2-cffi` (Argon2id) · `keyring` (Windows Credential Manager) · `platformdirs` ·
opsional `deepface==0.0.102` (ArcFace, ONNX Runtime CPU; menarik OpenCV) · `pytest`, `ruff` (dev).
Font: **IBM Plex Sans** (Regular & Bold, lisensi OFL, dibundel di `assets\fonts\`, dimuat otomatis per proses — tidak perlu install) dan
**Cascadia Code** untuk hash/ID/kode (bawaan Windows 11; fallback Cascadia Mono → Consolas). Bila font gagal dimuat, aplikasi memakai Segoe UI.
**Tidak ada dependensi baru** dibanding v1.2/v1.3 sebelumnya; yang bertambah hanya folder `assets\fonts\`.

## 5. Persyaratan sistem
Windows 11 64-bit · Python 3.13 64-bit (opsi **tcl/tk** aktif) · PowerShell (bukan Administrator) · internet untuk pip dan unduhan model ·
flash drive kosong (USB dongle) · webcam (hanya untuk fitur wajah) · ±1 GB ruang untuk venv + model.

## 6. Struktur folder project
```
SENTINEL\
├── main.py  config.py  requirements*.txt  pyproject.toml  pytest.ini  .env.example
├── assets\fonts\            IBM Plex Sans (Regular, Bold) + lisensi OFL
├── sentinel\
│   ├── bootstrap.py         perakitan service, first-run, migrasi DB
│   ├── ui\                  common.py (design tokens), app.py (shell + guard USB), login_view.py, dashboard_view.py,
│   │                        settings_view.py, dialogs.py, camera_widget.py, setup_view.py, *_view.py lain
│   ├── services\            auth, account_security, session_guard, biometric, usb, evidence, case, message, ledger, audit, dashboard, user ...
│   ├── security\            file/message/biometric crypto, key_manager, password_hasher, recovery_code, stego_lsb, vigenere
│   ├── database\            schema.sql, connection.py (SQLCipher + migrate), repositories.py
│   └── devices\             camera.py (OpenCV + stream live), usb_windows.py, face_engine.py
├── tests\{unit,integration,gui}   scripts\   docs\
```

## 7. Setup dari nol (Windows 11, PowerShell)

Panduan ini menjelaskan setup SENTINEL v1.3 pada komputer Windows 11 baru, mulai dari ekstraksi project sampai aplikasi dapat dijalankan. Pengujian otomatis yang tercantum di README dilakukan di sandbox Linux; langkah-langkah Windows di bawah tetap perlu diuji pada komputer Windows tujuan. Jika muncul error, simpan dan kirim teks error apa adanya.

### 7.1. Yang dibutuhkan

- Windows 11 64-bit.
- **Python 3.13 64-bit** dari [python.org](https://www.python.org/downloads/). Saat instalasi, centang **Add python.exe to PATH** dan pastikan opsi **tcl/tk and IDLE** aktif karena GUI menggunakannya.
- Flash drive kosong untuk USB dongle demo.
- Webcam, hanya jika ingin mencoba Face Verification. Tanpa webcam, aplikasi tetap dapat digunakan dengan faktor verifikasi wajah tidak diwajibkan.
- Koneksi internet untuk instalasi paket Python dan, jika memakai Face Verification, unduhan model.
- Sekitar 1 GB ruang kosong untuk virtual environment dan model biometrik.

Buka **PowerShell biasa**, bukan *Run as Administrator*. Windows Credential Manager terikat ke akun Windows yang menjalankan aplikasi.

### 7.2. Buat direktori dan ekstrak project

Contoh berikut menggunakan drive `D:`. Jika drive tersebut tidak tersedia, ganti `D:\Projects` dengan lokasi lain, misalnya `C:\Projects`.

```powershell
New-Item -ItemType Directory -Force D:\Projects | Out-Null
Expand-Archive -Path "$HOME\Downloads\SENTINEL_v1_3_project.zip" -DestinationPath D:\Projects
Set-Location D:\Projects\SENTINEL
Get-ChildItem
```

Arsip sudah berisi folder `SENTINEL`, sehingga hasil akhirnya harus `D:\Projects\SENTINEL`, bukan `D:\Projects\SENTINEL\SENTINEL`. Struktur utamanya kurang lebih seperti berikut:

```text
D:\Projects\SENTINEL\
├── main.py   config.py   pytest.ini   pyproject.toml
├── requirements.txt   requirements-biometric.txt   requirements-dev.txt
├── README.md   .env.example   .gitignore
├── assets\fonts\
├── sentinel\   (ui\, services\, security\, database\, devices\, ...)
├── tests\      (unit\, integration\, gui\)
├── scripts\    (smoke_sentinel.py, run_app.ps1, install_deps.ps1, ...)
└── docs\       (architecture.md, database.md, demo_guide.md, test_report.md, ...)
```

### 7.3. Pastikan Python 3.13 tersedia

```powershell
py -3.13 --version
py -3.13 -c "import sys, tkinter; print(sys.version); print(sys.maxsize > 2**32, tkinter.TkVersion)"
```

Pastikan hasil menunjukkan Python `3.13.x`, `True` untuk pemeriksaan 64-bit, dan versi Tcl/Tk `8.6`. Jika `py -3.13` tidak dikenali, instal Python 3.13 64-bit dan pastikan Python Launcher serta PATH sudah tersedia.

### 7.4. Buat dan aktifkan virtual environment

Buat `.venv` di dalam folder project. Jangan menyalin `.venv` dari komputer lain.

```powershell
py -3.13 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
```

Output perintah terakhir harus menunjuk ke `...\SENTINEL\.venv\Scripts\python.exe`. Jika belum, virtual environment belum aktif. Setelah aktif, gunakan `python -m pip` agar paket dipasang ke `.venv`, bukan ke Python global.

### 7.5. (Opsional) Pindahkan cache dan folder sementara

Lewati bagian ini jika tidak perlu mengatur lokasi cache. Contoh berikut menggunakan `D:\DevCache`; ganti lokasinya jika diperlukan.

```powershell
New-Item -ItemType Directory -Force D:\DevCache\pip, D:\DevCache\temp, D:\DevCache\deepface | Out-Null
$env:PIP_CACHE_DIR = "D:\DevCache\pip"
$env:TEMP = "D:\DevCache\temp"
$env:TMP = $env:TEMP
```

Pengaturan environment variable tersebut hanya berlaku pada jendela PowerShell yang sedang terbuka. Jika jendela ditutup, atur kembali sebelum menjalankan perintah terkait.

### 7.6. Install dependency core dan development

Dengan `.venv` sudah aktif, jalankan:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-biometric.txt
python -m pip check
```

`requirements-dev.txt` mencakup dependency core dari `requirements.txt` serta tool development seperti `pytest` dan `ruff`. Dependency inti meliputi CustomTkinter, Pillow, cryptography, argon2-cffi, keyring, platformdirs, dan `sqlcipher3==0.6.5`.

Alternatifnya, project menyediakan script instalasi:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_deps.ps1
```

Script tersebut mengatur cache/temp ke folder `DevCache` dan memasang dependency core serta development ke `.venv`. Perhatikan bahwa script ini memilih drive `D:` bila tersedia, atau drive sistem jika tidak. Jangan memasang `pysqlcipher3` bersamaan dan jangan mengganti SQLCipher dengan SQLite biasa.

`pip check` seharusnya menampilkan `No broken requirements found`.

### 7.7. Jalankan smoke test core

```powershell
python scripts\smoke_sentinel.py core
```

Semua pemeriksaan harus berstatus `[PASS]`, termasuk python, gui, sqlcipher, crypto, vigenere, lsb, argon2, dan keyring. Saat pemeriksaan `gui`, jendela kosong dapat muncul sebentar lalu tertutup; itu normal.

- Jika `keyring` gagal, pastikan aplikasi dijalankan sebagai user Windows biasa dan Windows Credential Manager dapat diakses.
- Pesan `ERROR ... sqlcipher_codec_ctx_set_error` yang mungkin muncul di terminal saat tes SQLCipher bukan dengan sendirinya tanda kegagalan.
- Jangan lanjut jika ada pemeriksaan `[FAIL]`; simpan output lengkapnya untuk ditelusuri.

### 7.8. Jalankan test otomatis

```powershell
python -m pytest
```

Test mencakup unit, integrasi, dan GUI. Test GUI dapat dilewati otomatis jika tidak tersedia display. Test integrasi dapat memerlukan waktu lebih lama karena operasi hash Argon2. Pengujian yang tercatat pada README adalah 75 test lulus di sandbox Linux/Python 3.12; hasil pada Windows perlu diverifikasi di komputer Windows yang digunakan.

### 7.9. Tentukan lokasi data dan jalankan aplikasi

Data aplikasi—database terenkripsi, bukti, model, dan log—disimpan terpisah dari folder project. Jika `SENTINEL_DATA_DIR` tidak diatur, lokasi default adalah `%LOCALAPPDATA%\SENTINEL`.

Untuk memilih lokasi sendiri dan menjalankan aplikasi secara manual:

```powershell
$env:SENTINEL_DATA_DIR = "D:\SENTINEL_DATA"
python main.py
```

Atau jalankan melalui script:

```powershell
.\scripts\run_app.ps1
```

`run_app.ps1` mengatur lokasi data dan cache/model secara default. Script ini menggunakan `D:` bila tersedia, atau drive sistem jika tidak. Jika menjalankan aplikasi secara manual dengan Face Verification, pastikan `DEEPFACE_HOME` menggunakan lokasi yang sama dengan yang dipakai saat memasang model.

### 7.10. Selesaikan setup pertama kali

Saat aplikasi pertama kali dibuka:

1. Buat akun Admin dan database terenkripsi melalui layar setup.
2. **Simpan kode pemulihan** yang ditampilkan. Konfirmasikan bahwa kode sudah disimpan, lalu pilih **Selesai**. Kode ini diperlukan untuk alur pemulihan password.
3. Colok flash drive, buka pengaturan faktor autentikasi, cari/pilih USB, lalu daftarkan atau buat USB dongle sesuai kontrol yang tersedia.
4. Login menggunakan username dan password Admin. Faktor USB atau wajah diperiksa sesuai kebijakan akun; jika belum mengaktifkan verifikasi wajah, pastikan faktor tersebut tidak diwajibkan.

Jika flash drive tidak muncul, Windows mungkin mengidentifikasinya sebagai *fixed disk*. Tutup aplikasi, lalu jalankan dari PowerShell:

```powershell
$env:SENTINEL_USB_INCLUDE_FIXED = "1"
python main.py
```

### 7.11. Data dummy untuk demo (opsional)

Setelah setup pertama selesai, buka terminal PowerShell kedua, aktifkan `.venv`, dan atur `SENTINEL_DATA_DIR` ke lokasi data yang sama. Kemudian jalankan:

```powershell
Set-Location D:\Projects\SENTINEL
.\.venv\Scripts\Activate.ps1
$env:SENTINEL_DATA_DIR = "D:\SENTINEL_DATA"
python scripts\seed_demo.py
```

Skrip meminta kredensial Admin lalu membuat data demo. Ikuti `docs\demo_guide.md` untuk alur demonstrasi. Gunakan **data dummy saja**.

### 7.12. (Opsional) Aktifkan Face Verification dengan webcam

Face Verification memerlukan dependency dan bobot model tambahan. Bagian ini boleh dilewati jika demo hanya menggunakan password dan USB.

Atur lokasi model terlebih dahulu. Contoh:

```powershell
$env:DEEPFACE_HOME = "D:\DevCache\deepface"
```

Lalu pasang dependency biometrik dan unduh bobot ArcFace:

```powershell
python -m pip install --dry-run --report "$env:TEMP\bio.json" -r requirements-biometric.txt
Select-String -Path "$env:TEMP\bio.json" -Pattern '"name": "(tensorflow|torch|keras|onnxruntime-gpu)"'
python -m pip install -r requirements-biometric.txt
python scripts\prefetch_models.py
python scripts\smoke_sentinel.py camera
python scripts\smoke_sentinel.py deepface
```

Periksa hasil *dry run* sebelum instalasi; pola `Select-String` di atas digunakan untuk memeriksa apakah paket yang disebut ikut ditarik sebagai dependency. Jika hasilnya tidak sesuai dengan yang diharapkan, jangan lanjutkan instalasi sebelum memeriksa dependency yang akan dipasang.

Gunakan nilai `DEEPFACE_HOME` yang sama setiap kali menjalankan aplikasi. Setelah login, buka **Settings → Faktor Autentikasi** dan daftarkan/perbarui wajah melalui webcam. Setelah wajah didaftarkan, verifikasi wajah dapat diwajibkan untuk akun tersebut. Kamera hanya aktif ketika diperlukan oleh kebijakan akun; frame diproses di memori dan tidak disimpan sebagai foto.

### 7.13. Mengulang setup dari awal (reset)

1. Tutup aplikasi.
2. Hapus folder data yang digunakan, misalnya:
   ```powershell
   Remove-Item -Recurse -Force $env:SENTINEL_DATA_DIR
   ```
   Jika `SENTINEL_DATA_DIR` tidak pernah diatur, periksa `%LOCALAPPDATA%\SENTINEL`.
3. Hapus entri layanan `SENTINEL-…` yang terkait di **Control Panel → Credential Manager → Windows Credentials** hanya jika memang ingin menghapus instalasi dan data demo sepenuhnya.
4. Jalankan `main.py` lagi untuk memulai setup baru.

**Peringatan:** menghapus entri key di Credential Manager dapat membuat data terenkripsi lama tidak dapat dibuka. Jangan hapus entri tersebut jika masih ingin mengakses database atau bukti dari instalasi sebelumnya.

### Catatan penting setelah instalasi

- Password selalu digunakan untuk login. USB dongle dan Face Verification diwajibkan sesuai pengaturan per akun.
- Gunakan **data dummy saja**; SENTINEL merupakan prototipe akademik.
- Key kriptografi disimpan di Windows Credential Manager, bukan di file konfigurasi.
- Untuk lokasi database, bukti, hasil ekspor, model, dan log, lihat bagian konfigurasi dan lokasi data di bawah.
- Batasan keamanan sistem dijelaskan pada bagian **Batasan sistem dan keamanan**.

## 8. Konfigurasi
Environment variable (lihat `.env.example`): `SENTINEL_DATA_DIR`, `DEEPFACE_HOME`, `SENTINEL_MAX_FILE_MB` (100), `SENTINEL_CAMERA_INDEX` (0),
`SENTINEL_THEME` (dark), `SENTINEL_USB_INCLUDE_FIXED` (isi `1` bila Windows menganggap flash drive Anda "fixed disk").
- **Kode Python** (`config.py`): bila `SENTINEL_DATA_DIR` kosong → `%LOCALAPPDATA%\SENTINEL`; bila `DEEPFACE_HOME` kosong → `<data>\models`.
- **`scripts\run_app.ps1`** memberi default `<drive>\SENTINEL_DATA` dan `<drive>\DevCache\deepface`, dengan `<drive>` = `D:` bila ada, selain itu drive sistem.
- **`scripts\install_deps.ps1`** memakai `<drive>\DevCache` untuk cache pip dan temp (agar C: tidak penuh).
Keamanan: key kriptografi **tidak pernah** ada di konfigurasi/file.

## 9. Cara menjalankan
```powershell
Set-Location D:\Projects\SENTINEL
.\scripts\run_app.ps1
```
Atau manual: `$env:SENTINEL_DATA_DIR="D:\SENTINEL_DATA"; $env:DEEPFACE_HOME="D:\DevCache\deepface"; .\.venv\Scripts\python.exe main.py`.

## 10. Cara menggunakan
1. **Setup awal**: buat Admin → **simpan kode pemulihan** (centang konfirmasi, lalu *Selesai*) → pasang flash drive → *Daftarkan USB*.
2. **Login**: username + password. USB dongle diperiksa bila akun mewajibkannya; wajah diperiksa bila akun mewajibkannya (kamera menyala pada saat itu).
3. **Settings → Faktor Autentikasi**: *Daftarkan / Perbarui Wajah (Webcam)* (preview live → *Ambil & Daftarkan*), *Cari USB*, *Buat USB Dongle* (Admin),
   centang *Wajibkan verifikasi wajah* / *Wajibkan USB dongle* → *Terapkan*. Menonaktifkan faktor yang aktif meminta password.
4. **Settings → Akun Pemulihan**: *Ganti Password*; *Buat Ulang Kode Pemulihan* (konfirmasi + password; kode lama langsung mati; kode baru harus dikonfirmasi tersimpan).
5. **Lupa Password** (layar login): username + kode pemulihan + password baru. Kode sekali pakai; setelah berhasil ditampilkan kode baru.
6. Alur kerja: Admin membuat akun & kasus/menugaskan Analyst → Investigator upload bukti → Analyst dekripsi/ekspor → Auditor memeriksa audit & ledger.

### Perilaku kamera di layar login (penting, dan menyimpang sedikit dari "kamera aktif saat halaman dibuka")
Kewajiban wajah ditentukan **per akun**, jadi aplikasi tidak tahu apakah akun tertentu mewajibkannya sebelum pengguna mengidentifikasi diri.
Menyalakan kamera untuk semua orang saat halaman dibuka akan melanggar aturan "jangan aktifkan kamera diam-diam"; menebak dari username akan
membocorkan akun mana yang mewajibkan wajah. Karena itu: panel kamera berstatus `CAMERA OFF` sampai **password (dan USB, bila diwajibkan) lolos**;
baru bila akun itu mewajibkan wajah, kamera menyala, preview tampil, dan dilepas segera setelah pemeriksaan. Frame hanya di memori, tidak disimpan.

### Pemantauan USB selama sesi
Berlaku bila akun yang sedang login mewajibkan USB (kebijakan dibaca ulang tiap pemeriksaan, jadi perubahan di Settings langsung berlaku).
Pemeriksaan tiap 2 detik (satu query drive ringan, di thread latar). Hanya flash drive yang **volume ID dan token marker-nya cocok** dengan USB terdaftar
yang dianggap valid. Overlay mengunci navigasi, hitung mundur 10 detik, lalu aplikasi ditutup (`SESSION_CLOSED_USB_REMOVED` dicatat di audit).
Bila gagal membaca drive (error sesaat), status `UNKNOWN` — aplikasi **tidak** ditutup.

## 11. Lokasi database
`<SENTINEL_DATA_DIR>\sentinel.db` — SQLCipher (terenkripsi); tidak dapat dibuka dengan SQLite biasa/DB Browser tanpa key.

## 12. Lokasi file terenkripsi
`<SENTINEL_DATA_DIR>\evidence\<NOMOR-KASUS>\<KODE-BUKTI>.sntenc`, mis. `D:\SENTINEL_DATA\evidence\CASE-001\EV-CASE-001-001.sntenc`.
Format: `SNTENC | versi | nonce(12) | ciphertext+tag`, ChaCha20-Poly1305. File asli hanya **dibaca** saat upload (tidak diubah/dipindah).
Folder `stego\` dibuat otomatis tetapi **saat ini tidak dipakai kode**: hasil steganografi disimpan ke lokasi yang Anda pilih lewat dialog Save.

## 13. Lokasi hasil dekripsi
Tidak ada folder tetap. *Ekspor Plaintext…* (role Analyst pada kasus yang ditugaskan) membuka dialog **Save** dan menulis plaintext ke lokasi pilihan Anda
setelah hash SHA-256 diverifikasi. Hapus hasil ekspor setelah demo.

## 14. Lokasi encryption key
Empat key acak 256-bit (`db_key`, `message_key`, `file_key`, `biometric_key`) disimpan **hanya** di Windows Credential Manager
(Control Panel → Credential Manager → Windows Credentials), di bawah layanan `SENTINEL-<10 hex>` (hash dari path folder data, sehingga dua instalasi tidak bertabrakan).
Tidak ada key di file/konfigurasi/log. Kehilangan entri ini = data terenkripsi tidak dapat dibuka (aplikasi menolak menimpa data dan menjelaskan alasannya).
Bobot model wajah: `<DEEPFACE_HOME>\.deepface\weights\` (dengan `run_app.ps1`: `D:\DevCache\deepface\.deepface\weights`; tanpa `DEEPFACE_HOME`: `<data>\models\.deepface\weights`).
Log aplikasi: `<SENTINEL_DATA_DIR>\logs\sentinel.log` (tanpa password/key/plaintext).

```
D:\SENTINEL_DATA\
├── sentinel.db
├── evidence\CASE-001\EV-CASE-001-001.sntenc
├── stego\            (dibuat, belum dipakai)
├── logs\sentinel.log
└── models\           (hanya bila DEEPFACE_HOME tidak diset; dengan run_app.ps1 model ada di D:\DevCache\deepface)
```

## 15. Panduan demonstrasi dosen
Lihat **`docs\demo_guide.md`** (18 langkah beserta path yang bisa langsung dibuka di Explorer dan poin penjelasan).

## 16. Troubleshooting
| Gejala | Tindakan |
|---|---|
| `Activate.ps1`/script ditolak | `Set-ExecutionPolicy -Scope Process Bypass` |
| `py -3.13` tidak dikenali | Install Python 3.13 64-bit, centang *Add to PATH* dan *tcl/tk* |
| `sqlcipher3` gagal | Pastikan 3.13 64-bit; coba `sqlcipher3==0.6.4` di `requirements.txt` |
| "Keyring OS tidak tersedia" | Jalankan sebagai user biasa; cek `smoke_sentinel.py keyring` |
| USB tidak terdeteksi | `$env:SENTINEL_USB_INCLUDE_FIXED="1"` lalu jalankan ulang |
| Kamera tidak terbuka / `CAMERA UNAVAILABLE` | Windows Settings → Privacy → Camera; `SENTINEL_CAMERA_INDEX=1`; tutup aplikasi lain yang memakai kamera |
| Layar login: kamera tetap `CAMERA OFF` | Normal bila akun tidak mewajibkan wajah; atur di Settings |
| Login ditolak "USB belum terdaftar" | Admin: Settings → *Buat USB Dongle*, atau matikan kewajiban USB akun (butuh password) |
| Font tampak berbeda | IBM Plex Sans gagal dimuat → fallback Segoe UI (fungsi tetap normal) |
| Aplikasi menutup sendiri saat sesi | USB dongle yang diwajibkan dicabut >10 detik; lihat audit `SESSION_CLOSED_USB_REMOVED` |
| Lupa Password: "kode salah" berulang | Percobaan salah ikut lockout 30 dtk setelah 5 kali; kode sekali pakai & hanya kode terbaru yang berlaku |
| Mulai dari nol | Tutup app, hapus folder data, hapus entri `SENTINEL-…` di Credential Manager, jalankan lagi |

## 17. Pengujian
`.\.venv\Scripts\python.exe -m pytest` (GUI dilewati otomatis bila tidak ada display). **75 test lulus** di sandbox Linux/Python 3.12 (GUI via Xvfb), coverage 82%.
Rincian per area, termasuk yang **belum diuji / butuh uji manual di Windows**: `docs\test_report.md`.

## 18. Batasan sistem dan keamanan
- USB flash drive biasa = faktor kepemilikan sederhana; **dapat dikloning** (token tersimpan di file marker). Bukan hardware token.
- Face verification = pencocokan 1:1; **tanpa liveness/anti-spoofing** (foto/layar bisa lolos).
- USB dongle adalah **satu USB global**; hanya Admin yang dapat membuat/mengganti. Akun lain hanya memilih mewajibkannya atau tidak.
- Mematikan semua faktor tambahan membuat login hanya memakai password (butuh konfirmasi + password saat ini; tercatat di audit).
- Kode pemulihan dibuat otomatis saat akun dibuat; Admin yang membuat akun melihatnya sekali (pemilik dapat membuat ulang sendiri). Akun hasil migrasi v1.2 tidak punya kode sampai membuatnya.
  Checkbox "sudah disimpan" adalah pernyataan pengguna, bukan bukti teknis. Reset password **tidak** melewati USB/wajah.
- Pemantauan USB hanya berlaku saat aplikasi berjalan; ini bukan proteksi terhadap proses lain di komputer yang sama.
- Vigenère = demonstrasi cipher klasik; perlindungan nyata dari AES-256-GCM / ChaCha20-Poly1305.
- SQLCipher + keyring melindungi data di disk, **bukan** dari proses lain pada akun Windows yang sama.
- LSB menyamarkan keberadaan data, bukan enkripsi dan bukan anti-deteksi.
- Hash chain mendeteksi perubahan/penghapusan di tengah rantai; **pemotongan di ujung rantai tidak terdeteksi**.
- Dashboard memverifikasi seluruh hash chain tiap dibuka (O(n)); untuk ribuan blok dapat terasa lambat.
- Pesan hanya antar akun dalam satu instalasi (bukan E2E lintas perangkat).
