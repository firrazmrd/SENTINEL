# Laporan Pengujian SENTINEL v1.3 (redesign)

Lingkungan pengujian otomatis: **sandbox Linux, Python 3.12.3, GUI lewat Xvfb**, SQLCipher/Argon2id/ChaCha20/AES-GCM nyata, keyring memori,
USB/kamera/wajah **palsu** (test double). Hasil: **75 test lulus, 0 gagal**; `ruff` bersih; coverage 82%.
Tangkapan layar dirender di Xvfb (Linux) dan diperiksa secara visual; kamera disimulasikan dengan frame sintetis yang diproses oleh jalur render OpenCV/Pillow asli.

Legenda: **Passed** = diuji otomatis/diperiksa di sandbox · **Failed** = gagal · **Not Tested** = belum diuji sama sekali · **Requires Manual Testing** = hanya bisa diuji di Windows/perangkat fisik.

| Area | Status | Bukti / catatan |
|---|---|---|
| Login (password, lockout, pesan generik) | Passed | `test_database_and_auth`, GUI flow |
| Register / setup Admin pertama | Passed | GUI flow (wizard + kode pemulihan) |
| Face Recognition (enroll, verify, beda orang ditolak) | Passed (dengan engine palsu) | `test_biometric`, `test_session_and_stages` |
| Face Recognition dengan **wajah & webcam nyata**, DeepFace/ArcFace | **Requires Manual Testing** | Dibuktikan v1.2 di sandbox dengan gambar publik; webcam belum |
| Live Camera Preview (login & enrollment) | Passed (render) / **Requires Manual Testing** (webcam) | Frame sintetis → panel kamera; urutan status & pelepasan stream diuji (`test_gui_login_camera_preview_and_stages`) |
| Kamera tidak menyala bila wajah tak diwajibkan / password salah | Passed | `test_camera_never_opened_when_face_not_required_or_password_wrong`, GUI flow (`opened == 0`) |
| Penanganan kamera gagal (`CAMERA UNAVAILABLE`) | Passed | `test_camera_unavailable_reported` |
| Registrasi USB Dongle | Passed (dengan USB palsu) | `test_database_and_auth`, GUI flow |
| Deteksi flash drive Windows (`usb_windows.py`) & USB fisik | **Requires Manual Testing** | Butuh flash drive & Windows |
| USB Disconnect Detection (kunci, hitung mundur, reconnect, tutup app) | Passed (logika + GUI dengan USB palsu) / **Requires Manual Testing** (cabut fisik) | `test_session_guard_*`, `test_gui_usb_removed_locks_...` |
| Flash drive asing tidak dianggap dongle | Passed | `test_a_foreign_flash_drive_is_not_the_dongle` |
| Beban CPU pemantauan USB (2 detik) | **Not Tested** | Hanya argumen desain (1 query ringan di thread latar); belum diukur di Windows |
| Authentication Settings (wajib wajah/USB, persisten, berlaku di login, re-auth saat melemahkan) | Passed | `test_account_security` |
| Recovery Code (generate, hash, sekali pakai, rotasi, lockout, tak bocor ke audit) | Passed | `test_account_security` |
| Recovery Code Copy Confirmation (checkbox → tombol Selesai) | Passed (logika/render) / **Requires Manual Testing** (klik penuh) | `RecoveryCodeDialog` dipakai di GUI flow; gating tombol diperiksa visual; tidak ada test klik khusus untuk checkbox |
| Forgot Password (end-to-end layar login) | Passed di level service; dialog **Not Tested** otomatis | `test_recovery_code_lifecycle`; dialog `FormDialog` terbuka di screenshot |
| Password Change | Passed | `test_change_password` |
| Evidence Upload / Encryption / Decryption / Integrity | Passed (service) | `test_cases_evidence`; **upload/ekspor lewat GUI tidak diotomasi** (dialog file) → Requires Manual Testing |
| Audit Log & Integrity Ledger | Passed | `test_messages_stego_ledger`, GUI flow |
| Database (SQLCipher, migrasi v1.2 → v1.3) | Passed | `test_database_and_auth`, `test_migration_upgrades_v12_database` |
| Dashboard (status, ringkasan, integritas, event) | Passed | `test_dashboard_overview_and_status_rules`, GUI flow, screenshot |
| Settings (UI + aksi) | Passed | GUI flow, screenshot |
| Halaman lain (Cases, Evidence, Messages, Stego, Users, Audit, Ledger) | Passed (navigasi tanpa error, tabel) | GUI flow memuat semuanya; tampilan lain hanya mengikuti token baru, diperiksa visual: Cases, Evidence |
| Fitur lama tidak rusak | Passed | 65 test sebelum redesign tetap lulus setelah redesign (total kini 75) |
| Font IBM Plex Sans / Cascadia Code di Windows 11 | **Requires Manual Testing** | Plex dimuat di Linux (terlihat di screenshot); jalur Windows (`AddFontResourceEx`) belum dijalankan |
| Windows Credential Manager (keyring) | **Requires Manual Testing** | Sandbox memakai backend memori |
| Python 3.13 + wheel Windows | **Requires Manual Testing** | Diuji di 3.12 |
| Layar DPI tinggi / skala 125–150% | **Not Tested** | Jendela minimum 1020×660 |
| Aksesibilitas | Sebagian | Token kontras dipilih; **tidak** diaudit dengan alat. Teks putih di tombol biru #3182E8 ±3.9:1 (memenuhi untuk teks tebal besar, kurang dari 4.5:1 untuk teks normal). Navigasi keyboard: Enter di form login; sisanya default Tk |

## Temuan yang diperbaiki selama pengujian
- Frame "daun" CustomTkinter meminta tinggi 200 px → sidebar & panel membengkak (ketahuan dari screenshot, diperbaiki).
- Teks "PASSWORD + USB + WAJAH" terpotong di dashboard (diperbaiki dengan wrap).
- Pemanggilan widget Tk dari thread worker pada dialog wajah (diperbaiki: tahap dipecah, UI hanya disentuh di thread Tk).

## Yang belum dilakukan
Uji di Windows 11 nyata (webcam, flash drive, Credential Manager, font), pengukuran CPU, audit aksesibilitas, uji beban ledger besar.
