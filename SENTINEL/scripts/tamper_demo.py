"""Demo SRS 17 langkah 12: mengubah SALINAN data uji lalu memverifikasi deteksinya. Data asli tidak diubah.
Jalankan:  python scripts/tamper_demo.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Settings  # noqa: E402
from sentinel import bootstrap  # noqa: E402
from sentinel.database.connection import Database  # noqa: E402
from sentinel.database.repositories import LedgerRepo  # noqa: E402
from sentinel.security.file_crypto import FileCrypto  # noqa: E402
from sentinel.security.hashing import sha256_hex  # noqa: E402
from sentinel.services.ledger_service import LedgerService  # noqa: E402
from sentinel.utils.exceptions import DecryptionError  # noqa: E402

settings = Settings.from_env()
settings.apply_environment()
ctx = bootstrap.open_existing(settings)
tmp = Path(tempfile.mkdtemp(prefix="sentinel_tamper_"))
try:
    print("== 1. Ledger pada SALINAN database ==")
    copy = tmp / "sentinel_copy.db"
    shutil.copy2(settings.db_path, copy)
    cdb = Database(copy, ctx.keys.get("db_key"))
    led = LedgerService(LedgerRepo(cdb), ctx.perms)
    print("sebelum diubah :", led.check_chain())
    mid = cdb.scalar("SELECT block_index FROM ledger_blocks ORDER BY block_index LIMIT 1 OFFSET 2")
    if mid is not None:
        cdb.run("UPDATE ledger_blocks SET event_type='DIUBAH' WHERE block_index=?", (mid,))
        print(f"setelah ubah block #{mid}:", led.check_chain())
    cdb.close_all()

    print("\n== 2. Ciphertext bukti pada SALINAN file ==")
    ev = ctx.db.one("SELECT * FROM evidence_items ORDER BY created_at LIMIT 1")
    if ev is None:
        print("Belum ada bukti; jalankan scripts/seed_demo.py atau unggah bukti dummy lebih dulu.")
    else:
        blob = bytearray((settings.evidence_dir / ev["encrypted_path"]).read_bytes())
        blob[-1] ^= 0x01
        print("hash ciphertext cocok catatan DB? ", sha256_hex(bytes(blob)) == ev["encrypted_sha256"])
        try:
            FileCrypto(ctx.keys.get("file_key")).decrypt(bytes(blob), ev["id"])
        except DecryptionError as exc:
            print("dekripsi salinan yang diubah ditolak:", exc)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    ctx.close()
