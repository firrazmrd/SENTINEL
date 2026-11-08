import os

import pytest

from sentinel.security.hashing import sha256_hex
from sentinel.utils.exceptions import PermissionDeniedError, ValidationError


@pytest.fixture
def world(env):
    ns = type("W", (), {})()
    ns.env, ns.ctx = env, env.ctx
    ns.inv = env.make_user("INVESTIGATOR", "inv1")
    ns.inv2 = env.make_user("INVESTIGATOR", "inv2")
    ns.ana = env.make_user("FORENSIC_ANALYST", "ana1")
    ns.ana2 = env.make_user("FORENSIC_ANALYST", "ana2")
    ns.aud = env.make_user("AUDITOR", "aud1")
    ns.case = env.ctx.cases.create_case(ns.inv, "Kasus dummy", "deskripsi")
    env.ctx.cases.assign_analyst(env.admin, ns.case["id"], ns.ana.id)
    ns.src = env.tmp / "bukti.txt"
    ns.src.write_bytes(b"ISI-BUKTI-DUMMY-RAHASIA " * 100)
    return ns


def test_case_numbering_visibility_and_updates(world):
    c, ctx = world.case, world.ctx
    assert c["case_number"] == "CASE-001"
    assert ctx.cases.create_case(world.inv2, "Kasus lain")["case_number"] == "CASE-002"
    assert [x["id"] for x in ctx.cases.list_cases(world.inv)] == [c["id"]]
    assert [x["id"] for x in ctx.cases.list_cases(world.ana)] == [c["id"]]
    assert ctx.cases.list_cases(world.ana2) == []
    assert len(ctx.cases.list_cases(world.aud)) == len(ctx.cases.list_cases(world.env.admin)) == 2
    with pytest.raises(PermissionDeniedError):
        ctx.cases.get_case(world.inv2, c["id"])
    with pytest.raises(PermissionDeniedError):
        ctx.cases.create_case(world.ana, "x")
    with pytest.raises(PermissionDeniedError):
        ctx.cases.assign_analyst(world.inv, c["id"], world.ana.id)
    ctx.cases.update_case(world.inv, c["id"], title="Judul baru", status="IN_REVIEW")
    with pytest.raises(PermissionDeniedError):                 # Investigator only while OPEN
        ctx.cases.update_case(world.inv, c["id"], title="lagi")
    ctx.cases.update_case(world.env.admin, c["id"], status="OPEN")  # Admin administrative edit
    with pytest.raises(ValidationError):
        ctx.cases.assign_analyst(world.env.admin, c["id"], world.inv.id)  # must be an analyst


def test_evidence_end_to_end(world):
    ctx, ev_svc = world.ctx, world.ctx.evidence
    orig = world.src.read_bytes()
    ev = ev_svc.upload(world.inv, world.case["id"], world.src)
    assert world.src.read_bytes() == orig                                    # original untouched
    assert ev["original_sha256"] == sha256_hex(orig) and ev["evidence_code"] == "EV-CASE-001-001"
    stored = world.env.settings.evidence_dir / ev["encrypted_path"]
    blob = stored.read_bytes()
    assert blob.startswith(b"SNTENC") and b"ISI-BUKTI" not in blob           # ciphertext only
    assert ev["encrypted_sha256"] == sha256_hex(blob)
    assert not list(world.env.settings.evidence_dir.rglob("*.tmp"))
    # Analyst: verify + export
    assert ev_svc.verify_plaintext(world.ana, ev["id"]).status == "VALID"
    out = world.env.tmp / "export.txt"
    assert ev_svc.export(world.ana, ev["id"], out).status == "VALID" and out.read_bytes() == orig
    with pytest.raises(FileExistsError):
        ev_svc.export(world.ana, ev["id"], out)
    with pytest.raises(PermissionDeniedError):
        ev_svc.export(world.ana, ev["id"], world.env.settings.evidence_dir / "x.txt")
    # Auditor: ciphertext hash only
    assert ev_svc.verify_ciphertext(world.aud, ev["id"]).status == "CIPHERTEXT_OK"
    with pytest.raises(PermissionDeniedError):
        ev_svc.verify_plaintext(world.aud, ev["id"])
    with pytest.raises(PermissionDeniedError):
        ev_svc.export(world.aud, ev["id"], out.with_name("aud.txt"))
    # others cannot touch it
    with pytest.raises(PermissionDeniedError):
        ev_svc.verify_plaintext(world.ana2, ev["id"])                           # unassigned analyst
    with pytest.raises(PermissionDeniedError):
        ev_svc.export(world.env.admin, ev["id"], world.env.tmp / "a.txt")       # Admin cannot decrypt
    with pytest.raises(PermissionDeniedError):
        ev_svc.export(world.inv, ev["id"], world.env.tmp / "b.txt")             # nor can the Investigator
    with pytest.raises(PermissionDeniedError):
        ev_svc.list_for_case(world.inv2, world.case["id"])
    assert len(ev_svc.list_for_case(world.env.admin, world.case["id"])) == 1    # Admin sees metadata
    ev_svc.add_note(world.ana, ev["id"], "hash cocok")
    events = {r["event_type"] for r in ctx.db.all("SELECT event_type FROM audit_logs")}
    assert {"EVIDENCE_UPLOADED", "EVIDENCE_DECRYPTED", "EVIDENCE_EXPORTED", "EVIDENCE_HASH_VERIFIED"} <= events


