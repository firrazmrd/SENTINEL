from __future__ import annotations

from typing import Any

import customtkinter as ctk

from sentinel.ui import common as C


class LoginView(ctk.CTkFrame):
    def __init__(self, app: Any) -> None:
        super().__init__(app, fg_color=C.BG)
        self.app, self._alive = app, True
        box = ctk.CTkFrame(self, fg_color=C.PANEL, corner_radius=14, width=430)
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="SENTINEL", font=C.font(32, "bold"), text_color=C.ACCENT).pack(padx=50, pady=(30, 0))
        ctk.CTkLabel(box, text="Secure Communication & Digital Evidence Management", font=C.font(11),
                     text_color=C.MUTED).pack(pady=(0, 18))
        self.user = ctk.CTkEntry(box, placeholder_text="Username", width=320, height=38, fg_color=C.BG, border_color=C.PANEL_2)
        self.user.pack(pady=5)
        self.pw = ctk.CTkEntry(box, placeholder_text="Password", show="•", width=320, height=38, fg_color=C.BG,
                               border_color=C.PANEL_2)
        self.pw.pack(pady=5)
        self.usb = ctk.CTkLabel(box, text="USB: memeriksa…", font=C.font(12), text_color=C.MUTED)
        self.usb.pack(pady=(10, 2))
        self.btn = ctk.CTkButton(box, text="Login", width=320, height=40, font=C.font(14, "bold"), fg_color=C.ACCENT,
                                 hover_color=C.ACCENT_HOVER, text_color="#04211f", command=self.submit)
        self.btn.pack(pady=(12, 2))
        ctk.CTkButton(box, text="Lupa Password?", width=320, height=28, fg_color="transparent", hover_color=C.PANEL_2,
                      text_color=C.MUTED, font=C.font(12), command=self.forgot).pack(pady=(0, 4))
        self.msg = ctk.CTkLabel(box, text="", font=C.font(12), text_color=C.ERR, wraplength=340, justify="center")
        self.msg.pack(padx=30, pady=(0, 24))
        self.user.bind("<Return>", lambda _e: self.submit())
        self.pw.bind("<Return>", lambda _e: self.submit())
        self.user.focus_set()
        self._poll_usb()

    def forgot(self) -> None:
        from sentinel.ui.dialogs import FormDialog, RecoveryCodeDialog
        ctx, app = self.app.ctx, self.app

        def validate(v: dict) -> str | None:
            if not v["u"].strip() or not v["c"].strip() or not v["p"]:
                return "Isi username, kode pemulihan, dan password baru."
            return None if v["p"] == v["p2"] else "Konfirmasi password baru tidak sama."

        def done(new_code: str) -> None:
            self.msg.configure(text="Password diganti. Login dengan password baru.", text_color=C.OK)
            RecoveryCodeDialog(app, new_code, "Kode lama sudah terpakai dan tidak berlaku lagi. Simpan kode BARU ini.")
        FormDialog(app, "Lupa Password", "Masukkan kode pemulihan akun Anda. Faktor USB/wajah tetap diperlukan saat login.",
                   [("u", "Username", False), ("c", "Kode pemulihan (XXXX-XXXX-XXXX-XXXX)", False),
                    ("p", "Password baru (min. 8 karakter)", True), ("p2", "Ulangi password baru", True)],
                   "Atur Ulang Password", lambda v: ctx.auth.reset_password_with_recovery_code(v["u"], v["c"], v["p"]),
                   done, validate)

    def _poll_usb(self) -> None:
        if not self._alive:
            return

        def show(check: Any) -> None:
            if self._alive:
                self.usb.configure(text=check.message, text_color=C.OK if check.state == "VALID" else C.WARN)
        self.app.run(self.app.ctx.usb.check, show, lambda _e: None)
        self.after(3000, self._poll_usb)

    def submit(self) -> None:
        username, password = self.user.get(), self.pw.get()
        if not username or not password:
            self.msg.configure(text="Isi username dan password.", text_color=C.ERR)
            return
        self.btn.configure(state="disabled")
        self.msg.configure(text="Memverifikasi… (hadap kamera bila verifikasi wajah diwajibkan akun ini)",
                           text_color=C.MUTED)
        ctx = self.app.ctx

        def done(user: Any) -> None:
            self.app.show_main(user)

        def failed(exc: BaseException) -> None:
            self.btn.configure(state="normal")
            self.pw.delete(0, "end")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self.app.run(lambda: ctx.auth.login(username, password), done, failed)

    def destroy(self) -> None:
        self._alive = False
        super().destroy()
