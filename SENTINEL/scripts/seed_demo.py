"""Membuat data DUMMY untuk demo pada instalasi yang sudah melewati first-run setup.
Jalankan di terminal (password Admin diminta secara interaktif, tidak disimpan):  python scripts/seed_demo.py
Membuat: investigator1 / analyst1 / auditor1 (password demo), CASE-001 + analyst, 1 bukti dummy, 1 pesan.
"""
import getpass
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Settings  # noqa: E402
from sentinel import bootstrap  # noqa: E402

DEMO_PASSWORD = "Demo-Pass-123"

settings = Settings.from_env()
settings.apply_environment()
ctx = bootstrap.open_existing(settings)
admin = ctx.auth.verify_admin_credentials(input("Username Admin: "), getpass.getpass("Password Admin: "))
existing = {u["username"] for u in ctx.users.list_users(admin)}
for username, name, role in (("investigator1", "Rina Investigator", "INVESTIGATOR"),
                             ("analyst1", "Dimas Analyst", "FORENSIC_ANALYST"),
                             ("auditor1", "Sari Auditor", "AUDITOR")):
    if username not in existing:
        created = ctx.users.create_user(admin, username, name, DEMO_PASSWORD, role)
        print(f"{username}: kode pemulihan {created['recovery_code']}  (simpan; hanya ditampilkan sekali)")
users = {u["username"]: u for u in ctx.users.list_users(admin)}
as_user = lambda n: type(admin)(users[n]["id"], n, users[n]["full_name"], users[n]["role"])
inv, ana = as_user("investigator1"), as_user("analyst1")
case = ctx.cases.create_case(inv, "Insiden kebocoran data (DUMMY)", "Kasus latihan; seluruh data fiktif.")
ctx.cases.assign_analyst(admin, case["id"], ana.id)
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp) / "log_akses_dummy.txt"
    f.write_text("2026-11-07 10:01 akses file X oleh user dummy\n" * 40, encoding="utf-8")
    ev = ctx.evidence.upload(inv, case["id"], f)
ctx.messages.send(inv, ana.id, "Bukti log akses (dummy) sudah diunggah. Mohon verifikasi hash.", case["id"])
print(f"Selesai: {case['case_number']}, bukti {ev['evidence_code']} (SHA-256 {ev['original_sha256']}).")
print(f"Akun demo: investigator1 / analyst1 / auditor1 — password: {DEMO_PASSWORD}")
