# Panduan demo (data dummy)

Persiapan: `.\scripts\run_app.ps1`; siapkan satu flash drive kosong untuk demo. Opsional: `python scripts\seed_demo.py` membuat akun
`investigator1`, `analyst1`, `auditor1` (password `Demo-Pass-123`), `CASE-001`, satu bukti, dan satu pesan.

1. **First-run**: buat Admin → pasang flash drive → "Daftarkan USB". Jelaskan: key acak di Credential Manager, database SQLCipher.
2. **Login Admin**: password + USB; daftarkan wajah di *Settings*, centang "Wajibkan verifikasi wajah saat login" lalu *Terapkan*; menonaktifkannya butuh password dan dicatat di audit.
3. **User Management**: Admin membuat Investigator, Forensic Analyst, Auditor. Logout.
4. **Investigator**: login (password + USB; wajah tidak wajib secara default). *Cases* → buat `CASE-001`. (Admin menugaskan Analyst: login Admin → *Cases* → pilih kasus → Tugaskan; SRS 4.2.)
5. **Upload bukti**: *Evidence* → pilih kasus → Upload file dummy → tampilkan SHA-256 sumber; tunjukkan file `.sntenc` di `<DATA_DIR>\evidence\CASE-001\` tidak berisi teks asli.
6. **Pesan**: *Secure Messages* → kirim ke Analyst (Vigenère + AES-256-GCM). Tunjukkan `messages.ciphertext` hanya blob (jelaskan di slide, DB terenkripsi).
7. **Steganografi**: pilih PNG, tulis pesan, simpan sebagai PNG baru; lalu ekstrak.
8. **Analyst**: login → kasus ditugaskan → baca pesan → *Dekripsi & Verifikasi Hash* (VALID) → *Ekspor Plaintext*.
9. **Auditor**: login → menu hanya Cases/Evidence (metadata)/Ledger/Activity Logs; *Verifikasi Hash Ciphertext*; *Integrity Ledger → Verifikasi* (VALID). Tidak ada tombol dekripsi, tidak ada menu Pesan/Stego.
10. **Uji perubahan data**: `python scripts\tamper_demo.py` mengubah SALINAN ledger/ciphertext dan menunjukkan deteksinya (data asli tidak berubah).
11. **Batasan** (README): USB dapat dikloning, tanpa liveness, hash chain tanpa anchor (tail truncation), keyring = akun Windows.

Checklist kriteria SRS 15.4: lihat tabel di README; item 1–9 dapat dilakukan lewat langkah di atas. Item yang memerlukan perangkat (USB, webcam) perlu diperagakan di laptop.
