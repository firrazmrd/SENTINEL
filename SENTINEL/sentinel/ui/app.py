from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from config import Settings
from sentinel import bootstrap
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.ui import common as C
from sentinel.ui.async_utils import AsyncRunner
from sentinel.utils.exceptions import SentinelError

log = logging.getLogger("sentinel.ui")

NAV = [  # (key, label, action required to see the menu entry; services enforce again)
    ("dashboard", "Dashboard", Action.VIEW_OWN_CASES),
    ("cases", "Cases", Action.VIEW_OWN_CASES),
    ("evidence", "Evidence", Action.VIEW_EVIDENCE_META),
    ("messages", "Secure Messages", Action.READ_MESSAGE),
    ("stego", "Steganography", Action.USE_STEGO),
    ("ledger", "Integrity Ledger", Action.VERIFY_LEDGER),
    ("audit", "Activity Logs", Action.VIEW_AUDIT),
    ("users", "User Management", Action.MANAGE_USERS),
    ("settings", "Settings", Action.MANAGE_OWN_SECURITY),
]


def view_classes() -> dict[str, type]:
    from sentinel.ui.audit_view import AuditView
    from sentinel.ui.cases_view import CasesView
    from sentinel.ui.dashboard_view import DashboardView
    from sentinel.ui.evidence_view import EvidenceView
    from sentinel.ui.ledger_view import LedgerView
    from sentinel.ui.messages_view import MessagesView
    from sentinel.ui.settings_view import SettingsView
    from sentinel.ui.steganography_view import SteganographyView
    from sentinel.ui.users_view import UsersView
    return {"dashboard": DashboardView, "cases": CasesView, "evidence": EvidenceView, "messages": MessagesView,
            "stego": SteganographyView, "ledger": LedgerView, "audit": AuditView, "users": UsersView,
            "settings": SettingsView}


class MainShell(ctk.CTkFrame):
    def __init__(self, master: Any, app: "SentinelApp") -> None:
        super().__init__(master, fg_color=C.BG)
        self.app = app
        side = ctk.CTkFrame(self, width=220, fg_color=C.PANEL, corner_radius=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ctk.CTkLabel(side, text="SENTINEL", font=C.font(22, "bold"), text_color=C.ACCENT).pack(pady=(20, 2))
        ctk.CTkLabel(side, text="Investigation Workspace", font=C.font(10), text_color=C.MUTED).pack(pady=(0, 18))
        self._buttons: dict[str, ctk.CTkButton] = {}
        for key, label, action in NAV:
            if PermissionService.role_allows(app.user.role, action):
                b = ctk.CTkButton(side, text=label, anchor="w", height=36, fg_color="transparent", text_color=C.TEXT,
                                  hover_color=C.PANEL_2, font=C.font(13), command=lambda k=key: self.navigate(k))
                b.pack(fill="x", padx=10, pady=2)
                self._buttons[key] = b
        main = ctk.CTkFrame(self, fg_color=C.BG)
        main.pack(side="left", fill="both", expand=True)
        top = ctk.CTkFrame(main, fg_color=C.PANEL, height=52, corner_radius=0)
        top.pack(fill="x")
        ctk.CTkLabel(top, text=f"{app.user.full_name}  ·  {app.user.role_label}", font=C.font(13, "bold"),
                     text_color=C.TEXT).pack(side="left", padx=16)
        ctk.CTkButton(top, text="Logout", width=80, fg_color=C.PANEL_2, hover_color="#22324f", font=C.font(12, "bold"),
                      command=app.logout).pack(side="right", padx=12, pady=10)
        self.usb_label = ctk.CTkLabel(top, text="USB: …", font=C.font(12), text_color=C.MUTED)
        self.usb_label.pack(side="right", padx=12)
        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=22, pady=18)
        self._view: Any = None
        self._alive = True
        self._poll_usb()
        self.navigate("dashboard")

    def navigate(self, key: str) -> None:
        if self._view is not None:
            self._view.destroy()
        for k, b in self._buttons.items():
            b.configure(fg_color=C.PANEL_2 if k == key else "transparent")
        self._view = view_classes()[key](self.content, self.app)
        self._view.pack(fill="both", expand=True)
        self._view.refresh()

    def _poll_usb(self) -> None:
        if not self._alive:
            return

        def show(check: Any) -> None:
            if self._alive:
                ok = check.state == "VALID"
                self.usb_label.configure(text=("USB: valid" if ok else f"USB: {check.message}"),
                                         text_color=C.OK if ok else C.WARN)
        self.app.run(self.app.ctx.usb.check, show, lambda _e: None)
        self.after(8000, self._poll_usb)

    def destroy(self) -> None:
        self._alive = False
        super().destroy()


class SentinelApp(ctk.CTk):
    def __init__(self, settings: Settings, devices: bootstrap.Devices | None = None) -> None:
        super().__init__()
        ctk.set_appearance_mode(settings.theme)
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=C.BG)
        self.title("SENTINEL — Secure Communication & Digital Evidence Management")
        self.geometry("1180x740")
        self.minsize(1020, 660)
        self.settings, self._devices = settings, devices
        self.ctx: bootstrap.AppContext | None = None
        self.user: CurrentUser | None = None
        self.runner = AsyncRunner(self)
        self._frame: Any = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start()

    # -- navigation ----------------------------------------------------------
    def _swap(self, frame: Any) -> None:
        if self._frame is not None:
            self._frame.destroy()
        self._frame = frame
        frame.pack(fill="both", expand=True)

    def start(self) -> None:
        from sentinel.ui.setup_view import SetupView, StartupErrorView
        try:
            if bootstrap.is_first_run(self.settings):
                self._swap(SetupView(self, mode="first_run"))
            else:
                self.ctx = bootstrap.open_existing(self.settings, self._devices)
                self.show_login()
        except SentinelError as exc:
            self._swap(StartupErrorView(self, str(exc)))

    def show_login(self) -> None:
        from sentinel.ui.login_view import LoginView
        if self.ctx is not None and self.ctx.needs_usb_setup():
            from sentinel.ui.setup_view import SetupView
            self._swap(SetupView(self, mode="usb_recovery"))
            return
        self.user = None
        self._swap(LoginView(self))

    def show_main(self, user: CurrentUser) -> None:
        self.user = user
        self._swap(MainShell(self, self))

    def logout(self) -> None:
        user, ctx = self.user, self.ctx
        self.user = None  # clear session state first
        if user is not None and ctx is not None:
            self.run(lambda: ctx.auth.logout(user), None, lambda _e: None)
        self.show_login()

    def on_close(self) -> None:
        self.runner.shutdown()
        if self.ctx is not None:
            self.ctx.close()
        self.destroy()

    # -- helpers ---------------------------------------------------------------
    def run(self, fn: Any, ok: Any = None, err: Any = None) -> None:
        self.runner.submit(fn, ok, err or self.show_error)

    def describe_error(self, exc: BaseException) -> str:
        if isinstance(exc, SentinelError):
            return str(exc)
        if isinstance(exc, FileExistsError):
            return "File tujuan sudah ada."
        if isinstance(exc, (PermissionError, OSError)):
            log.warning("OS error: %s", exc)
            return f"Operasi file gagal: {exc.strerror or exc}"
        log.exception("Unexpected error", exc_info=exc)
        return "Terjadi kesalahan tak terduga. Detail teknis ada di log aplikasi."

    def show_error(self, exc: BaseException) -> None:
        messagebox.showerror("SENTINEL", self.describe_error(exc))

    def confirm(self, title: str, message: str) -> bool:
        return messagebox.askokcancel(title, message)
