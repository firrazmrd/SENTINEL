# Panduan Demonstrasi SENTINEL v1.3 (untuk dosen)

Gunakan **data dummy**. Semua path di bawah memakai default `scripts\run_app.ps1` (`D:\SENTINEL_DATA`; bila tidak ada drive D, ganti `D:` dengan drive sistem).
Alat bantu: Windows Explorer, flash drive kosong, webcam. Siapkan juga satu file dummy (mis. `log_dummy.txt`).

| # | Langkah | Yang dilakukan | Poin penjelasan |
|---|---|---|---|
| 1 | Ekstrak project | `Expand-Archive "$HOME\Downloads\SENTINEL_v1_3_project.zip" D:\Projects` | Struktur folder: `sentinel\`, `assets\fonts`, `scripts`, `docs` |
| 2 | Install dependensi | `py -3.13 -m venv .venv` → `.\scripts\install_deps.ps1 -Biometric` → `.\.venv\Scripts\python.exe scripts\prefetch_models.py` | Semua ke `.venv`; cache ke `D:\DevCache`; model ArcFace diunduh sekali |
| 3 | Jalankan aplikasi | `.\scripts\run_app.ps1` | Konsol menampilkan lokasi data & model |
| 4 | Buat akun Admin | Isi username/nama/password → *Buat Admin & Database Terenkripsi* | 4 key acak masuk Credential Manager; layar berikutnya **kode pemulihan** (centang konfirmasi → *Selesai*) |
| 5 | Daftarkan wajah | Login dulu (langkah 6), lalu *Settings → Daftarkan / Perbarui Wajah (Webcam)* → preview live → *Ambil & Daftarkan* | Hanya embedding terenkripsi (AES-GCM) yang disimpan, bukan foto; tanpa liveness |
| 6 | Daftarkan USB | Wizard: colok flash drive → *Segarkan* → *Daftarkan USB*. (Ganti kemudian: *Settings → Cari USB → Buat USB Dongle*) | Marker `.sentinel-token` + hash token + volume ID; dapat dikloning |
| 7 | Login sesuai konfigurasi | *Settings*: centang *Wajibkan verifikasi wajah* + *Wajibkan USB dongle* → *Terapkan* → Logout → Login | Kamera menyala **setelah** password lolos; status `CAMERA INITIALIZING → ACTIVE → SCANNING → VERIFYING → VERIFIED`. Cabut USB saat sesi → overlay + hitung mundur → aplikasi menutup |
| 8 | Buat akun pengguna | *User Management* → buat `investigator1` (Investigator), `analyst1` (Forensic Analyst), `auditor1` | Dialog kode pemulihan tampil sekali untuk Admin; pemilik bisa membuat ulang sendiri |
| 9 | Buat Case | Admin membuat kasus & menugaskan Analyst; atau login `investigator1` → *Cases* | Role & izin ditegakkan di service |
| 10 | Upload bukti | Login `investigator1` → *Evidence* → *Upload Bukti…* → pilih `log_dummy.txt` | SHA-256 dihitung dulu, lalu dienkripsi ChaCha20-Poly1305 |
| 11 | Lokasi `.sntenc` | Explorer: `D:\SENTINEL_DATA\evidence\CASE-001\EV-CASE-001-001.sntenc` (tempel path di address bar) | Isi tidak terbaca; header `SNTENC` + nonce |
| 12 | File asli vs terenkripsi | Bandingkan `log_dummy.txt` (tidak berubah) dengan `.sntenc` (ukuran = asli + 6+1+12+16 byte; tidak bisa dibuka) | File asli hanya dibaca; ciphertext-only di penyimpanan |
| 13 | Verifikasi integritas | *Evidence* → *Verifikasi Hash Ciphertext*. Opsional: ubah 1 byte salinan `.sntenc` → ulangi (→ `CIPHERTEXT_MODIFIED`) lalu kembalikan. `python scripts\tamper_demo.py` untuk versi aman | Hash ciphertext tidak butuh key; plaintext butuh key |
| 14 | Dekripsi & ekspor | Login `analyst1` (kasus ditugaskan) → *Evidence* → *Dekripsi & Verifikasi Hash*, lalu *Ekspor Plaintext…* → pilih lokasi, mis. `D:\Export\log_dummy.txt` | Poly1305 memastikan keaslian; SHA-256 plaintext dicocokkan sebelum ditulis |
| 15 | Lokasi hasil ekspor | Explorer: `D:\Export\` (folder yang Anda pilih) | Tidak ada folder tetap; hapus setelah demo |
| 16 | Database | Explorer: `D:\SENTINEL_DATA\sentinel.db` (coba buka dengan DB Browser → gagal) | SQLCipher; key dari Credential Manager |
| 17 | Key | `control.exe keymgr.dll` → Windows Credentials → entri `SENTINEL-…` (4 key) | Tidak ada key di file; kehilangan entri = data tak terbuka |
| 18 | Audit Log & Ledger | *Activity Logs* (filter event) lalu *Integrity Ledger → Verifikasi Integritas Ledger*; `python scripts\tamper_demo.py` untuk simulasi perubahan | Hash chain mendeteksi perubahan di tengah rantai; ujung rantai tidak |

Tambahan singkat bila waktu cukup: **Lupa Password** (Logout → *Lupa Password?* → username + kode + password baru → kode baru muncul),
**Dashboard** (status keamanan, integritas file, event keamanan), **cabut USB** saat sesi.

Path Explorer cepat: `D:\SENTINEL_DATA` · `D:\SENTINEL_DATA\evidence` · `D:\SENTINEL_DATA\logs\sentinel.log` · `D:\DevCache\deepface\.deepface\weights`.
