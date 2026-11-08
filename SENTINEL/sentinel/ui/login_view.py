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
        self.face = ctk.CTkSwitch(box, text="Face Verification", progress_color=C.ACCENT, font=C.font(12))
        self.face.select()  # default ON
        self.face.pack(pady=(6, 0))
        self.face_note = ctk.CTkLabel(box, text="", font=C.font(10), text_color=C.WARN, wraplength=320)
        self.face_note.pack()
        self.face.configure(command=self._face_toggled)
        self.btn = ctk.CTkButton(box, text="Login", width=320, height=40, font=C.font(14, "bold"), fg_color=C.ACCENT,
                                 hover_color=C.ACCENT_HOVER, text_color="#04211f", command=self.submit)
        self.btn.pack(pady=(12, 6))
        self.msg = ctk.CTkLabel(box, text="", font=C.font(12), text_color=C.ERR, wraplength=340, justify="center")
        self.msg.pack(padx=30, pady=(0, 24))
        self.user.bind("<Return>", lambda _e: self.submit())
        self.pw.bind("<Return>", lambda _e: self.submit())
        self.user.focus_set()
        self._poll_usb()

    def _face_toggled(self) -> None:
        self.face_note.configure(text="" if self.face.get() else
                                 "Hanya verifikasi wajah yang dilewati. Password dan USB tetap wajib. "
                                 "Ini kemudahan khusus prototipe akademik.")

    def _poll_usb(self) -> None:
        if not self._alive:
            return

        def show(check: Any) -> None:
            if self._alive:
                self.usb.configure(text=check.message, text_color=C.OK if check.state == "VALID" else C.WARN)
        self.app.run(self.app.ctx.usb.check, show, lambda _e: None)
        self.after(3000, self._poll_usb)

    def submit(self) -> None:
        username, password, bio = self.user.get(), self.pw.get(), bool(self.face.get())
        if not username or not password:
            self.msg.configure(text="Isi username dan password.", text_color=C.ERR)
            return
        self.btn.configure(state="disabled")
        self.msg.configure(text="Memverifikasi… (hadap kamera bila Face Verification ON)" if bio else "Memverifikasi…",
                           text_color=C.MUTED)
        ctx = self.app.ctx

        def done(user: Any) -> None:
            self.app.show_main(user)

        def failed(exc: BaseException) -> None:
            self.btn.configure(state="normal")
            self.pw.delete(0, "end")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self.app.run(lambda: ctx.auth.login(username, password, bio), done, failed)

    def destroy(self) -> None:
        self._alive = False
        super().destroy()