def test_tampered_ciphertext_detected(world):
    ev_svc = world.ctx.evidence
    ev = ev_svc.upload(world.inv, world.case["id"], world.src)
    stored = world.env.settings.evidence_dir / ev["encrypted_path"]
    data = bytearray(stored.read_bytes()); data[-1] ^= 1; stored.write_bytes(bytes(data))
    assert ev_svc.verify_ciphertext(world.aud, ev["id"]).status == "CIPHERTEXT_MODIFIED"
    out = world.env.tmp / "never.txt"
    assert ev_svc.export(world.ana, ev["id"], out).status == "CIPHERTEXT_MODIFIED"
    assert not out.exists()                                                      # no plaintext when tag/hash fails
    # attacker also fixes the DB hash -> AEAD tag must still catch it
    world.ctx.db.run("UPDATE evidence_items SET encrypted_sha256=? WHERE id=?", (sha256_hex(bytes(data)), ev["id"]))
    assert ev_svc.verify_plaintext(world.ana, ev["id"]).status == "DECRYPTION_FAILED"
    stored.unlink()
    assert ev_svc.verify_ciphertext(world.aud, ev["id"]).status == "CIPHERTEXT_MODIFIED"


def test_upload_validation(world):
    ev_svc, cid = world.ctx.evidence, world.case["id"]
    bad = world.env.tmp / "malware.exe"; bad.write_bytes(b"x")
    with pytest.raises(ValidationError):
        ev_svc.upload(world.inv, cid, bad)
    with pytest.raises(ValidationError):
        ev_svc.upload(world.inv, cid, world.env.tmp / "nope.txt")
    big = world.env.tmp / "big.txt"
    with open(big, "wb") as fh:
        fh.truncate(world.env.settings.max_file_bytes + 1)                       # sparse >100 MB
    with pytest.raises(ValidationError, match="terlalu besar"):
        ev_svc.upload(world.inv, cid, big)
    with pytest.raises(PermissionDeniedError):
        ev_svc.upload(world.ana, cid, world.src)
    with pytest.raises(PermissionDeniedError):
        ev_svc.upload(world.env.admin, cid, world.src)
    with pytest.raises(PermissionDeniedError):
        ev_svc.upload(world.inv2, cid, world.src)                                # not their case
    world.ctx.cases.update_case(world.env.admin, cid, status="CLOSED")
    with pytest.raises(ValidationError):
        ev_svc.upload(world.inv, cid, world.src)


def test_upload_exactly_at_limit_ok_and_orphan_cleanup(world, monkeypatch):
    ev_svc = world.ctx.evidence
    monkeypatch.setattr(ev_svc, "_max", 1024)
    ok = world.env.tmp / "edge.txt"; ok.write_bytes(os.urandom(1024))
    ev = ev_svc.upload(world.inv, world.case["id"], ok)
    assert ev["original_size"] == 1024
    monkeypatch.setattr(world.ctx.audit, "record", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        ev_svc.upload(world.inv, world.case["id"], ok)
    assert len(list(world.env.settings.evidence_dir.rglob("*.sntenc"))) == 1     # failed upload left no orphan file
