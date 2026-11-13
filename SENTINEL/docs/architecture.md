# Arsitektur SENTINEL v1.2

```
UI (CustomTkinter)  ->  Services  ->  Repositories  ->  SQLCipher
 ui/*_view.py           services/*     database/*          (satu koneksi per thread)
        |                   |
        |                   +-> security/* (Argon2id, AES-GCM, ChaCha20-Poly1305, Vigenere, LSB, hashing)
        |                   +-> devices/*  (USB Windows, webcam, DeepFace)  <- diganti fake pada test
        +-> AsyncRunner: pekerjaan lambat di ThreadPoolExecutor(2); callback kembali ke thread Tk lewat queue + after()
```

- **Tidak ada SQL maupun logika bisnis di callback GUI.** View hanya memanggil service dan menampilkan hasil/exception.
- **bootstrap.py** merangkai semua service (`AppContext`) dan menjalankan first-run. `open_existing()` tidak pernah membuat/menimpa database.
- **PermissionService.authorize()** membaca ulang akun (status ACTIVE, role) pada tiap aksi; hak berbasis relasi kasus (`created_by`, `assigned_analyst_id`) diperiksa di service.
- **AuditService.record()** menulis `audit_logs` dan menambahkan blok ledger **dalam satu transaksi** (`BEGIN IMMEDIATE`); satu sumber event.
- **Transaksi**: `Database.transaction()` bersarang-aman; operasi multi-tabel (upload bukti, kirim pesan, registrasi USB) atomik. File ciphertext ditulis atomik (`tmp` + `os.replace`) dan dihapus bila insert DB gagal.
- **Thread**: `Database.conn()` mengembalikan koneksi per-thread; worker pool dibatasi 2 sehingga jumlah koneksi terbatas.

## Kriptografi (keputusan SRS 19)

| Data | Algoritma | Key | Binding (AAD) |
|---|---|---|---|
| Database | SQLCipher (raw key `x'..'`) | `db_key` (keyring) | — |
| Password | Argon2id (argon2-cffi default) | — | — |
| Pesan | Vigenère (kunci demo publik) → AES-256-GCM, nonce 12 B acak | `message_key` | `SNT|v1|message|<message_id>` |
| Payload stego | pipeline yang sama | `message_key` | `SNT|v1|stego|<artifact_id>` |
| Bukti | ChaCha20-Poly1305 one-shot ≤100 MB; `SNTENC|v1|nonce|ct+tag` | `file_key` | `SNT-EVD|v1|<evidence_id>` |
| Template wajah | AES-256-GCM atas float32 LE | `biometric_key` | `SNT-BIO|v1|<user_id>` |
| Ledger | SHA-256 atas canonical JSON | — | `previous_hash` rantai |

Tidak ada per-object DEK, wrapped key, rotasi key, chunked encryption, HKDF, atau anchor eksternal (sengaja, SRS 19).

## Login (SRS 6.1)

username+password (Argon2id, hash dummy untuk user tak dikenal) → lockout 5 gagal/30 dtk → akun ACTIVE → USB bila `users.require_usb` (marker + token hash + serial volume, `hmac.compare_digest`) → Face Verification bila `users.require_face` (1:1 ArcFace, jarak kosinus ≤ threshold dari DeepFace) → audit. Pengaturan ini diubah lewat `AccountSecurityService` (halaman Settings); melemahkan login butuh password saat ini.

Lupa Password: `AuthService.reset_password_with_recovery_code` (kode sekali pakai, di-hash Argon2id, ikut lockout, kode dirotasi setelah dipakai).
Pesan gagal pada tahap password dibuat generik; password/username salah tidak dicatat mentah.

## Biometrik

`DeepFace.represent(frame, ArcFace, opencv, enforce_detection=True)`; tepat satu wajah wajib. Enrollment: 3 frame → rata-rata embedding ter-normalisasi → dienkripsi. Threshold dibaca dari DeepFace terpasang
(`deepface.modules.verification.find_threshold`, 0.68 pada 0.0.102) dan sumbernya dicatat di `app_settings.face_threshold_source`. Foto tidak pernah disimpan.

## Deviasi dari SRS dan alasannya

- Struktur folder: `utils/paths.py` dan `utils/validators.py` tidak dibuat (path ada di `config.Settings`, validasi di service); ditambah `setup_view.py`, `async_utils.py`, `common.py`, `dashboard_service.py`.
- Skenario demo SRS 17 langkah 6 menyebut Investigator menugaskan Analyst; matriks 4.2 dan CASE-04 hanya mengizinkan Admin. Implementasi mengikuti matriks (Admin menugaskan).
- Matriks "Baca pesan: hanya pesan untuknya" vs SRS 5.5 "pengirim/penerima": pengirim boleh membaca ulang pesan terkirimnya sendiri; pihak lain (termasuk Admin) tidak.
- `psutil` dihapus dari dependency (deteksi USB memakai ctypes `kernel32`).
- Deteksi flash drive: `GetDriveTypeW == DRIVE_REMOVABLE` (opsional fixed non-C: via env).
- Pemulihan USB: bila tidak ada USB aktif (setup terhenti / dicabut), layar login menawarkan registrasi dengan kredensial Admin; bila ada USB aktif jalur ini tertutup.
- Hanya Admin aktif terakhir yang dilindungi dari penonaktifan/penurunan role.
- DeepFace 0.0.102 menarik `opencv-contrib-python-headless` (bukan `opencv-python`); cukup untuk VideoCapture, GUI tetap CustomTkinter.


## Tambahan redesign v1.3
- **Login berstahap**: `BiometricService.verify(user_id, on_stage, on_stream)` membuka stream kamera hanya selama pemeriksaan, melaporkan tahap
  (`CAMERA_INITIALIZING → CAMERA_ACTIVE → SCANNING → VERIFYING → VERIFIED/FAILED/CAMERA_UNAVAILABLE`) dan selalu menutup stream. UI menerima tahap lewat queue thread-safe.
- **SessionGuard** (`services/session_guard.py`): memutuskan status USB selama sesi (`OK/NOT_REQUIRED/DISCONNECTED/UNKNOWN`) dari kebijakan akun; UI (`MainShell`) yang menampilkan overlay,
  hitung mundur, dan menutup aplikasi. Event audit: `SESSION_USB_DISCONNECTED`, `SESSION_USB_RECONNECTED`, `SESSION_CLOSED_USB_REMOVED`.
- **Design system** di `ui/common.py`: token warna/spasi/radius, `init_fonts()` (IBM Plex Sans dibundel + Cascadia Code), komponen `StatusDot`, `StatusPill`, `Panel`, `DataTable`.
