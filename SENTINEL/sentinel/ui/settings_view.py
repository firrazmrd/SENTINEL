"""Settings: login factors (face, USB dongle, required-at-login switches) and recovery (password, recovery code).
All buttons call real services; nothing here touches SQL or crypto."""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.ui.dialogs import FaceEnrollDialog, FormDialog, RecoveryCodeDialog

NO_DRIVE = "(tidak ada USB)"


class SettingsView(C.BaseView):
    title = "Settings"

    def build(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        wrap = ctk.CTkFrame(scroll, fg_color=C.PANEL, border_width=1, border_color=C.BORDER, corner_radius=12)
        wrap.pack(fill="x", padx=2, pady=2)
        self._saved: dict | None = None
        self._drives: dict[str, Any] = {}

        # ---- Faktor Autentikasi -------------------------------------------------
        self._title(wrap, "Faktor Autentikasi", first=True)
        g = self._group(wrap)
        self.face_status = self._stat_label(g, "Wajah: …", 0)
        self.btn_face = self._btn(g, "Daftarkan / Perbarui Wajah (Webcam)", self.enroll_face)
        self.btn_face.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(2, 8))
        self.usb_status = self._stat_label(g, "USB dongle: …", 2)
        self.drive_var = ctk.StringVar(value=NO_DRIVE)
        self.drive_menu = ctk.CTkOptionMenu(g, variable=self.drive_var, values=[NO_DRIVE], height=36, anchor="w",
                                            font=C.font(12), dropdown_font=C.font(12), fg_color=C.PANEL_2,
                                            button_color=C.PANEL_2, button_hover_color=C.HOVER_2,
                                            text_color=C.TEXT, dropdown_fg_color=C.PANEL_2, corner_radius=8)
        self.drive_menu.grid(row=3, column=0, sticky="ew", padx=(10, 4), pady=(2, 8))
        self.btn_search = self._btn(g, "Cari USB", self.search_usb, secondary=True)
        self.btn_search.grid(row=3, column=1, sticky="ew", padx=4, pady=(2, 8))
        self.btn_usb = self._btn(g, "Buat USB Dongle", self.create_usb)
        self.btn_usb.grid(row=3, column=2, sticky="ew", padx=(4, 10), pady=(2, 8))
        self.cb_face = self._check(g, "Wajibkan verifikasi wajah saat login", 4)
        self.cb_usb = self._check(g, "Wajibkan USB dongle saat login", 5)
        self.btn_apply = self._btn(g, "Terapkan", self.apply)
        self.btn_apply.grid(row=6, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 10))
        for col in range(3):
            g.grid_columnconfigure(col, weight=1, uniform="usbcols")

        # ---- Akun Pemulihan -----------------------------------------------------
        self._title(wrap, "Akun Pemulihan")
        r = self._group(wrap)
        self.rec_status = self._stat_label(r, "Kode pemulihan: …", 0)
        self._btn(r, "Ganti Password", self.change_password).grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))
        self._btn(r, "Buat Ulang Kode Pemulihan", self.regenerate_code, secondary=True
                  ).grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        r.grid_columnconfigure(0, weight=1)

    # -- widget helpers ------------------------------------------------------------
    def _title(self, parent: Any, text: str, first: bool = False) -> None:
        ctk.CTkLabel(parent, text=text, font=C.font(14, "bold"), text_color=C.TEXT, anchor="w"
                     ).pack(fill="x", padx=16, pady=(14 if first else 8, 6))

    def _group(self, parent: Any) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color=C.PANEL, border_width=1, border_color=C.BORDER, corner_radius=10)
        f.pack(fill="x", padx=14, pady=(0, 6))
        return f

    def _stat_label(self, parent: Any, text: str, row: int) -> ctk.CTkLabel:
        lb = ctk.CTkLabel(parent, text=text, font=C.font(12), text_color=C.TEXT, anchor="w")
        lb.grid(row=row, column=0, columnspan=3, sticky="ew", padx=12, pady=(10, 4))
        return lb

    def _btn(self, parent: Any, text: str, cmd: Any, secondary: bool = False) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, command=cmd, height=36, corner_radius=8, font=C.font(12, "bold"),
                             fg_color=C.PANEL_2 if secondary else C.ACCENT,
                             hover_color=C.HOVER_2 if secondary else C.ACCENT_HOVER, text_color=C.TEXT)

    def _check(self, parent: Any, text: str, row: int) -> ctk.CTkCheckBox:
        cb = ctk.CTkCheckBox(parent, text=text, font=C.font(12), text_color=C.TEXT, fg_color=C.ACCENT,
                             hover_color=C.ACCENT_HOVER, border_color="#5b6b8a", checkbox_width=18, checkbox_height=18)
        cb.grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=4)
        return cb

    # -- data --------------------------------------------------------------------------
    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: (ctx.account.overview(user), ctx.usb.list_drives(), ctx.usb.check()), self._loaded, self.fail)

    def _loaded(self, data: tuple) -> None:
        ov, drives, check = data
        self._saved = ov
        self.face_status.configure(text="Wajah: terdaftar" if ov["has_face"] else "Wajah: belum terdaftar")
        self.usb_status.configure(text="USB dongle: terdaftar" if ov["usb_registered"] else "USB dongle: belum terdaftar")
        self.rec_status.configure(text="Kode pemulihan: sudah dibuat" if ov["has_recovery_code"]
                                  else "Kode pemulihan: belum dibuat")
        (self.cb_face.select if ov["require_face"] else self.cb_face.deselect)()
        (self.cb_usb.select if ov["require_usb"] else self.cb_usb.deselect)()
        self._set_drives(drives)
        can_usb = ov["can_manage_usb"]
        self.btn_usb.configure(state="normal" if can_usb else "disabled")
        if ov["usb_registered"] and check.state != "VALID":
            self.say(f"USB: {check.message}", "warn")
        elif not can_usb:
            self.say("USB dongle bersifat global; hanya Admin yang dapat membuat/mengganti USB dongle.", "info")

    def _set_drives(self, drives: list) -> None:
        self._drives = {d.mount: d for d in drives}
        names = list(self._drives) or [NO_DRIVE]
        keep = self.drive_var.get()
        self.drive_menu.configure(values=names)
        self.drive_var.set(keep if keep in names else names[0])

    # -- faktor autentikasi ----------------------------------------------------------------
    def enroll_face(self) -> None:
        FaceEnrollDialog(self.app, lambda: (self.say("Template wajah tersimpan terenkripsi.", "ok"), self.refresh()))

    def search_usb(self) -> None:
        ctx = self.ctx

        def done(drives: list) -> None:
            self._set_drives(drives)
            self.say(f"{len(drives)} USB ditemukan." if drives else
                     "USB tidak ditemukan. Pasang flash drive lalu klik Cari USB.", "ok" if drives else "warn")
        self.app.run(ctx.usb.list_drives, done, self.fail)

    def create_usb(self) -> None:
        drive = self._drives.get(self.drive_var.get())
        if drive is None:
            return self.say("USB tidak ditemukan. Pasang flash drive lalu klik Cari USB.", "warn")
        if not self.app.confirm("Buat USB Dongle",
                                f"Marker autentikasi akan ditulis ke {drive.mount}. USB dongle lama (jika ada) dicabut, "
                                "dan semua akun yang mewajibkan USB harus memakai USB baru. Lanjutkan?"):
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.usb.register(user, drive),
                     lambda _r: (self.say("USB dongle berhasil dibuat.", "ok"), self.refresh()), self.fail)

    def apply(self) -> None:
        s = self._saved
        if s is None:
            return
        face, usb = bool(self.cb_face.get()), bool(self.cb_usb.get())
        if (face, usb) == (s["require_face"], s["require_usb"]):
            return self.say("Tidak ada perubahan untuk diterapkan.", "warn")
        if not face and not usb and not self.app.confirm(
                "Terapkan", "Tanpa verifikasi wajah dan USB, login hanya memakai password. Lanjutkan?"):
            return
        ctx, user = self.ctx, self.user

        def done(_r: Any) -> None:
            self.say("Pengaturan autentikasi disimpan dan berlaku mulai login berikutnya.", "ok")
            self.refresh()

        def work(pw: str | None) -> Any:
            return ctx.account.apply_auth_requirements(user, require_face=face, require_usb=usb, current_password=pw)

        if (s["require_face"] and not face) or (s["require_usb"] and not usb):
            FormDialog(self.app, "Konfirmasi Password", "Menonaktifkan faktor autentikasi memerlukan password Anda.",
                       [("pw", "Password saat ini", True)], "Konfirmasi dan Terapkan",
                       lambda v: work(v["pw"]), done)
        else:
            self.app.run(lambda: work(None), done, self._apply_failed)

    def _apply_failed(self, exc: BaseException) -> None:
        self.fail(exc)
        self.refresh()  # put the checkboxes back to what is actually saved

    # -- akun pemulihan ----------------------------------------------------------------------
    def change_password(self) -> None:
        ctx, user = self.ctx, self.user

        def validate(v: dict) -> str | None:
            if not v["cur"] or not v["new"]:
                return "Isi password saat ini dan password baru."
            return None if v["new"] == v["new2"] else "Konfirmasi password baru tidak sama."
        FormDialog(self.app, "Ganti Password", "Password baru minimal 8 karakter dan disimpan sebagai hash Argon2id.",
                   [("cur", "Password saat ini", True), ("new", "Password baru", True), ("new2", "Ulangi password baru", True)],
                   "Simpan Password", lambda v: ctx.account.change_password(user, v["cur"], v["new"]),
                   lambda _r: self.say("Password berhasil diganti.", "ok"), validate)

    def regenerate_code(self) -> None:
        if not self.app.confirm("Buat Ulang Kode Pemulihan",
                                "Kode pemulihan lama akan langsung dinonaktifkan dan diganti kode baru. Lanjutkan?"):
            return
        ctx, user, app = self.ctx, self.user, self.app

        def shown(code: str) -> None:
            self.refresh()
            RecoveryCodeDialog(app, code, "Kode ini dipakai pada Lupa Password di halaman login.", self.refresh)
        FormDialog(app, "Konfirmasi Password", "Masukkan password Anda untuk membuat kode pemulihan baru.",
                   [("pw", "Password saat ini", True)], "Buat Kode Baru",
                   lambda v: ctx.account.regenerate_recovery_code(user, v["pw"]), shown)
