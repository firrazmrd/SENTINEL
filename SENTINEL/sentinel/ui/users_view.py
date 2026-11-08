from __future__ import annotations

import customtkinter as ctk

from sentinel.services.permission_service import ROLE_LABEL, ROLES
from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class UsersView(C.BaseView):
    title = "User Management"

    def build(self) -> None:
        self.table = C.DataTable(self, [("username", "Username", 130), ("name", "Nama", 180), ("role", "Role", 130),
                                        ("status", "Status", 80), ("face", "Wajah", 70), ("last", "Login terakhir", 140)],
                                 height=7, on_select=self._selected)
        self.table.pack(fill="x")
        row = ctk.CTkFrame(self, fg_color="transparent"); row.pack(fill="x", pady=10)
        new = self.card(row); new.pack(side="left", fill="y", padx=(0, 10))
        self.label(new, "Pengguna baru", bold=True).pack(anchor="w", padx=12, pady=(10, 2))
        self.n_user, self.n_name = self.entry(new, "Username"), self.entry(new, "Nama lengkap")
        self.n_pw = self.entry(new, "Password (min. 8)", show="•")
        for e in (self.n_user, self.n_name, self.n_pw):
            e.pack(padx=12, pady=2)
        self.n_role = ctk.StringVar(value=ROLES[1])
        ctk.CTkOptionMenu(new, variable=self.n_role, values=list(ROLES), width=220, fg_color=C.BG, button_color=C.PANEL_2).pack(padx=12, pady=2)
        self.button(new, "Buat Pengguna", self.create).pack(padx=12, pady=(6, 12), fill="x")
        upd = self.card(row); upd.pack(side="left", fill="y", padx=(0, 10))
        self.label(upd, "Ubah pengguna terpilih", bold=True).pack(anchor="w", padx=12, pady=(10, 2))
        self.u_role, self.u_status = ctk.StringVar(value=ROLES[1]), ctk.StringVar(value="ACTIVE")
        ctk.CTkOptionMenu(upd, variable=self.u_role, values=list(ROLES), width=220, fg_color=C.BG, button_color=C.PANEL_2).pack(padx=12, pady=2)
        ctk.CTkOptionMenu(upd, variable=self.u_status, values=["ACTIVE", "DISABLED"], width=220, fg_color=C.BG, button_color=C.PANEL_2).pack(padx=12, pady=2)
        self.u_pw = self.entry(upd, "Reset password (opsional)", show="•"); self.u_pw.pack(padx=12, pady=2)
        self.button(upd, "Simpan Perubahan", self.update).pack(padx=12, pady=(6, 2), fill="x")
        self.button(upd, "Reset Template Wajah", self.reset_face, secondary=True).pack(padx=12, pady=(2, 12), fill="x")
        usb = self.card(row); usb.pack(side="left", fill="both", expand=True)
        self.label(usb, "USB Dongle (satu USB global)", bold=True).pack(anchor="w", padx=12, pady=(10, 2))
        self.usb_info = self.label(usb, "…", muted=True); self.usb_info.pack(anchor="w", padx=12)
        self.drive_var = ctk.StringVar(value="(tidak ada drive)")
        self.drive_menu = ctk.CTkOptionMenu(usb, variable=self.drive_var, values=["(tidak ada drive)"], width=300, fg_color=C.BG, button_color=C.PANEL_2)
        self.drive_menu.pack(anchor="w", padx=12, pady=4)
        for text, cmd, sec in (("Segarkan drive", self.refresh_drives, True), ("Daftarkan / Ganti USB", self.register_usb, False),
                               ("Cabut USB aktif", self.revoke_usb, True)):
            self.button(usb, text, cmd, secondary=sec).pack(anchor="w", padx=12, pady=2)
        self._drives: dict = {}

    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        def work():
            users = ctx.users.list_users(user)
            for u in users:
                u["face"] = "ada" if ctx.biometric.has_template(u["id"]) else "-"
            return users, ctx.usb.active_device(user), ctx.usb.list_drives()
        self.app.run(work, self._loaded, self.fail)

    def _loaded(self, data: tuple) -> None:
        users, dev, drives = data
        self.table.set_rows([{"id": u["id"], "username": u["username"], "name": u["full_name"], "role": ROLE_LABEL[u["role"]],
                              "status": u["status"], "face": u["face"], "last": to_local(u["last_login_at"]), "_u": u} for u in users])
        self.usb_info.configure(text=(f"Aktif: volume {dev['volume_identifier']} ({dev['label'] or 'tanpa label'}), "
                                      f"terdaftar {to_local(dev['registered_at'])}" if dev else "Tidak ada USB aktif."))
        self._drives = {d.display(): d for d in drives}
        names = list(self._drives) or ["(tidak ada drive)"]
        self.drive_menu.configure(values=names); self.drive_var.set(names[0])

    def _selected(self, row: dict | None) -> None:
        if row:
            self.u_role.set(row["_u"]["role"]); self.u_status.set(row["_u"]["status"])

    def create(self) -> None:
        ctx, user, a = self.ctx, self.user, (self.n_user.get(), self.n_name.get(), self.n_pw.get(), self.n_role.get())
        self.app.run(lambda: ctx.users.create_user(user, *a),
                     lambda u: (self.say(f"Pengguna {u['username']} dibuat.", "ok"), self.n_pw.delete(0, "end"), self.refresh()), self.fail)

    def update(self) -> None:
        sel = self.table.selected()
        if not sel:
            return self.say("Pilih pengguna dahulu.", "warn")
        ctx, user, role, status, pw = self.ctx, self.user, self.u_role.get(), self.u_status.get(), self.u_pw.get() or None
        self.app.run(lambda: ctx.users.update_user(user, sel["id"], role=role, status=status, new_password=pw),
                     lambda u: (self.say(f"Pengguna {u['username']} diperbarui.", "ok"), self.u_pw.delete(0, "end"), self.refresh()), self.fail)

    def reset_face(self) -> None:
        sel = self.table.selected()
        if not sel or not self.app.confirm("Reset template wajah", f"Hapus template wajah {sel['username']}?"):
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.biometric.delete_template(user, sel["id"]),
                     lambda _r: (self.say("Template wajah dihapus.", "ok"), self.refresh()), self.fail)

    def refresh_drives(self) -> None:
        self.refresh()

    def register_usb(self) -> None:
        d = self._drives.get(self.drive_var.get())
        if d is None:
            return self.say("Tidak ada drive removable terdeteksi.", "warn")
        if not self.app.confirm("Daftarkan USB", f"USB lama (jika ada) akan dicabut. Tulis marker ke {d.mount}?"):
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.usb.register(user, d), lambda _r: (self.say("USB terdaftar.", "ok"), self.refresh()), self.fail)

    def revoke_usb(self) -> None:
        if not self.app.confirm("Cabut USB", "Tanpa USB aktif, login ditolak sampai USB baru didaftarkan (butuh password Admin). Lanjutkan?"):
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.usb.revoke(user), lambda _r: (self.say("USB dicabut.", "ok"), self.refresh()), self.fail)
