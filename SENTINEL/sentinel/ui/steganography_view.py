from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from sentinel.ui import common as C


class SteganographyView(C.BaseView):
    title = "Steganography (LSB PNG)"

    def build(self) -> None:
        self.src: Path | None = None
        self.stego_file: Path | None = None
        wrap = ctk.CTkFrame(self, fg_color="transparent"); wrap.pack(fill="both", expand=True)
        emb = self.card(wrap); emb.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.label(emb, "Sisipkan pesan", bold=True, size=14).pack(anchor="w", padx=12, pady=(10, 4))
        self.src_lbl = self.label(emb, "Belum ada PNG dipilih", muted=True); self.src_lbl.pack(anchor="w", padx=12)
        self.button(emb, "Pilih PNG pembawa…", self.pick_src, secondary=True).pack(anchor="w", padx=12, pady=6)
        self.msg_box = self.textbox(emb, 160); self.msg_box.pack(fill="x", padx=12, pady=6)
        self.button(emb, "Enkripsi, Sisipkan & Simpan Sebagai…", self.embed).pack(anchor="w", padx=12, pady=(4, 12))
        ext = self.card(wrap); ext.pack(side="left", fill="both", expand=True)
        self.label(ext, "Ekstrak pesan", bold=True, size=14).pack(anchor="w", padx=12, pady=(10, 4))
        self.ext_lbl = self.label(ext, "Belum ada PNG dipilih", muted=True); self.ext_lbl.pack(anchor="w", padx=12)
        self.button(ext, "Pilih PNG stego…", self.pick_ext, secondary=True).pack(anchor="w", padx=12, pady=6)
        self.button(ext, "Ekstrak & Dekripsi", self.extract).pack(anchor="w", padx=12, pady=4)
        self.out_box = self.textbox(ext, 160); self.out_box.pack(fill="x", padx=12, pady=10)
        self.label(self, "Catatan: LSB hanya menyamarkan keberadaan data dan dapat dideteksi analisis statistik. "
                   "Kerahasiaan berasal dari enkripsi AES-256-GCM pada payload.", muted=True, size=11).pack(anchor="w", pady=(10, 0))

    def pick_src(self) -> None:
        p = filedialog.askopenfilename(title="Pilih gambar PNG", filetypes=[("PNG", "*.png")])
        if not p:
            return
        self.src = Path(p)
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.stego.capacity(user, self.src),
                     lambda cap: self.src_lbl.configure(text=f"{self.src.name} — kapasitas teks ± {cap} byte"), self.fail)

    def embed(self) -> None:
        if self.src is None:
            return self.say("Pilih PNG pembawa dahulu.", "warn")
        out = filedialog.asksaveasfilename(title="Simpan PNG stego", defaultextension=".png", filetypes=[("PNG", "*.png")],
                                           initialfile=f"{self.src.stem}_stego.png")
        if not out:
            return
        ctx, user, text = self.ctx, self.user, self.get_text(self.msg_box)
        self.app.run(lambda: ctx.stego.embed(user, self.src, text, Path(out), overwrite=True),
                     lambda r: self.say(f"Tersimpan: {r.output_path} ({r.payload_bytes} byte payload dari kapasitas {r.capacity_bytes}).", "ok"),
                     self.fail)

    def pick_ext(self) -> None:
        p = filedialog.askopenfilename(title="Pilih PNG stego", filetypes=[("PNG", "*.png")])
        if p:
            self.stego_file = Path(p)
            self.ext_lbl.configure(text=self.stego_file.name)

    def extract(self) -> None:
        if self.stego_file is None:
            return self.say("Pilih PNG stego dahulu.", "warn")
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.stego.extract(user, self.stego_file),
                     lambda t: (self.set_text(self.out_box, t), self.say("Payload berhasil diautentikasi dan didekripsi.", "ok")),
                     lambda e: (self.set_text(self.out_box, ""), self.fail(e)))
