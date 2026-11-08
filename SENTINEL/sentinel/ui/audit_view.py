from __future__ import annotations

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class AuditView(C.BaseView):
    title = "Activity Logs"

    def build(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent"); bar.pack(fill="x", pady=(0, 8))
        self.ev_var = ctk.StringVar(value="(semua event)")
        self.ev_menu = ctk.CTkOptionMenu(bar, variable=self.ev_var, values=["(semua event)"], width=210, fg_color=C.BG, button_color=C.PANEL_2)
        self.ev_menu.pack(side="left")
        self.case_var = ctk.StringVar(value="(semua kasus)")
        self.case_menu = ctk.CTkOptionMenu(bar, variable=self.case_var, values=["(semua kasus)"], width=170, fg_color=C.BG, button_color=C.PANEL_2)
        self.case_menu.pack(side="left", padx=6)
        self.actor = self.entry(bar, "Username aktor", width=130); self.actor.pack(side="left", padx=6)
        self.d_from = self.entry(bar, "Dari YYYY-MM-DD", width=120); self.d_from.pack(side="left", padx=6)
        self.d_to = self.entry(bar, "Sampai YYYY-MM-DD", width=130); self.d_to.pack(side="left", padx=6)
        self.button(bar, "Terapkan", self.search).pack(side="left", padx=6)
        self.table = C.DataTable(self, [("at", "Waktu", 130), ("actor", "Aktor", 110), ("event", "Event", 190),
                                        ("target", "Target", 120), ("case", "Kasus", 80), ("details", "Detail", 300)], height=17)
        self.table.pack(fill="both", expand=True)
        self._cases: dict[str, str] = {}

    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: (ctx.audit.event_types(user), ctx.cases.list_cases(user)), self._filters, self.fail)

    def _filters(self, data: tuple) -> None:
        events, cases = data
        self.ev_menu.configure(values=["(semua event)", *events])
        self._cases = {c["case_number"]: c["id"] for c in cases}
        self.case_menu.configure(values=["(semua kasus)", *self._cases])
        self.search()

    def search(self) -> None:
        ctx, user = self.ctx, self.user
        ev = None if self.ev_var.get().startswith("(") else self.ev_var.get()
        cid = self._cases.get(self.case_var.get())
        d_from = self.d_from.get().strip() or None
        d_to = (self.d_to.get().strip() + "T23:59:59.999999Z") if self.d_to.get().strip() else None
        d_from = (d_from + "T00:00:00.000000Z") if d_from else None
        who = self.actor.get().strip().lower()
        def work():
            rows = ctx.audit.search(user, event_type=ev, case_id=cid, date_from=d_from, date_to=d_to, limit=1000)
            return [r for r in rows if not who or who in (r["actor_username"] or "").lower()]
        self.app.run(work, self._show, self.fail)

    def _show(self, rows: list) -> None:
        self.table.set_rows([{"id": r["id"], "at": to_local(r["created_at"]), "actor": r["actor_username"] or "—",
                              "event": r["event_type"], "target": f"{r['target_type'] or ''} {C.short(r['target_id'], 8)}".strip(),
                              "case": r["case_number"] or "", "details": r["details_json"]} for r in rows])
        self.say(f"{len(rows)} event ditampilkan.")
