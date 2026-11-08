from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from sentinel.services.permission_service import Action as A
from sentinel.services.permission_service import PermissionService as P
from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local

STATUS_HELP = {
    "VALID": ("VALID — tag autentikasi dan hash plaintext cocok.", "ok"),
    "CIPHERTEXT_OK": ("Hash ciphertext cocok dengan catatan saat intake (tanpa dekripsi).", "ok"),
    "CIPHERTEXT_MODIFIED": ("CIPHERTEXT_MODIFIED — file terenkripsi berubah atau hilang!", "error"),
    "PLAINTEXT_HASH_MISMATCH": ("PLAINTEXT_HASH_MISMATCH — hash plaintext tidak cocok.", "error"),
    "DECRYPTION_FAILED": ("DECRYPTION_FAILED — autentikasi ChaCha20-Poly1305 gagal.", "error"),
}


class EvidenceView(C.BaseView):
    title = "Evidence"

    def build(self) -> None:
        r = self.user.role
        self.perm = {a: P.role_allows(r, a) for a in (A.UPLOAD_EVIDENCE, A.VERIFY_PLAINTEXT, A.DECRYPT_EVIDENCE, A.ADD_NOTE)}
        bar = ctk.CTkFrame(self, fg_color="transparent"); bar.pack(fill="x", pady=(0, 8))
        self.label(bar, "Kasus:", muted=True).pack(side="left")
        self.case_var = ctk.StringVar(value="")
        self.case_menu = ctk.CTkOptionMenu(bar, variable=self.case_var, values=["(tidak ada kasus)"], width=360,
                                           fg_color=C.BG, button_color=C.PANEL_2, command=lambda _v: self.load_evidence())
        self.case_menu.pack(side="left", padx=8)
        if self.perm[A.UPLOAD_EVIDENCE]:
            self.button(bar, "Upload Bukti…", self.upload).pack(side="left", padx=4)
        self.table = C.DataTable(self, [("code", "Kode", 130), ("name", "File asli", 200), ("size", "Ukuran", 80),
                                        ("status", "Status integritas", 170), ("sha", "SHA-256 sumber", 120),
                                        ("by", "Diunggah oleh", 130), ("at", "Waktu", 130)], height=7, on_select=self._selected)
        self.table.pack(fill="x")
        actions = ctk.CTkFrame(self, fg_color="transparent"); actions.pack(fill="x", pady=10)
        self.button(actions, "Verifikasi Hash Ciphertext", self.verify_ct, secondary=True).pack(side="left", padx=(0, 6))
        if self.perm[A.VERIFY_PLAINTEXT]:
            self.button(actions, "Dekripsi & Verifikasi Hash", self.verify_pt, secondary=True).pack(side="left", padx=6)
        if self.perm[A.DECRYPT_EVIDENCE]:
            self.button(actions, "Ekspor Plaintext…", self.export).pack(side="left", padx=6)
        self.detail = self.textbox(self, 120); self.detail.pack(fill="x")
        self.set_text(self.detail, "Pilih bukti untuk melihat detail.")
        if self.perm[A.ADD_NOTE]:
            row = ctk.CTkFrame(self, fg_color="transparent"); row.pack(fill="x", pady=8)
            self.note = self.entry(row, "Catatan pemeriksaan singkat", width=560); self.note.pack(side="left")
            self.button(row, "Simpan Catatan", self.save_note, secondary=True).pack(side="left", padx=8)
        self._cases: dict[str, str] = {}

    # -- loading ---------------------------------------------------------------
    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.cases.list_cases(user), self._cases_loaded, self.fail)

    def _cases_loaded(self, cases: list) -> None:
        self._cases = {f"{c['case_number']} — {c['title']}": c["id"] for c in cases}
        names = list(self._cases) or ["(tidak ada kasus)"]
        self.case_menu.configure(values=names)
        if self.case_var.get() not in self._cases:
            self.case_var.set(names[0])
        self.load_evidence()

    def _case_id(self) -> str | None:
        return self._cases.get(self.case_var.get())

    def load_evidence(self) -> None:
        cid = self._case_id()
        if not cid:
            return self.table.set_rows([])
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.evidence.list_for_case(user, cid), self._show, self.fail)

    def _show(self, items: list) -> None:
        self.table.set_rows([{"id": e["id"], "code": e["evidence_code"], "name": e["original_filename"],
                              "size": C.human_size(e["original_size"]), "status": e["status"],
                              "sha": C.short(e["original_sha256"], 14), "by": e["uploader_name"],
                              "at": to_local(e["created_at"]), "_e": e} for e in items])

    def _selected(self, row: dict | None) -> None:
        if not row:
            return
        e = row["_e"]
        self.set_text(self.detail,
                      f"Kode: {e['evidence_code']}   |   Algoritma: {e['encryption_algorithm']}\n"
                      f"File asli: {e['original_filename']} ({C.human_size(e['original_size'])}, {e['mime_type'] or 'tipe tidak diketahui'})\n"
                      f"SHA-256 sumber    : {e['original_sha256']}\nSHA-256 ciphertext: {e['encrypted_sha256']}\n"
                      f"Catatan analyst   : {e['analyst_note'] or '-'}")

    def _need_selection(self) -> dict | None:
        row = self.table.selected()
        if not row:
            self.say("Pilih bukti pada tabel terlebih dahulu.", "warn")
        return row

    # -- actions ---------------------------------------------------------------
    def upload(self) -> None:
        cid = self._case_id()
        if not cid:
            return self.say("Pilih kasus terlebih dahulu.", "warn")
        path = filedialog.askopenfilename(title="Pilih file bukti (maks. 100 MB)")
        if not path:
            return
        ctx, user = self.ctx, self.user
        self.say("Menghitung hash dan mengenkripsi…")
        self.app.run(lambda: ctx.evidence.upload(user, cid, Path(path)),
                     lambda e: (self.say(f"Bukti {e['evidence_code']} tersimpan terenkripsi. SHA-256: {e['original_sha256']}", "ok"),
                                self.load_evidence()), self.fail)

    def _report(self, res) -> None:
        text, level = STATUS_HELP.get(res.status, (res.status, "info"))
        self.say(f"{text} {res.detail if level == 'error' else ''}", level)
        self.load_evidence()

    def verify_ct(self) -> None:
        if row := self._need_selection():
            ctx, user = self.ctx, self.user
            self.app.run(lambda: ctx.evidence.verify_ciphertext(user, row["id"]), self._report, self.fail)

    def verify_pt(self) -> None:
        if row := self._need_selection():
            ctx, user = self.ctx, self.user
            self.say("Mendekripsi di memori…")
            self.app.run(lambda: ctx.evidence.verify_plaintext(user, row["id"]), self._report, self.fail)

    def export(self) -> None:
        row = self._need_selection()
        if not row:
            return
        if not self.app.confirm("Ekspor plaintext", "File hasil ekspor TIDAK lagi dilindungi enkripsi SENTINEL. Lanjutkan?"):
            return
        dest = filedialog.asksaveasfilename(title="Simpan hasil dekripsi", initialfile=row["_e"]["original_filename"])
        if not dest:
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.evidence.export(user, row["id"], Path(dest), overwrite=True),
                     lambda res: (self._report(res), res.status == "VALID" and self.say(f"Diekspor ke {dest}. {STATUS_HELP['VALID'][0]}", "ok")),
                     self.fail)

    def save_note(self) -> None:
        if row := self._need_selection():
            ctx, user, note = self.ctx, self.user, self.note.get()
            self.app.run(lambda: ctx.evidence.add_note(user, row["id"], note),
                         lambda _r: (self.say("Catatan disimpan.", "ok"), self.load_evidence()), self.fail)
