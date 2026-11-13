"""Split-screen login. Left: live camera + authentication info. Right: branding and credentials.

The camera is opened by the Face Recognition service itself, and only when the account that just passed the
password (and USB) check requires face verification. Which accounts require it is private per-account data, so
the screen cannot (and must not) guess it before the user identifies themselves."""
from __future__ import annotations

import queue
from typing import Any

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.ui.camera_widget import STATUS, CameraPanel


class LoginView(ctk.CTkFrame):
    def __init__(self, app: Any) -> None:
        super().__init__(app, fg_color=C.BG)
        self.app, self._alive, self._busy, self._face_used = app, True, False, False
        self._events: queue.Queue = queue.Queue()
        self.grid_columnconfigure(0, weight=5, uniform="login")
        self.grid_columnconfigure(1, weight=4, uniform="login")
        self.grid_rowconfigure(0, weight=1)
        self._build_left()
        self._build_right()
        self.user.bind("<Return>", lambda _e: self.submit())
        self.pw.bind("<Return>", lambda _e: self.submit())
        self.user.focus_set()
        self._poll_usb()

    # -- left: camera + authentication info -----------------------------------------------------
    def _build_left(self) -> None:
        left = ctk.CTkFrame(self, fg_color=C.PANEL, corner_radius=0, border_width=0)
        left.grid(row=0, column=0, sticky="nsew")
        inner = ctk.CTkFrame(left, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=C.SP_XL + 8, pady=C.SP_XL + 8)
        ctk.CTkLabel(inner, text="VERIFIKASI IDENTITAS", font=C.mono(11, "bold"), text_color=C.MUTED).pack(anchor="w")
        ctk.CTkLabel(inner, text="Face Recognition", font=C.font(22, "bold"), text_color=C.TEXT).pack(anchor="w", pady=(2, 12))
        self.camera = CameraPanel(inner, 480, 360)
        self.camera.pack(fill="both", expand=True)
        self.pill = C.StatusPill(inner, "CAMERA OFF", C.MUTED, bg=C.PANEL_2)
        self.pill.pack(anchor="w", pady=(C.SP_M, C.SP_M))
        ctk.CTkFrame(inner, fg_color=C.BORDER, height=1).pack(fill="x")
        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(fill="x", pady=C.SP_M)
        C.kv_row(info, 0, "Password", "wajib untuk semua akun", C.OK)
        self.usb_dot = C.kv_row(info, 1, "USB dongle", "memeriksa…", C.MUTED)
        self.usb_text = info.grid_slaves(row=1, column=1)[0].winfo_children()[-1]
        C.kv_row(info, 2, "Wajah", "diwajibkan per akun (Settings)", C.CYAN)
        ctk.CTkLabel(inner, text="Kamera hanya menyala bila akun Anda mewajibkan verifikasi wajah, hanya selama "
                     "pemeriksaan, lalu dilepas. Tidak ada frame yang disimpan.", font=C.font(11), text_color=C.MUTED,
                     wraplength=440, justify="left").pack(anchor="w")

    # -- right: branding + credentials ---------------------------------------------------------------
    def _build_right(self) -> None:
        right = ctk.CTkFrame(self, fg_color=C.BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        col = ctk.CTkFrame(right, fg_color="transparent", width=360)
        col.place(relx=0.5, rely=0.5, anchor="center")
        bar = ctk.CTkFrame(col, fg_color=C.CYAN, width=36, height=3, corner_radius=0)
        bar.pack(anchor="w", pady=(0, C.SP_M))
        ctk.CTkLabel(col, text="SENTINEL", font=C.font(38, "bold"), text_color=C.TEXT).pack(anchor="w")
        ctk.CTkLabel(col, text="SECURE COMMUNICATION & DIGITAL EVIDENCE", font=C.mono(10, "bold"),
                     text_color=C.MUTED).pack(anchor="w", pady=(0, 28))
        ctk.CTkLabel(col, text="USERNAME", font=C.mono(10, "bold"), text_color=C.MUTED).pack(anchor="w")
        self.user = ctk.CTkEntry(col, width=360, height=40, fg_color=C.PANEL, border_color=C.BORDER,
                                 corner_radius=C.RADIUS_S, font=C.font(13))
        self.user.pack(pady=(4, C.SP_M))
        ctk.CTkLabel(col, text="PASSWORD", font=C.mono(10, "bold"), text_color=C.MUTED).pack(anchor="w")
        self.pw = ctk.CTkEntry(col, show="•", width=360, height=40, fg_color=C.PANEL, border_color=C.BORDER,
                               corner_radius=C.RADIUS_S, font=C.font(13))
        self.pw.pack(pady=(4, C.SP_L))
        self.btn = ctk.CTkButton(col, text="Login", width=360, height=42, font=C.font(14, "bold"),
                                 corner_radius=C.RADIUS_S, fg_color=C.ACCENT, hover_color=C.ACCENT_HOVER,
                                 text_color=C.ON_ACCENT, text_color_disabled="#C9DDF8", command=self.submit)
        self.btn.pack()
        ctk.CTkButton(col, text="Lupa Password?", width=360, height=30, fg_color="transparent", hover_color=C.PANEL,
                      text_color=C.CYAN, font=C.font(12), command=self.forgot).pack(pady=(C.SP_S, 0))
        self.msg = ctk.CTkLabel(col, text="", font=C.font(12), text_color=C.ERR, wraplength=350, justify="left")
        self.msg.pack(anchor="w", pady=(C.SP_M, 0))

    # -- forgot password ---------------------------------------------------------------------------
    def forgot(self) -> None:
        from sentinel.ui.dialogs import FormDialog, RecoveryCodeDialog
        ctx, app = self.app.ctx, self.app

        def validate(v: dict) -> str | None:
            if not v["u"].strip() or not v["c"].strip() or not v["p"]:
                return "Isi username, kode pemulihan, dan password baru."
            return None if v["p"] == v["p2"] else "Konfirmasi password baru tidak sama."

        def done(new_code: str) -> None:
            self.msg.configure(text="Password diganti. Login dengan password baru.", text_color=C.OK)
            RecoveryCodeDialog(app, new_code, "Kode lama sudah terpakai dan tidak berlaku lagi. Simpan kode BARU ini.",
                               lambda: self.user.focus_set())
        FormDialog(app, "Lupa Password", "Masukkan kode pemulihan akun Anda. Faktor USB/wajah tetap diperlukan saat login.",
                   [("u", "Username", False), ("c", "Kode pemulihan (XXXX-XXXX-XXXX-XXXX)", False),
                    ("p", "Password baru (min. 8 karakter)", True), ("p2", "Ulangi password baru", True)],
                   "Atur Ulang Password", lambda v: ctx.auth.reset_password_with_recovery_code(v["u"], v["c"], v["p"]),
                   done, validate)

    # -- USB indicator -------------------------------------------------------------------------------
    def _poll_usb(self) -> None:
        if not self._alive:
            return

        def show(check: Any) -> None:
            if self._alive:
                ok = check.state == "VALID"
                self.usb_text.configure(text=check.message)
                self.usb_dot.set(C.OK if ok else C.WARN)
        self.app.run(self.app.ctx.usb.check, show, lambda _e: None)
        self.after(3000, self._poll_usb)

    # -- login -----------------------------------------------------------------------------------------
    def submit(self) -> None:
        if self._busy:
            return
        username, password = self.user.get(), self.pw.get()
        if not username or not password:
            self.msg.configure(text="Isi username dan password.", text_color=C.ERR)
            return
        self._busy, self._face_used = True, False
        self.btn.configure(state="disabled", text="Memverifikasi…")
        self.msg.configure(text="", text_color=C.MUTED)
        ctx, q = self.app.ctx, self._events

        def work() -> Any:  # worker thread: only the thread-safe queue is touched from here
            return ctx.auth.login(username, password, on_stage=lambda s: q.put(("stage", s)),
                                  on_stream=lambda st: q.put(("stream", st)))

        def done(user: Any) -> None:
            self._drain()
            delay = 450 if self._face_used else 0  # let VERIFIED be seen
            self.after(delay, lambda: self._finish_ok(user))

        def failed(exc: BaseException) -> None:
            self._drain()
            self._busy = False
            self.camera.detach(self.camera.stage if self.camera.stage in ("FAILED", "CAMERA_UNAVAILABLE") else "IDLE")
            self.btn.configure(state="normal", text="Login")
            self.pw.delete(0, "end")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self._pump()
        self.app.run(work, done, failed)

    def _finish_ok(self, user: Any) -> None:
        if self._alive:
            self.camera.detach()
            self.app.show_main(user)

    def _pump(self) -> None:
        if not self._alive or not self._busy:
            return
        self._drain()
        self.after(40, self._pump)

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "stream":
                    self.camera.attach(payload)
                else:
                    self._face_used = True
                    self.camera.set_stage(payload)
                    label, color, animated = STATUS[payload]
                    self.pill.set(label, color, animated)
        except queue.Empty:
            pass
        if not self._busy and self.camera.stage == "IDLE":
            self.pill.set(*STATUS["IDLE"][:2])

    def destroy(self) -> None:
        self._alive = False
        super().destroy()
