import sqlite3
from pathlib import Path

import keyring
import pytest
from conftest import PASSWORD, MemoryKeyring

from sentinel import bootstrap
from sentinel.database.connection import Database
from sentinel.utils.exceptions import (
    AccountLockedError,
    AuthenticationError,
    DatabaseKeyError,
    KeyMissingError,
    PermissionDeniedError,
    StartupError,
    UsbValidationError,
    ValidationError,
)


def test_sqlcipher_is_really_encrypted(env):
    path = env.settings.db_path
    raw = path.read_bytes()
    assert not raw.startswith(b"SQLite format 3\x00")
    assert b"admin" not in raw and b"LOGIN" not in raw
    assert env.ctx.db.cipher_version()
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(str(path)).execute("SELECT count(*) FROM sqlite_master").fetchall()
    with pytest.raises(DatabaseKeyError):
        Database(path, bytes(32)).conn()
    key = env.ctx.keys.get("db_key")
    assert Database(path, key).scalar("SELECT count(*) FROM users") == 1


def test_connections_are_per_thread(env):
    import threading
    ids = {}
    ids["main"] = id(env.ctx.db.conn())

    def work():
        ids["thread"] = id(env.ctx.db.conn())
        assert env.ctx.db.scalar("SELECT count(*) FROM users") == 1
    t = threading.Thread(target=work); t.start(); t.join()
    assert ids["main"] != ids["thread"]


def test_first_run_creates_everything(env):
    assert env.ctx.users.__class__.__name__ == "UserService"
    first = env.ctx.db.one("SELECT * FROM ledger_blocks WHERE block_index=0")
    assert first["event_type"] == "LEDGER_GENESIS" and first["previous_hash"] == "0" * 64
    assert env.ctx.keys.has_all()
    assert env.ctx.ledger.check_chain().valid
    with pytest.raises(StartupError):
        bootstrap.first_run(env.settings, "x", "X", PASSWORD)  # never re-run over an existing DB


def test_missing_key_never_creates_or_overwrites_db(env):
    size = env.settings.db_path.stat().st_size
    env.ctx.close()
    keyring.set_keyring(MemoryKeyring())  # simulates a lost keyring
    with pytest.raises(KeyMissingError):
        bootstrap.open_existing(env.settings)
    assert env.settings.db_path.stat().st_size == size


def test_login_requires_password_and_usb(env):
    u = env.make_user("INVESTIGATOR", "invest")
    assert u.role == "INVESTIGATOR"
    with pytest.raises(AuthenticationError):
        env.ctx.auth.login("invest", "salah-salah")
    with pytest.raises(AuthenticationError):
        env.ctx.auth.login("tidak-ada", PASSWORD)
    env.usb.drives = []                                    # USB removed
    with pytest.raises(UsbValidationError):
        env.ctx.auth.login("invest", PASSWORD)


def test_usb_wrong_marker_or_serial_rejected(env):
    env.make_user("AUDITOR", "aud")
    marker = Path(env.usb.drives[0].mount) / ".sentinel-token"
    good = marker.read_text()
    marker.write_text(good.replace(good.split('"token": "')[1][:4], "ffff", 1))   # forged token
    with pytest.raises(UsbValidationError):
        env.ctx.auth.login("aud", PASSWORD)
    marker.write_text(good)
    assert env.ctx.auth.login("aud", PASSWORD)
    from sentinel.devices.usb_windows import DriveInfo
    env.usb.drives = [DriveInfo(env.usb.drives[0].mount, "X", "11111111")]          # different volume (clone elsewhere)
    with pytest.raises(UsbValidationError):
        env.ctx.auth.login("aud", PASSWORD)


def test_revoked_usb_rejected_and_reregistration(env):
    env.make_user("AUDITOR", "aud")
    env.ctx.usb.revoke(env.admin)
    with pytest.raises(UsbValidationError):
        env.ctx.auth.login("aud", PASSWORD)
    assert env.ctx.needs_usb_setup()
    env.ctx.usb.register_when_none_active(env.admin, env.usb.drives[0])
    assert env.ctx.auth.login("aud", PASSWORD)


def test_face_requirement_is_per_account_setting(env):
    u = env.make_user("INVESTIGATOR", "invest")
    env.ctx.auth.login("invest", PASSWORD)                  # default: face not required, password + USB still are
    with pytest.raises(ValidationError):                    # cannot require a face that is not enrolled
        env.ctx.account.apply_auth_requirements(u, require_face=True, require_usb=True)
    with pytest.raises(AuthenticationError):                # password stays mandatory
        env.ctx.auth.login("invest", "salah-salah")
    events = [r["details_json"] for r in env.ctx.db.all("SELECT details_json FROM audit_logs WHERE event_type='LOGIN_SUCCESS'")]
    assert any('"biometric":"NOT_REQUIRED"' in e for e in events)


def test_lockout_after_repeated_failures(env):
    env.make_user("AUDITOR", "aud")
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            env.ctx.auth.login("aud", "salah-salah")
    with pytest.raises(AccountLockedError):
        env.ctx.auth.login("aud", PASSWORD)         # even the right password is refused during cooldown


def test_disabled_account_and_stale_session(env):
    u = env.make_user("INVESTIGATOR", "invest")
    env.ctx.users.update_user(env.admin, u.id, status="DISABLED")
    with pytest.raises(AuthenticationError):
        env.ctx.auth.login("invest", PASSWORD)
    with pytest.raises(PermissionDeniedError):             # old in-memory session is useless once disabled
        env.ctx.cases.list_cases(u)


def test_user_management_rules(env):
    inv = env.make_user("INVESTIGATOR", "invest")
    with pytest.raises(PermissionDeniedError):
        env.ctx.users.create_user(inv, "hacker", "H", PASSWORD, "ADMIN")
    with pytest.raises(Exception):
        env.ctx.users.update_user(env.admin, env.admin.id, status="DISABLED")  # last admin
    with pytest.raises(Exception):
        env.ctx.users.create_user(env.admin, "short", "S", "123", "AUDITOR")


def test_no_secret_in_audit(env):
    env.make_user("AUDITOR", "aud")
    with pytest.raises(AuthenticationError):
        env.ctx.auth.login("aud", "typed-password-xyz")
    dump = str(env.ctx.db.all("SELECT * FROM audit_logs"))
    assert "typed-password-xyz" not in dump and PASSWORD not in dump
    with pytest.raises(ValueError):
        env.ctx.audit.record("X", details={"password": "p"})
