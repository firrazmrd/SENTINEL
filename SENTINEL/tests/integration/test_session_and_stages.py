import pytest
from conftest import PASSWORD

from sentinel.services import biometric_service as B
from sentinel.services import session_guard as G
from sentinel.ui.dashboard_view import evaluate
from sentinel.utils.exceptions import BiometricError, DeviceError


def _enroll_and_require(env, user, who="alice"):
    env.camera.frames = [who] * 3
    env.ctx.biometric.enroll(user)
    env.ctx.account.apply_auth_requirements(user, require_face=True, require_usb=True)


def test_face_stages_in_order_and_camera_released(env):
    u = env.make_user("INVESTIGATOR", "invest")
    _enroll_and_require(env, u)
    stages, streams = [], []
    env.camera.frames = ["alice+1"] * 3
    env.ctx.auth.login("invest", PASSWORD, on_stage=stages.append, on_stream=streams.append)
    assert stages == [B.CAMERA_INITIALIZING, B.CAMERA_ACTIVE, B.SCANNING, B.VERIFYING, B.VERIFIED]
    assert len(streams) == 1 and env.camera.streams[-1].closed


def test_failed_face_reports_failed_and_releases_camera(env):
    u = env.make_user("INVESTIGATOR", "invest")
    _enroll_and_require(env, u)
    env.camera.frames, stages = ["bob"] * 3, []
    with pytest.raises(BiometricError):
        env.ctx.auth.login("invest", PASSWORD, on_stage=stages.append)
    assert stages[-1] == B.FAILED and env.camera.streams[-1].closed


def test_camera_unavailable_reported(env):
    u = env.make_user("INVESTIGATOR", "invest")
    _enroll_and_require(env, u)
    env.camera.fail_open, stages = True, []
    with pytest.raises(DeviceError):
        env.ctx.auth.login("invest", PASSWORD, on_stage=stages.append)
    assert stages == [B.CAMERA_INITIALIZING, B.CAMERA_UNAVAILABLE]


def test_camera_never_opened_when_face_not_required_or_password_wrong(env):
    u = env.make_user("INVESTIGATOR", "invest")
    env.camera.frames = ["alice"] * 3
    env.ctx.biometric.enroll(u)                       # enrolled, but NOT required
    stages = []
    env.ctx.auth.login("invest", PASSWORD, on_stage=stages.append)
    assert stages == [] and getattr(env.camera, "opened", 0) == 0
    env.ctx.account.apply_auth_requirements(u, require_face=True, require_usb=True)
    with pytest.raises(Exception):
        env.ctx.auth.login("invest", "salah-salah", on_stage=stages.append)
    assert stages == [] and getattr(env.camera, "opened", 0) == 0     # password is checked before the camera starts


def test_session_guard_policy_and_reconnect(env):
    u = env.make_user("INVESTIGATOR", "invest")
    guard = env.ctx.session_guard
    assert guard.poll(u)[0] == G.OK
    saved = list(env.usb.drives)
    env.usb.drives = []
    assert guard.poll(u)[0] == G.DISCONNECTED
    env.usb.drives = saved                             # same dongle plugged back in
    assert guard.poll(u)[0] == G.OK
    env.ctx.account.apply_auth_requirements(u, require_face=False, require_usb=False, current_password=PASSWORD)
    env.usb.drives = []
    assert guard.poll(u)[0] == G.NOT_REQUIRED          # policy: USB not required for this account
    guard.record("SESSION_USB_DISCONNECTED", u, grace_seconds=10)
    assert env.ctx.db.scalar("SELECT count(*) FROM audit_logs WHERE event_type='SESSION_USB_DISCONNECTED'") == 1


def test_a_foreign_flash_drive_is_not_the_dongle(env):
    from sentinel.devices.usb_windows import DriveInfo
    u = env.make_user("INVESTIGATOR", "invest")
    env.usb.drives = [DriveInfo(str(env.usb.mount) + "/", "OTHER", "11223344")]   # different volume
    assert env.ctx.session_guard.poll(u)[0] == G.DISCONNECTED


def test_dashboard_overview_and_status_rules(env):
    u = env.make_user("INVESTIGATOR", "invest")
    assert evaluate(env.ctx.dashboard.security_overview(u))[0] == "AMAN"       # new accounts are issued a code
    env.ctx.db.run("UPDATE users SET recovery_code_hash=NULL WHERE username='invest'")   # like an account migrated from v1.2
    ov = env.ctx.dashboard.security_overview(u)
    assert ov["ledger"]["valid"] and ov["usb"]["state"] == "VALID" and ov["auth"]["require_usb"]
    level, _c, reasons = evaluate(ov)
    assert level == "PERHATIAN" and any("pemulihan" in r for r in reasons)      # no recovery code yet
    env.ctx.account.regenerate_recovery_code(u, PASSWORD)
    assert evaluate(env.ctx.dashboard.security_overview(u))[0] == "AMAN"
    ov["ledger"]["valid"], ov["ledger"]["first_invalid_index"] = False, 3
    assert evaluate(ov)[0] == "KRITIS"
    ov["ledger"]["valid"] = True
    ov["evidence_status"] = {"CIPHERTEXT_MODIFIED": 1}
    assert evaluate(ov)[0] == "KRITIS"
