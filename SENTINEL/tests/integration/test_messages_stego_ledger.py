import pytest
from PIL import Image

from sentinel.utils.exceptions import DecryptionError, PermissionDeniedError, ValidationError


@pytest.fixture
def w(env):
    ns = type("W", (), {})()
    ns.env, ns.ctx = env, env.ctx
    ns.inv, ns.ana = env.make_user("INVESTIGATOR", "inv1"), env.make_user("FORENSIC_ANALYST", "ana1")
    ns.ana2, ns.aud = env.make_user("FORENSIC_ANALYST", "ana2"), env.make_user("AUDITOR", "aud1")
    return ns


def test_message_flow(w):
    ms = w.ctx.messages
    mid = ms.send(w.inv, w.ana.id, "Bukti siap diperiksa — rahasia 123")
    row = w.ctx.db.one("SELECT * FROM messages WHERE id=?", (mid,))
    assert row["algorithm"] == "VIGENERE+AES-256-GCM" and b"rahasia" not in row["ciphertext"] and len(row["nonce"]) == 12
    assert "rahasia" not in str(w.ctx.db.all("SELECT * FROM audit_logs"))       # no plaintext in audit
    assert ms.unread_count(w.ana) == 1
    assert ms.read(w.ana, mid) == "Bukti siap diperiksa — rahasia 123"
    assert ms.unread_count(w.ana) == 0 and len(ms.inbox(w.ana)) == 1 and len(ms.sent(w.inv)) == 1
    assert ms.read(w.inv, mid).startswith("Bukti")                              # sender may re-read
    with pytest.raises(PermissionDeniedError):
        ms.read(w.ana2, mid)                                                    # third party
    with pytest.raises(PermissionDeniedError):
        ms.read(w.env.admin, mid)                                               # Admin is not special here
    with pytest.raises(PermissionDeniedError):
        ms.read(w.aud, mid)
    with pytest.raises(PermissionDeniedError):
        ms.send(w.aud, w.ana.id, "x")
    with pytest.raises(ValidationError):
        ms.send(w.inv, w.aud.id, "x")                                           # Auditors cannot receive
    with pytest.raises(ValidationError):
        ms.send(w.inv, w.inv.id, "x")
    with pytest.raises(ValidationError):
        ms.send(w.inv, w.ana.id, "   ")


def test_message_tamper_and_swap_rejected(w):
    ms = w.ctx.messages
    a, b = ms.send(w.inv, w.ana.id, "pesan A"), ms.send(w.inv, w.ana.id, "pesan B")
    ca = w.ctx.db.one("SELECT ciphertext, nonce FROM messages WHERE id=?", (a,))
    w.ctx.db.run("UPDATE messages SET ciphertext=?, nonce=? WHERE id=?", (ca["ciphertext"], ca["nonce"], b))
    with pytest.raises(DecryptionError):                                        # AAD binds ciphertext to message id
        ms.read(w.ana, b)
    flipped = bytearray(ca["ciphertext"]); flipped[0] ^= 1
    w.ctx.db.run("UPDATE messages SET ciphertext=? WHERE id=?", (bytes(flipped), a))
    with pytest.raises(DecryptionError):
        ms.read(w.ana, a)


def _png(path, size=(64, 64), mode="RGB"):
    Image.effect_noise(size, 60).convert(mode).save(path, "PNG")
    return path


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_stego_round_trip(w, mode):
    src = _png(w.env.tmp / "cover.png", mode=mode)
    before = src.read_bytes()
    out = w.env.tmp / "out.png"
    r = w.ctx.stego.embed(w.inv, src, "Pesan rahasia: titik temu 21:00 — café", out)
    assert src.read_bytes() == before and out.exists()                          # source never overwritten
    assert w.ctx.stego.extract(w.ana, out) == "Pesan rahasia: titik temu 21:00 — café"
    assert w.ctx.db.one("SELECT * FROM stego_artifacts WHERE id=?", (r.artifact_id,))["created_by"] == w.inv.id
    with pytest.raises(ValidationError):
        w.ctx.stego.embed(w.inv, src, "x", src)                                 # refuses to overwrite the source
    with pytest.raises(ValidationError):
        w.ctx.stego.extract(w.inv, src)                                         # clean image has no payload
    with pytest.raises(PermissionDeniedError):
        w.ctx.stego.extract(w.aud, out)


