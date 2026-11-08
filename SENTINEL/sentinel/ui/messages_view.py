from __future__ import annotations

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class MessagesView(C.BaseView):
    title = "Secure Messages"

    def build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="both", expand=True)
        left = ctk.CTkFrame(top, fg_color="transparent"); left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.tab = ctk.CTkSegmentedButton(left, values=["Inbox", "Terkirim"], command=lambda _v: self.refresh(),
                                          selected_color=C.ACCENT, selected_hover_color=C.ACCENT_HOVER)
        self.tab.set("Inbox"); self.tab.pack(anchor="w", pady=(0, 6))
        self.table = C.DataTable(left, [("who", "Dari / Kepada", 150), ("case", "Kasus", 80), ("at", "Waktu", 130),
                                        ("state", "Status", 70)], height=8, on_select=self._open)
        self.table.pack(fill="x")
        self.reader = self.textbox(left, 140); self.reader.pack(fill="x", pady=8)
        self.set_text(self.reader, "Pilih pesan untuk membaca (didekripsi: AES-256-GCM lalu Vigenère).")
        comp = self.card(); comp.pack(side="left", fill="y")
        self.label(comp, "Pesan baru", bold=True, size=14).pack(anchor="w", padx=12, pady=(10, 4))
        self.to_var = ctk.StringVar(value="")
        self.to_menu = ctk.CTkOptionMenu(comp, variable=self.to_var, values=["(memuat)"], width=260, fg_color=C.BG, button_color=C.PANEL_2)
        self.to_menu.pack(padx=12, pady=4)
        self.case_var = ctk.StringVar(value="(tanpa kasus)")
        self.case_menu = ctk.CTkOptionMenu(comp, variable=self.case_var, values=["(tanpa kasus)"], width=260, fg_color=C.BG, button_color=C.PANEL_2)
        self.case_menu.pack(padx=12, pady=4)
        self.body = self.textbox(comp, 150); self.body.pack(padx=12, pady=6, fill="x")
        self.button(comp, "Kirim Terenkripsi", self.send).pack(padx=12, pady=(4, 12), fill="x")
        self._rcpt: dict[str, str] = {}
        self._cases: dict[str, str] = {}

    def refresh(self) -> None:
        ctx, user, sent = self.ctx, self.user, self.tab.get() == "Terkirim"
        def work():
            rows = ctx.messages.sent(user) if sent else ctx.messages.inbox(user)
            return rows, ctx.users.list_recipients(user), ctx.cases.list_cases(user)
        self.app.run(work, lambda d: self._loaded(d, sent), self.fail)

    def _loaded(self, data: tuple, sent: bool) -> None:
        rows, rcpts, cases = data
        self.table.set_rows([{"id": m["id"], "who": m["receiver_name"] if sent else m["sender_name"],
                              "case": m["case_number"] or "", "at": to_local(m["created_at"]),
                              "state": "" if sent else ("baru" if m["read_at"] is None else "dibaca")} for m in rows])
        self._rcpt = {f"{u['full_name']} — {u['role']}": u["id"] for u in rcpts}
        names = list(self._rcpt) or ["(tidak ada penerima)"]
        self.to_menu.configure(values=names)
        if self.to_var.get() not in self._rcpt:
            self.to_var.set(names[0])
        self._cases = {f"{c['case_number']} — {c['title']}": c["id"] for c in cases}
        self.case_menu.configure(values=["(tanpa kasus)", *self._cases])

    def _open(self, row: dict | None) -> None:
        if not row:
            return
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.messages.read(user, row["id"]),
                     lambda text: (self.set_text(self.reader, text), self.say("Pesan berhasil diautentikasi dan didekripsi.", "ok")),
                     lambda e: (self.set_text(self.reader, ""), self.fail(e)))

    def send(self) -> None:
        rid, body = self._rcpt.get(self.to_var.get()), self.get_text(self.body)
        if not rid:
            return self.say("Pilih penerima.", "warn")
        cid = self._cases.get(self.case_var.get())
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.messages.send(user, rid, body, cid),
                     lambda _m: (self.set_text(self.body, ""), self.say("Pesan terkirim (Vigenère + AES-256-GCM).", "ok"), self.refresh()),
                     self.fail)
