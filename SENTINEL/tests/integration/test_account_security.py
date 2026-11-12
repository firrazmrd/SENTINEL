import pytest
from conftest import PASSWORD, FakeFace

from sentinel import bootstrap
from sentinel.database.connection import Database
from sentinel.security import recovery_code
from sentinel.utils.exceptions import (
    AccountLockedError,
    AuthenticationError,
    BiometricError,
    PermissionDeniedError,
    UsbValidationError,
    ValidationError,
)


def _enroll(env, user, who="alice"):
    env.camera.frames = [who] * 3
    env.ctx.biometric.enroll(user)


def test_usb_requirement_can_be_switched_off_and_really_skips_usb(env):
    u = env.make_user("INVESTIGATOR", "invest")
    env.usb.drives = []
    with pytest.raises(UsbValidationError):
        env.ctx.auth.login("invest", PASSWORD)
    with pytest.raises(AuthenticationError):                       # weakening needs the current password
        env.ctx.account.apply_auth_requirements(u, require_face=False, require_usb=False)
    with pytest.raises(AuthenticationError):
        env.ctx.account.apply_auth_requirements(u, require_face=False, require_usb=False, current_password="salah-salah")
    env.ctx.account.apply_auth_requirements(u, require_face=False, require_usb=False, current_password=PASSWORD)
    assert env.ctx.auth.login("invest", PASSWORD).id == u.id        # no USB present, still logs in


def test_face_requirement_enforced_and_needs_template(env):
    u = env.make_user("INVESTIGATOR", "invest")
    with pytest.raises(ValidationError):
        env.ctx.account.apply_auth_requirements(u, require_face=True, require_usb=True)
    _enroll(env, u)
    ov = env.ctx.account.apply_auth_requirements(u, require_face=True, require_usb=True)
    assert ov["require_face"] and ov["has_face"]
    env.camera.frames = ["bob"] * 3
    with pytest.raises(BiometricError):
        env.ctx.auth.login("invest", PASSWORD)
    env.camera.frames = ["alice+1"] * 3
    assert env.ctx.auth.login("invest", PASSWORD)


def test_both_factors_together_and_settings_are_per_account(env):
    a, _b = env.make_user("INVESTIGATOR", "inv_a"), env.make_user("AUDITOR", "aud_b")
    _enroll(env, a)
    env.ctx.account.apply_auth_requirements(a, require_face=True, require_usb=True)
    env.camera.frames = ["bob"] * 3
    assert env.ctx.auth.login("aud_b", PASSWORD)                     # b never required a face
    with pytest.raises(BiometricError):
        env.ctx.auth.login("inv_a", PASSWORD)
    env.usb.drives = []
    with pytest.raises(UsbValidationError):                          # USB is checked before the face
        env.ctx.auth.login("inv_a", PASSWORD)


def test_settings_persist_after_restart(env):
    u = env.make_user("INVESTIGATOR", "invest")
    _enroll(env, u)
    env.ctx.account.apply_auth_requirements(u, require_face=True, require_usb=True)
    env.ctx.close()
    ctx2 = bootstrap.open_existing(env.settings, bootstrap.Devices(env.usb, env.camera, FakeFace()))
    try:
        ov = ctx2.account.overview(u)
        assert ov["require_face"] and ov["require_usb"]
        env.camera.frames = ["bob"] * 3
        with pytest.raises(BiometricError):
            ctx2.auth.login("invest", PASSWORD)
    finally:
        ctx2.close()


def test_admin_face_reset_clears_requirement_so_account_is_not_locked_out(env):
    u = env.make_user("INVESTIGATOR", "invest")
    _enroll(env, u)
    env.ctx.account.apply_auth_requirements(u, require_face=True, require_usb=True)
    env.ctx.biometric.delete_template(env.admin, u.id)
    assert env.ctx.auth.login("invest", PASSWORD)


