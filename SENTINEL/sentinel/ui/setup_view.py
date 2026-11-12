from __future__ import annotations

from typing import Any

import customtkinter as ctk

from sentinel import bootstrap
from sentinel.ui import common as C


class StartupErrorView(ctk.CTkFrame):
    def __init__(self, app: Any, message: str) -> None:
        super().__init__(app, fg_color=C.BG)
        box = ctk.CTkFrame(self, fg_color=C.PANEL, corner_radius=14)
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="SENTINEL tidak dapat dimulai", font=C.font(20, "bold"), text_color=C.ERR).pack(padx=40, pady=(28, 8))
        ctk.CTkLabel(box, text=message, font=C.font(13), text_color=C.TEXT, wraplength=520, justify="left").pack(padx=40, pady=8)
        ctk.CTkButton(box, text="Keluar", command=app.on_close, fg_color=C.PANEL_2).pack(pady=(10, 28))


class SetupView(ctk.CTkFrame):
    """mode='first_run': create Admin then register the demo USB. mode='usb_recovery': no USB is active."""

    def __init__(self, app: Any, mode: str) -> None:
        super().__init__(app, fg_color=C.BG)
        self.app, self.mode, self.admin = app, mode, None
        self.box = ctk.CTkFrame(self, fg_color=C.PANEL, corner_radius=14)
        self.box.place(relx=0.5, rely=0.5, anchor="center")
        self.msg: ctk.CTkLabel
        (self._step_admin if mode == "first_run" else self._step_usb)()

    def _clear(self, title: str, sub: str) -> None:
        for w in self.box.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.box, text=title, font=C.font(22, "bold"), text_color=C.ACCENT).pack(padx=50, pady=(28, 2))
        ctk.CTkLabel(self.box, text=sub, font=C.font(11), text_color=C.MUTED, wraplength=380).pack(pady=(0, 14))

    def _entry(self, ph: str, show: str | None = None) -> ctk.CTkEntry:
        e = ctk.CTkEntry(self.box, placeholder_text=ph, show=show, width=340, height=36, fg_color=C.BG, border_color=C.PANEL_2)
        e.pack(pady=4)
        return e

    def _footer(self, text: str, cmd: Any) -> None:
        self.btn = ctk.CTkButton(self.box, text=text, width=340, height=40, command=cmd, fg_color=C.ACCENT,
                                 hover_color=C.ACCENT_HOVER, text_color="#04211f", font=C.font(13, "bold"))
        self.btn.pack(pady=(14, 6))
        self.msg = ctk.CTkLabel(self.box, text="", font=C.font(12), text_color=C.ERR, wraplength=360)
        self.msg.pack(padx=24, pady=(0, 24))

    # -- step 1 ----------------------------------------------------------------
    def _step_admin(self) -> None:
        self._clear("Setup Awal SENTINEL", "Langkah 1/2 — buat akun Admin pertama. Key enkripsi dibuat acak dan "
                    "disimpan di Windows Credential Manager (bukan di file).")
        self.f_user, self.f_name = self._entry("Username Admin"), self._entry("Nama lengkap")
        self.f_pw, self.f_pw2 = self._entry("Password (min. 8 karakter)", "•"), self._entry("Ulangi password", "•")
        self._footer("Buat Admin & Database Terenkripsi", self._create_admin)

    def _create_admin(self) -> None:
        if self.f_pw.get() != self.f_pw2.get():
            self.msg.configure(text="Konfirmasi password tidak sama.")
            return
        self.btn.configure(state="disabled")
        self.msg.configure(text="Membuat database terenkripsi…", text_color=C.MUTED)
        args = (self.app.settings, self.f_user.get(), self.f_name.get(), self.f_pw.get(), self.app._devices)
        password = args[3]

        def work() -> tuple:
            ctx, admin = bootstrap.first_run(*args)
            return ctx, admin, ctx.account.regenerate_recovery_code(admin, password)  # first recovery code

        def ok(res: Any) -> None:
            self.app.ctx, self.admin, self.recovery_code = res
            self._step_code()

        def err(exc: BaseException) -> None:
            self.btn.configure(state="normal")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self.app.run(work, ok, err)

    # -- step 1b: recovery code ----------------------------------------------------
    def _step_code(self) -> None:
        self._clear("Kode Pemulihan Admin", "Simpan kode ini sekarang. Kode hanya ditampilkan sekali dan dipakai pada "
                    "Lupa Password di halaman login. Kode bisa dibuat ulang di Settings.")
        ctk.CTkLabel(self.box, text=self.recovery_code, width=340, height=56, corner_radius=8, fg_color=C.PANEL_2,
                     text_color=C.TEXT, font=ctk.CTkFont(family="Consolas", size=22, weight="bold")).pack(pady=6)
        self.copy_btn = ctk.CTkButton(self.box, text="Salin Kode", width=340, fg_color=C.PANEL_2, hover_color="#22324f",
                                      command=self._copy_code)
        self.copy_btn.pack(pady=4)
        self._footer("Saya sudah menyimpan kode ini", self._continue_to_usb)

    def _copy_code(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.recovery_code)
        self.copy_btn.configure(text="Tersalin ✓")

    def _continue_to_usb(self) -> None:
        self._step_usb()

    # -- step 2 ----------------------------------------------------------------
    def _step_usb(self) -> None:
        recovery = self.admin is None
        self._clear("Registrasi USB Dongle" if recovery else "Setup Awal SENTINEL",
                    "Belum ada USB aktif. Masukkan kredensial Admin untuk mendaftarkan flash drive." if recovery else
                    "Langkah 2/2 — pasang satu flash drive demo. SENTINEL menulis file marker .sentinel-token "
                    "(faktor kepemilikan sederhana; flash drive biasa dapat dikloning).")
        if recovery:
            self.f_user, self.f_pw = self._entry("Username Admin"), self._entry("Password Admin", "•")
        self.drive_var = ctk.StringVar(value="(tidak ada drive)")
        self.menu = ctk.CTkOptionMenu(self.box, variable=self.drive_var, values=["(tidak ada drive)"], width=340,
                                      fg_color=C.BG, button_color=C.PANEL_2)
        self.menu.pack(pady=6)
        ctk.CTkButton(self.box, text="Segarkan daftar drive", width=340, fg_color=C.PANEL_2, hover_color="#22324f",
                      command=self._refresh_drives).pack()
        self._footer("Daftarkan USB", self._do_register)
        self._drives: dict[str, Any] = {}
        self._refresh_drives()

    def _refresh_drives(self) -> None:
        def ok(drives: list) -> None:
            self._drives = {d.display(): d for d in drives}
            names = list(self._drives) or ["(tidak ada drive removable terdeteksi)"]
            self.menu.configure(values=names)
            self.drive_var.set(names[0])
        self.app.run(self.app.ctx.usb.list_drives, ok)

    def _do_register(self) -> None:
        drive = self._drives.get(self.drive_var.get())
        if drive is None:
            self.msg.configure(text="Pasang flash drive lalu segarkan daftar.", text_color=C.ERR)
            return
        self.btn.configure(state="disabled")
        ctx, admin = self.app.ctx, self.admin
        creds = (self.f_user.get(), self.f_pw.get()) if admin is None else None

        def work() -> None:
            actor = admin or ctx.auth.verify_admin_credentials(*creds)
            ctx.usb.register_when_none_active(actor, drive)

        def err(exc: BaseException) -> None:
            self.btn.configure(state="normal")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self.app.run(work, lambda _r: self.app.show_login(), err)
