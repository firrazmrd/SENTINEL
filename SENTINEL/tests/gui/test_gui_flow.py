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
    a.on_close()


def test_full_gui_flow(app):
    from sentinel.ui.app import MainShell
    from sentinel.ui.login_view import LoginView
    from sentinel.ui.setup_view import SetupView
    view = app._frame
    assert isinstance(view, SetupView)
    for e, v in ((view.f_user, "admin"), (view.f_name, "Admin Utama"), (view.f_pw, PASSWORD), (view.f_pw2, PASSWORD)):
        e.insert(0, v)
    view._create_admin()
    wait(app, lambda: app.ctx is not None and getattr(view, "_drives", None))
    view._do_register()
    wait(app, lambda: isinstance(app._frame, LoginView))
    login = app._frame
    wait(app, lambda: "valid" in login.usb.cget("text").lower())
    login.user.insert(0, "admin"); login.pw.insert(0, "wrong-pass-1")
    login.submit()
    wait(app, lambda: login.msg.cget("text") == "Username atau password salah.")
    login.pw.delete(0, "end"); login.pw.insert(0, PASSWORD)
    login.face.deselect()
    login.submit()
    wait(app, lambda: isinstance(app._frame, MainShell))
    shell = app._frame
    for key in ("cases", "evidence", "messages", "stego", "ledger", "audit", "users", "profile", "dashboard"):
        shell.navigate(key)
        pump(app, 0.6)
        assert not app.errors, (key, app.errors)
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