def test_stego_capacity_and_tamper(w):
    tiny = _png(w.env.tmp / "tiny.png", (10, 10))
    with pytest.raises(ValidationError):
        w.ctx.stego.embed(w.inv, tiny, "A" * 500, w.env.tmp / "t_out.png")
    src = _png(w.env.tmp / "cover.png")
    out = w.env.tmp / "out.png"
    w.ctx.stego.embed(w.inv, src, "isi", out)
    img = Image.open(out).convert("RGB")
    data = bytearray(img.tobytes())
    for i in range(39 * 8 + 5, 39 * 8 + 40):
        data[i] ^= 1                                                            # flip LSBs inside ciphertext
    Image.frombytes("RGB", img.size, bytes(data)).save(w.env.tmp / "bad.png")
    with pytest.raises(DecryptionError):
        w.ctx.stego.extract(w.inv, w.env.tmp / "bad.png")
    jpg = w.env.tmp / "x.jpg"; Image.new("RGB", (50, 50)).save(jpg, "JPEG")
    with pytest.raises(ValidationError, match="PNG"):
        w.ctx.stego.extract(w.inv, jpg)


def test_ledger_chain_and_tamper_detection(w):
    ms = w.ctx.messages
    for i in range(4):
        ms.send(w.inv, w.ana.id, f"m{i}")
    res = w.ctx.ledger.verify(w.aud)
    assert res.valid and res.blocks_checked >= 10
    assert w.ctx.db.scalar("SELECT count(*) FROM ledger_blocks") == w.ctx.db.scalar("SELECT count(*) FROM audit_logs")
    # 1) altered block data
    victim = w.ctx.db.all("SELECT block_index FROM ledger_blocks ORDER BY block_index")[5]["block_index"]
    w.ctx.db.run("UPDATE ledger_blocks SET actor_id=NULL WHERE block_index=?", (victim,))
    bad = w.ctx.ledger.check_chain()
    assert not bad.valid and bad.first_invalid_index == victim
    w.ctx.db.run("UPDATE ledger_blocks SET actor_id=? WHERE block_index=?", (w.inv.id, victim))  # (restore not guaranteed equal)
    # 2) altered audit log text
    w.ctx.db.run("UPDATE audit_logs SET details_json='{\"x\":1}' WHERE id=(SELECT audit_log_id FROM ledger_blocks WHERE block_index=3)")
    assert w.ctx.ledger.check_chain().first_invalid_index == 3
    # 3) removed block in the middle
    w.ctx.db.run("PRAGMA foreign_keys=OFF")
    w.ctx.db.run("DELETE FROM ledger_blocks WHERE block_index=2")
    assert w.ctx.ledger.check_chain().first_invalid_index == 2


def test_ledger_documented_limitation_tail_truncation(w):
    w.ctx.messages.send(w.inv, w.ana.id, "x")
    last = w.ctx.db.scalar("SELECT max(block_index) FROM ledger_blocks")
    w.ctx.db.run("DELETE FROM ledger_blocks WHERE block_index=?", (last,))
    assert w.ctx.ledger.check_chain().valid        # known limitation: no external anchor (SRS 5.7)


def test_audit_log_scoping(w):
    c = w.ctx.cases.create_case(w.inv, "K")
    w.ctx.cases.assign_analyst(w.env.admin, c["id"], w.ana.id)
    w.ctx.messages.send(w.inv, w.ana2.id, "pribadi")
    assert w.ctx.audit.search(w.aud) and w.ctx.audit.search(w.env.admin)
    mine = w.ctx.audit.search(w.ana2)
    assert all(r["actor_id"] == w.ana2.id for r in mine)                         # own activity only
    ana_view = w.ctx.audit.search(w.ana)
    assert any(r["event_type"] == "CASE_CREATED" for r in ana_view)             # assigned-case events visible
    assert not any(r["event_type"] == "MESSAGE_SENT" for r in ana_view)
    assert w.ctx.dashboard.summary(w.aud)["cases"] == 1
