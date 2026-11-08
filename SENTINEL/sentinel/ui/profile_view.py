from __future__ import annotations

from tkinter import messagebox

from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class ProfileView(C.BaseView):
    title = "Profile"

    def build(self) -> None:
        c = self.card(); c.pack(fill="x")
        self.label(c, f"{self.user.full_name}  (@{self.user.username})", bold=True, size=15).pack(anchor="w", padx=14, pady=(12, 0))
        self.label(c, f"Role: {self.user.role_label}", muted=True).pack(anchor="w", padx=14, pady=(0, 10))
        f = self.card(); f.pack(fill="x", pady=12)
        self.label(f, "Face Verification (1:1, ArcFace + OpenCV detector)", bold=True).pack(anchor="w", padx=14, pady=(12, 2))
        self.info = self.label(f, "…", muted=True); self.info.pack(anchor="w", padx=14)
        self.label(f, "Hanya embedding terenkripsi yang disimpan — foto wajah tidak disimpan. Tidak ada liveness detection.",
                   muted=True, size=11).pack(anchor="w", padx=14, pady=(2, 6))
        row = C.ctk.CTkFrame(f, fg_color="transparent"); row.pack(anchor="w", padx=14, pady=(4, 14))
        self.button(row, "Daftarkan / Perbarui Wajah", self.enroll).pack(side="left", padx=(0, 8))
        self.button(row, "Hapus Template Saya", self.delete, secondary=True).pack(side="left")

    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.biometric.my_template_info(user), self._show, self.fail)

    def _show(self, info: dict | None) -> None:
        self.info.configure(text="Belum ada template wajah." if info is None else
                            f"Template aktif: {info['model_name']} / {info['detector_backend']}, dim {info['embedding_dim']}, "
                            f"threshold {info['threshold']:.3f}, diperbarui {to_local(info['updated_at'])}")

    def enroll(self) -> None:
        if not self.app.confirm("Daftarkan wajah", "Kamera akan dinyalakan sebentar dan mengambil 3 frame. "
                                "Pastikan hanya Anda yang terlihat. Lanjutkan?"):
            return
        ctx, user = self.ctx, self.user
        self.say("Menghadap kamera… memproses embedding (pertama kali dapat lebih lama).")
        self.app.run(lambda: ctx.biometric.enroll(user), lambda _r: (self.say("Template wajah tersimpan terenkripsi.", "ok"), self.refresh()), self.fail)

    def delete(self) -> None:
        if not messagebox.askokcancel("Hapus template", "Hapus template wajah Anda? Login dengan Face Verification ON akan gagal sampai didaftarkan ulang."):
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.biometric.delete_template(user), lambda _r: (self.say("Template dihapus.", "ok"), self.refresh()), self.fail)