def test_enroll_from_live_preview_frames(env):
    u = env.make_user("INVESTIGATOR", "invest")
    stream = env.ctx.biometric.open_preview(u)
    env.ctx.biometric.enroll_from_frames(u, stream.grab(3))
    stream.close()
    assert env.ctx.biometric.has_template(u.id)
    with pytest.raises(BiometricError):
        env.ctx.biometric.enroll_from_frames(u, [])


def test_non_admin_cannot_create_usb_dongle(env):
    u = env.make_user("INVESTIGATOR", "invest")
    assert env.ctx.account.overview(u)["can_manage_usb"] is False
    with pytest.raises(PermissionDeniedError):
        env.ctx.usb.register(u, env.usb.drives[0])


def test_change_password(env):
    u = env.make_user("INVESTIGATOR", "invest")
    with pytest.raises(AuthenticationError):
        env.ctx.account.change_password(u, "salah-salah", "Brand-New-Pass-1")
    with pytest.raises(ValidationError):
        env.ctx.account.change_password(u, PASSWORD, "short")
    with pytest.raises(ValidationError):
        env.ctx.account.change_password(u, PASSWORD, PASSWORD)
    env.ctx.account.change_password(u, PASSWORD, "Brand-New-Pass-1")
    assert env.ctx.db.one("SELECT password_hash FROM users WHERE username='invest'")["password_hash"].startswith("$argon2id$")
    with pytest.raises(AuthenticationError):
        env.ctx.auth.login("invest", PASSWORD)
    assert env.ctx.auth.login("invest", "Brand-New-Pass-1")


def test_reauth_failures_lock_the_account(env):
    u = env.make_user("INVESTIGATOR", "invest")
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            env.ctx.account.change_password(u, "salah-salah", "Brand-New-Pass-1")
    with pytest.raises(AccountLockedError):
        env.ctx.account.change_password(u, PASSWORD, "Brand-New-Pass-1")


def test_recovery_code_lifecycle(env):
    u = env.make_user("INVESTIGATOR", "invest")
    with pytest.raises(AuthenticationError):                         # no code yet -> generic failure
        env.ctx.auth.reset_password_with_recovery_code("invest", "AAAA-BBBB-CCCC-DDDD", "Brand-New-Pass-1")
    with pytest.raises(AuthenticationError):
        env.ctx.account.regenerate_recovery_code(u, "salah-salah")
    code1 = env.ctx.account.regenerate_recovery_code(u, PASSWORD)
    assert recovery_code.is_well_formed(code1) and len(code1) == 19
    stored = env.ctx.db.one("SELECT recovery_code_hash FROM users WHERE username='invest'")["recovery_code_hash"]
    assert stored.startswith("$argon2id$") and recovery_code.normalize(code1) not in stored
    code2 = env.ctx.account.regenerate_recovery_code(u, PASSWORD)    # regenerate: code1 is dead
    with pytest.raises(AuthenticationError):
        env.ctx.auth.reset_password_with_recovery_code("invest", code1, "Brand-New-Pass-1")
    with pytest.raises(ValidationError):                             # weak new password does not burn the code
        env.ctx.auth.reset_password_with_recovery_code("invest", code2, "short")
    code3 = env.ctx.auth.reset_password_with_recovery_code("invest", code2.lower().replace("-", " "), "Brand-New-Pass-1")
    assert code3 != code2
    with pytest.raises(AuthenticationError):                         # single use
        env.ctx.auth.reset_password_with_recovery_code("invest", code2, "Another-Pass-22")
    with pytest.raises(AuthenticationError):
        env.ctx.auth.login("invest", PASSWORD)
    assert env.ctx.auth.login("invest", "Brand-New-Pass-1")
    assert env.ctx.auth.reset_password_with_recovery_code("invest", code3, "Third-Pass-333")
    dump = str(env.ctx.db.all("SELECT * FROM audit_logs"))
    assert code1 not in dump and code2 not in dump and code3 not in dump and "Brand-New-Pass-1" not in dump
    events = {r["event_type"] for r in env.ctx.db.all("SELECT event_type FROM audit_logs")}
    assert {"RECOVERY_CODE_REGENERATED", "PASSWORD_RESET_RECOVERY", "REAUTH_FAILED", "LOGIN_FAILED"} <= events


