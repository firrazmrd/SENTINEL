from __future__ import annotations

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class DashboardView(C.BaseView):
    title = "Dashboard"

    def build(self) -> None:
        self.cards = ctk.CTkFrame(self, fg_color="transparent")
        self.cards.pack(fill="x")
        self.label(self, "Aktivitas terbaru (sesuai izin akses)", muted=True).pack(anchor="w", pady=(18, 4))
        self.table = C.DataTable(self, [("time", "Waktu", 140), ("actor", "Aktor", 120), ("event", "Event", 220),
                                        ("case", "Kasus", 90)], height=9)
        self.table.pack(fill="x")

    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: (ctx.dashboard.summary(user), ctx.audit.search(user, limit=8)), self._show, self.fail)

    def _show(self, data: tuple) -> None:
        summary, events = data
        for w in self.cards.winfo_children():
            w.destroy()
        names = {"cases": "Kasus", "evidence": "Bukti", "unread_messages": "Pesan belum dibaca",
                 "audit_events": "Event audit", "users": "Pengguna"}
        for key, label in names.items():
            if key in summary:
                card = self.card(self.cards)
                card.pack(side="left", padx=(0, 12), ipadx=14, ipady=8)
                ctk.CTkLabel(card, text=str(summary[key]), font=C.font(28, "bold"), text_color=C.ACCENT).pack(padx=16, pady=(8, 0))
                ctk.CTkLabel(card, text=label, font=C.font(11), text_color=C.MUTED).pack(padx=16, pady=(0, 8))
        self.table.set_rows([{"id": e["id"], "time": to_local(e["created_at"]), "actor": e["actor_username"] or "—",
                              "event": e["event_type"], "case": e["case_number"] or ""} for e in events])
