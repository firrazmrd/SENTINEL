from __future__ import annotations

import logging
import math
import time
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from config import Settings
from sentinel import bootstrap
from sentinel.services import session_guard
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


GRACE_SECONDS = 10        # how long a removed USB dongle may be re-inserted before the app closes itself
GUARD_INTERVAL_MS = 2000  # USB poll period: one cheap drive query per 2 s


class MainShell(ctk.CTkFrame):
    def __init__(self, master: Any, app: "SentinelApp") -> None:
        super().__init__(master, fg_color=C.BG)
        self.app = app
        self._alive, self._locked, self._deadline, self._overlay = True, False, 0.0, None
        self._busy_ticks = 0
        side = ctk.CTkFrame(self, width=232, fg_color=C.PANEL, corner_radius=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ctk.CTkFrame(self, width=1, height=1, fg_color=C.BORDER, corner_radius=0).pack(side="left", fill="y")
        ctk.CTkFrame(side, fg_color=C.CYAN, width=28, height=3, corner_radius=0).pack(anchor="w", padx=C.SP_XL, pady=(C.SP_XL, C.SP_S))
        ctk.CTkLabel(side, text="SENTINEL", font=C.font(21, "bold"), text_color=C.TEXT).pack(anchor="w", padx=C.SP_XL)
        ctk.CTkLabel(side, text="INVESTIGATION WORKSPACE", font=C.mono(9, "bold"), text_color=C.MUTED
                     ).pack(anchor="w", padx=C.SP_XL, pady=(0, C.SP_XL))
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._bars: dict[str, ctk.CTkFrame] = {}
        for key, label, action in NAV:
            if PermissionService.role_allows(app.user.role, action):
                row = ctk.CTkFrame(side, fg_color="transparent", height=38)
                row.pack(fill="x", pady=1)
                bar = ctk.CTkFrame(row, width=3, height=1, fg_color="transparent", corner_radius=0)
                bar.pack(side="left", fill="y")
                b = ctk.CTkButton(row, text=label, anchor="w", height=36, fg_color="transparent", text_color=C.MUTED,
                                  hover_color=C.PANEL_2, font=C.font(13), corner_radius=C.RADIUS_S,
                                  command=lambda k=key: self.navigate(k))
                b.pack(side="left", fill="x", expand=True, padx=(C.SP_S, C.SP_S))
                self._buttons[key], self._bars[key] = b, bar
        ctk.CTkLabel(side, text="v1.3  ·  SESI AKTIF", font=C.mono(9), text_color=C.MUTED
                     ).pack(side="bottom", anchor="w", padx=C.SP_XL, pady=C.SP_L)
        main = ctk.CTkFrame(self, fg_color=C.BG, corner_radius=0)
        main.pack(side="left", fill="both", expand=True)
        top = ctk.CTkFrame(main, fg_color=C.PANEL, height=52, corner_radius=0)
        top.pack(fill="x")
        ctk.CTkLabel(top, text=app.user.full_name, font=C.font(13, "bold"), text_color=C.TEXT).pack(side="left", padx=(C.SP_XL, C.SP_S))
        ctk.CTkLabel(top, text=app.user.role_label.upper(), font=C.mono(10, "bold"), text_color=C.CYAN, fg_color=C.PANEL_2,
                     corner_radius=C.RADIUS_S, width=10, height=22).pack(side="left", ipadx=8)
        ctk.CTkButton(top, text="Logout", width=84, height=32, fg_color=C.PANEL_2, hover_color=C.HOVER_2, text_color=C.TEXT,
                      font=C.font(12, "bold"), corner_radius=C.RADIUS_S, command=app.logout).pack(side="right", padx=C.SP_L, pady=10)
        self.usb_pill = C.StatusPill(top, "USB …", C.MUTED)
        self.usb_pill.pack(side="right", padx=C.SP_S)
        self.busy = ctk.CTkProgressBar(main, height=2, corner_radius=0, mode="indeterminate", fg_color=C.BG,
                                       progress_color=C.ACCENT)
        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=C.SP_XL, pady=C.SP_L + 2)
        self._view: Any = None
        self._busy_shown = False
        self._watch_busy()
        self._guard_tick()
        self.navigate("dashboard")

    # -- navigation ------------------------------------------------------------------------------
    def navigate(self, key: str) -> None:
        if self._locked:  # sensitive operations are stopped while the USB dongle is missing
            return
        if self._view is not None:
            self._view.destroy()
        for k, b in self._buttons.items():
            on = k == key
            b.configure(fg_color=C.PANEL_2 if on else "transparent", text_color=C.TEXT if on else C.MUTED)
            self._bars[k].configure(fg_color=C.ACCENT if on else "transparent")
        self._view = view_classes()[key](self.content, self.app)
        self._view.pack(fill="both", expand=True)
        self._view.refresh()

    # -- loading indicator (any background job running for more than ~0.3 s) ---------------------------
    def _watch_busy(self) -> None:
        if not self._alive:
            return
        self._busy_ticks = self._busy_ticks + 1 if self.app.runner.pending > 0 else 0
        want = self._busy_ticks >= 2
        if want and not self._busy_shown:
            self.busy.pack(fill="x", before=self.content)
            self.busy.start()
            self._busy_shown = True
        elif not want and self._busy_shown:
            self.busy.stop()
            self.busy.pack_forget()
            self._busy_shown = False
        self.after(150, self._watch_busy)

    # -- USB session guard -------------------------------------------------------------------------
    def _guard_tick(self) -> None:
        if not self._alive:
            return
        ctx, user = self.app.ctx, self.app.user

        def job() -> tuple:
            state, check = ctx.session_guard.poll(user)
            if check is None and state != session_guard.UNKNOWN:
                check = ctx.usb.check()  # not required for this account: still feed the status indicator
            return state, check
        self.app.run(job, self._guard_result, lambda _e: None)
        self.after(GUARD_INTERVAL_MS, self._guard_tick)

    def _guard_result(self, result: tuple) -> None:
        if not self._alive:
            return
        state, check = result
        if check is not None:
            ok = check.state == "VALID"
            self.usb_pill.set("USB VALID" if ok else "USB " + check.state.replace("_", " "), C.OK if ok else C.WARN, False)
        if state == session_guard.DISCONNECTED and not self._locked:
            self._lock_session()
        elif state != session_guard.DISCONNECTED and self._locked:
            self._unlock_session()

    def _lock_session(self) -> None:
        ctx, user = self.app.ctx, self.app.user
        self._locked, self._deadline = True, time.monotonic() + GRACE_SECONDS
        self.app.run(lambda: ctx.session_guard.record("SESSION_USB_DISCONNECTED", user, grace_seconds=GRACE_SECONDS),
                     None, lambda _e: None)
        ov = ctk.CTkFrame(self, fg_color="#070C16", corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        box = ctk.CTkFrame(ov, fg_color=C.PANEL, border_width=1, border_color=C.ERR, corner_radius=C.RADIUS)
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="USB DONGLE TERPUTUS", font=C.mono(13, "bold"), text_color=C.ERR).pack(padx=48, pady=(28, 6))
        ctk.CTkLabel(box, text="Operasi sensitif dihentikan. Pasang kembali USB dongle terdaftar untuk melanjutkan;\n"
                     "jika tidak, SENTINEL ditutup otomatis.", font=C.font(12), text_color=C.TEXT, justify="center"
                     ).pack(padx=32)
        self.count_label = ctk.CTkLabel(box, text=str(GRACE_SECONDS), font=C.mono(44, "bold"), text_color=C.WARN)
        self.count_label.pack(pady=C.SP_M)
        ctk.CTkButton(box, text="Tutup Aplikasi Sekarang", fg_color=C.ERR, hover_color="#B93E3E", text_color=C.ON_ACCENT,
                      font=C.font(12, "bold"), height=34, command=self._expire).pack(pady=(0, 28))
        ov.lift()
        ov.focus_set()
        self._overlay = ov
        self._countdown()

    def _countdown(self) -> None:
        if not self._alive or not self._locked:
            return
        remaining = math.ceil(self._deadline - time.monotonic())
        if remaining <= 0:
            self._expire()
            return
        self.count_label.configure(text=str(remaining))
        self.after(250, self._countdown)

    def _unlock_session(self) -> None:
        ctx, user = self.app.ctx, self.app.user
        self._locked = False
        if self._overlay is not None:
            self._overlay.destroy()
            self._overlay = None
        self.app.run(lambda: ctx.session_guard.record("SESSION_USB_RECONNECTED", user), None, lambda _e: None)
        if self._view is not None:
            self._view.refresh()

    def _expire(self) -> None:
        if not self._alive:
            return
        self._alive = False  # stop every poll first
        app, ctx, user = self.app, self.app.ctx, self.app.user
        app.run(lambda: ctx.session_guard.record("SESSION_CLOSED_USB_REMOVED", user), lambda _r: app.on_close(),
                lambda _e: app.on_close())

    def destroy(self) -> None:
        self._alive = False
        super().destroy()


class SentinelApp(ctk.CTk):
    def __init__(self, settings: Settings, devices: bootstrap.Devices | None = None) -> None:
        super().__init__()
        C.init_fonts(self)
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
