# Skema database (SQLCipher)

Sumber kebenaran: `sentinel/database/schema.sql`. Semua tabel mengikuti SRS 9.1; `PRAGMA foreign_keys=ON` per koneksi.

| Tabel | Kegunaan | Catatan |
|---|---|---|
| `users` | akun, role, status, lockout (`failed_attempts`, `locked_until`), `require_face`, `require_usb`, `recovery_code_hash`, `recovery_code_created_at` | username unik NOCASE; hash Argon2id; migrasi otomatis dari v1.2 (`Database.migrate`) |
| `usb_devices` | satu USB global `ACTIVE`; yang lama `REVOKED` | hanya hash token + serial volume |
| `biometric_templates` | embedding terenkripsi + metadata model/detector/dim/metric/threshold/versi | satu per user; tanpa foto |
| `cases` | nomor `CASE-NNN`, status OPEN/IN_REVIEW/CLOSED, `created_by`, `assigned_analyst_id` | |
| `evidence_items` | metadata bukti, `original_sha256`, `encrypted_sha256`, `status`, `analyst_note` | path relatif terhadap `evidence/` |
| `messages` | ciphertext+nonce, pengirim/penerima, `read_at` | tanpa plaintext |
| `stego_artifacts` | hash carrier & payload, pembuat | |
| `audit_logs` | satu-satunya sumber event | `details_json` tanpa secret |
| `ledger_blocks` | `block_index`, `payload_hash`, `previous_hash`, `block_hash` | tiap audit log punya satu blok |
| `app_settings` | `schema_version`, `face_threshold_source` | |

Status integritas bukti: `STORED`, `CIPHERTEXT_MODIFIED`, `PLAINTEXT_HASH_MISMATCH`, `DECRYPTION_FAILED`, `VALID`.

Ledger: `payload_hash = SHA256(canonical_json(audit row))`; `block_hash = SHA256(canonical_json({index, audit_log_id, timestamp, actor, event, target, payload_hash, previous_hash}))`;
blok 0 = `LEDGER_GENESIS` dengan `previous_hash` 64 nol. Verifikasi menghitung ulang seluruh rantai dan melaporkan indeks blok pertama yang gagal.

Membuktikan database terenkripsi: `python scripts/smoke_sentinel.py sqlcipher` (header bukan "SQLite format 3", marker tidak ada di file, `sqlite3` bawaan dan key salah gagal).
