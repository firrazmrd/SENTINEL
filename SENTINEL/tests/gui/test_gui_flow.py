"""Drives the real CustomTkinter app (needs a display; run with: xvfb-run -a python -m pytest tests/gui)."""
import time

import keyring
import pytest

tk = pytest.importorskip("tkinter")

from conftest import PASSWORD, FakeCamera, FakeFace, FakeUsb, MemoryKeyring  # noqa: E402

from config import Settings  # noqa: E402
from sentinel import bootstrap  # noqa: E402


def pump(app, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def wait(app, cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        app.update()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("timeout waiting for condition")


@pytest.fixture
def app(tmp_path):
    from sentinel.ui.app import SentinelApp
    keyring.set_keyring(MemoryKeyring())
    usb_dir = tmp_path / "usb"; usb_dir.mkdir()
    settings = Settings(data_dir=tmp_path / "data", deepface_home=tmp_path / "m")
    devices = bootstrap.Devices(FakeUsb(usb_dir), FakeCamera(), FakeFace())
    try:
        a = SentinelApp(settings, devices)
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    a.errors = []
    a.show_error = lambda exc: a.errors.append(exc)
    yield a
    try:
        a.on_close()
    except tk.TclError:  # a test may already have closed the app (USB-removed shutdown)
        pass


def test_full_gui_flow(app):
    from sentinel.ui.app import MainShell
    from sentinel.ui.login_view import LoginView
    from sentinel.ui.setup_view import SetupView
    view = app._frame
    assert isinstance(view, SetupView)
    for e, v in ((view.f_user, "admin"), (view.f_name, "Admin Utama"), (view.f_pw, PASSWORD), (view.f_pw2, PASSWORD)):
        e.insert(0, v)
    view._create_admin()
    wait(app, lambda: getattr(view, "recovery_code", None))      # first Admin gets a recovery code at creation
    from sentinel.security import recovery_code as rc
    assert rc.is_well_formed(view.recovery_code)
    view._continue_to_usb()
    wait(app, lambda: app.ctx is not None and getattr(view, "_drives", None))
    view._do_register()
    wait(app, lambda: isinstance(app._frame, LoginView))
    login = app._frame
    wait(app, lambda: "valid" in login.usb_text.cget("text").lower())
    login.user.insert(0, "admin"); login.pw.insert(0, "wrong-pass-1")
    login.submit()
    wait(app, lambda: login.msg.cget("text") == "Username atau password salah.")
    login.pw.delete(0, "end"); login.pw.insert(0, PASSWORD)
    login.submit()
    wait(app, lambda: isinstance(app._frame, MainShell))
    shell = app._frame
    for key in ("cases", "evidence", "messages", "stego", "ledger", "audit", "users", "settings", "dashboard"):
        shell.navigate(key)
        pump(app, 0.6)
        assert not app.errors, (key, app.errors)
    # dashboard: status strip is filled from real data
    shell.navigate("dashboard"); pump(app, 0.5)
    dash = shell._view
    wait(app, lambda: dash._cells["security"][1].cget("text") in ("AMAN", "PERHATIAN", "KRITIS"))
    assert dash._cells["usb"][1].cget("text") == "TERHUBUNG" and dash._cells["ledger"][1].cget("text") == "VALID"
    assert getattr(app._devices.camera, "opened", 0) == 0     # face not required: the camera was never switched on
    # cases: create one as Admin
    shell.navigate("cases"); pump(app, 0.4)
    v = shell._view
    v.title_e.insert(0, "Kasus GUI"); v.desc.insert("1.0", "uji gui"); v.create()
    wait(app, lambda: len(v.table.tree.get_children()) == 1)
    # users: create an investigator
    shell.navigate("users"); pump(app, 0.5)
    u = shell._view
    u.n_user.insert(0, "invest"); u.n_name.insert(0, "Investigator Satu"); u.n_pw.insert(0, PASSWORD)
    u.create()
    wait(app, lambda: len(u.table.tree.get_children()) == 2)
    for w in app.winfo_children():                          # the Admin is shown the new user's recovery code
        if w.winfo_class() == "Toplevel":
            w.destroy()
    # settings page: real status, apply persists to the account
    shell.navigate("settings"); pump(app, 0.6)
    st = shell._view
    wait(app, lambda: st._saved is not None)
    assert st.usb_status.cget("text") == "USB dongle: terdaftar" and st.face_status.cget("text") == "Wajah: belum terdaftar"
    assert st.rec_status.cget("text") == "Kode pemulihan: sudah dibuat"
    assert st.cb_usb.get() == 1 and st.cb_face.get() == 0
    st.cb_face.select(); st.apply()                          # no template yet -> rejected by the service
    wait(app, lambda: "Daftarkan wajah" in st._status.cget("text"))
    wait(app, lambda: st.cb_face.get() == 0)                  # checkbox snaps back to the saved state
    st.search_usb(); pump(app, 0.4)
    assert not app.errors
    # ledger verify through the UI
    shell.navigate("ledger"); pump(app, 0.5)
    ledger = shell._view
    ledger.verify()
    wait(app, lambda: "VALID" in ledger.result.cget("text") and "TIDAK" not in ledger.result.cget("text"))
    assert not app.errors
    # logout returns to login and clears the session
    app.logout()
    pump(app, 0.3)
    assert isinstance(app._frame, LoginView) and app.user is None


def test_gui_role_menus_and_denials(app):
    """An Investigator's menu has no Users/Ledger-admin pages and the Auditor menu has no message/stego pages."""
    from sentinel.services.permission_service import PermissionService as P
    from sentinel.ui.app import NAV
    shown = lambda role: {k for k, _l, a in NAV if P.role_allows(role, a)}
    assert "users" not in shown("INVESTIGATOR") and "users" in shown("ADMIN")
    assert not ({"messages", "stego"} & shown("AUDITOR"))
    assert {"cases", "evidence", "ledger", "audit"} <= shown("AUDITOR")


def _prepared_app(tmp_path, require_face):
    """An installation that already finished first-run, so the app starts on the login screen."""
    from sentinel.ui.app import SentinelApp
    keyring.set_keyring(MemoryKeyring())
    usb_dir = tmp_path / "usb"; usb_dir.mkdir()
    settings = Settings(data_dir=tmp_path / "data", deepface_home=tmp_path / "m")
    devices = bootstrap.Devices(FakeUsb(usb_dir), FakeCamera(), FakeFace())
    ctx, admin = bootstrap.first_run(settings, "admin", "Admin Utama", PASSWORD, devices)
    ctx.usb.register(admin, devices.usb.drives[0])
    if require_face:
        devices.camera.frames = ["alice"] * 3
        ctx.biometric.enroll(admin)
        ctx.account.apply_auth_requirements(admin, require_face=True, require_usb=True)
    ctx.close()
    try:
        a = SentinelApp(settings, devices)
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    a.errors = []
    a.show_error = lambda exc: a.errors.append(exc)
    return a, devices


@pytest.mark.parametrize("who,ok", [("alice+1", True), ("bob", False)])
def test_gui_login_camera_preview_and_stages(tmp_path, who, ok):
    from sentinel.ui.app import MainShell
    app, devices = _prepared_app(tmp_path, require_face=True)
    try:
        login = app._frame
        seen = []
        real = login.camera.set_stage
        login.camera.set_stage = lambda st: (seen.append(st), real(st))
        assert login.camera.stage == "IDLE"                       # standby: no camera before the credentials are checked
        devices.camera.frames = [who] * 3
        login.user.insert(0, "admin"); login.pw.insert(0, PASSWORD)
        login.submit()
        if ok:
            wait(app, lambda: isinstance(app._frame, MainShell))
            assert seen[:5] == ["CAMERA_INITIALIZING", "CAMERA_ACTIVE", "SCANNING", "VERIFYING", "VERIFIED"]
        else:
            wait(app, lambda: login.btn.cget("state") == "normal" and login.msg.cget("text"))
            assert seen[-1] == "FAILED" and "tidak cocok" in login.msg.cget("text")
        assert devices.camera.streams and all(s.closed for s in devices.camera.streams)   # camera always released
    finally:
        app.on_close()


def test_gui_usb_removed_locks_then_reconnect_unlocks_then_expiry_closes(tmp_path):
    from sentinel.ui.app import MainShell
    app, devices = _prepared_app(tmp_path, require_face=False)
    login = app._frame
    login.user.insert(0, "admin"); login.pw.insert(0, PASSWORD); login.submit()
    wait(app, lambda: isinstance(app._frame, MainShell))
    shell = app._frame
    pump(app, 0.4)
    drives = list(devices.usb.drives)
    devices.usb.drives = []                                         # USB pulled out
    shell._guard_tick()
    wait(app, lambda: shell._locked and shell._overlay is not None)
    shell.navigate("cases")                                         # sensitive navigation is blocked while locked
    assert shell._view.__class__.__name__ == "DashboardView"
    devices.usb.drives = drives                                     # re-inserted inside the grace period
    shell._guard_tick()
    wait(app, lambda: not shell._locked and shell._overlay is None)
    devices.usb.drives = []
    shell._guard_tick()
    wait(app, lambda: shell._locked)
    shell._deadline = 0                                             # grace period over -> closes the app
    closed = []
    real_close = app.on_close
    app.on_close = lambda: (closed.append(1), real_close())
    wait(app, lambda: closed)
    assert app.ctx is not None