def test_recovery_reset_rules(env):
    u = env.make_user("INVESTIGATOR", "invest")
    code = env.ctx.account.regenerate_recovery_code(u, PASSWORD)
    with pytest.raises(AuthenticationError):
        env.ctx.auth.reset_password_with_recovery_code("tidak-ada", code, "Brand-New-Pass-1")
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            env.ctx.auth.reset_password_with_recovery_code("invest", "AAAA-BBBB-CCCC-DDDD", "Brand-New-Pass-1")
    with pytest.raises(AccountLockedError):                           # brute force is throttled
        env.ctx.auth.reset_password_with_recovery_code("invest", code, "Brand-New-Pass-1")
    env.ctx.users.update_user(env.admin, u.id, status="DISABLED")
    with pytest.raises(AuthenticationError):
        env.ctx.auth.reset_password_with_recovery_code("invest", code, "Brand-New-Pass-1")


def test_reset_does_not_bypass_usb_at_login(env):
    u = env.make_user("INVESTIGATOR", "invest")
    code = env.ctx.account.regenerate_recovery_code(u, PASSWORD)
    env.ctx.auth.reset_password_with_recovery_code("invest", code, "Brand-New-Pass-1")
    env.usb.drives = []
    with pytest.raises(UsbValidationError):
        env.ctx.auth.login("invest", "Brand-New-Pass-1")


def test_migration_upgrades_v12_database(tmp_path):
    key = bytes(range(32))
    db = Database(tmp_path / "old.db", key)
    db.conn().executescript("""
        CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT, password_hash TEXT, full_name TEXT, role TEXT,
            status TEXT, failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT, created_at TEXT, last_login_at TEXT);
        CREATE TABLE biometric_templates (id TEXT PRIMARY KEY, user_id TEXT);
        INSERT INTO users(id,username) VALUES ('u1','with_face'),('u2','no_face');
        INSERT INTO biometric_templates VALUES ('b1','u1');""")
    assert set(db.migrate()) == {"require_face", "require_usb", "recovery_code_hash", "recovery_code_created_at"}
    rows = {r["id"]: r for r in db.all("SELECT * FROM users")}
    assert rows["u1"]["require_face"] == 1 and rows["u2"]["require_face"] == 0
    assert rows["u1"]["require_usb"] == 1 and rows["u1"]["recovery_code_hash"] is None
    assert db.migrate() == []                                          # idempotent
    db.close_all()


def test_created_user_gets_a_working_recovery_code(env):
    created = env.ctx.users.create_user(env.admin, "baru", "Pengguna Baru", PASSWORD, "AUDITOR")
    code = created["recovery_code"]
    assert recovery_code.is_well_formed(code)
    stored = env.ctx.db.one("SELECT recovery_code_hash FROM users WHERE username='baru'")["recovery_code_hash"]
    assert stored.startswith("$argon2id$") and recovery_code.normalize(code) not in stored
    assert "recovery_code" not in str(env.ctx.users.list_users(env.admin))      # never listed afterwards
    assert code not in str(env.ctx.db.all("SELECT * FROM audit_logs"))
    new_code = env.ctx.auth.reset_password_with_recovery_code("baru", code, "Brand-New-Pass-1")
    assert new_code != code and env.ctx.auth.login("baru", "Brand-New-Pass-1")


def test_first_admin_recovery_code_via_setup_flow(env):
    code = env.ctx.account.regenerate_recovery_code(env.admin, PASSWORD)
    assert env.ctx.account.overview(env.admin)["has_recovery_code"]
    assert env.ctx.auth.reset_password_with_recovery_code("admin", code, "Brand-New-Pass-1")
