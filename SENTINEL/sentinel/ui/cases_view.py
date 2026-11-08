from __future__ import annotations

import customtkinter as ctk

from sentinel.services.permission_service import Action as A
from sentinel.services.permission_service import PermissionService as P
from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class CasesView(C.BaseView):
    title = "Cases"

    def build(self) -> None:
        role = self.user.role
        self.can_create, self.can_update = P.role_allows(role, A.CREATE_CASE), P.role_allows(role, A.UPDATE_CASE)
        self.can_assign = P.role_allows(role, A.ASSIGN_ANALYST)
        bar = ctk.CTkFrame(self, fg_color="transparent"); bar.pack(fill="x", pady=(0, 8))
        self.q = self.entry(bar, "Cari nomor/judul kasus", width=280); self.q.pack(side="left")
        self.button(bar, "Cari", self.refresh).pack(side="left", padx=8)
        self.q.bind("<Return>", lambda _e: self.refresh())
        self.table = C.DataTable(self, [("number", "Nomor", 90), ("title", "Judul", 260), ("status", "Status", 90),
                                        ("creator", "Pembuat", 140), ("analyst", "Analyst", 140), ("created", "Dibuat", 130)],
                                 height=8, on_select=self._selected)
        self.table.pack(fill="x")
        form = self.card(); form.pack(fill="x", pady=12)
        self.label(form, "Detail / form kasus", bold=True).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.title_e = self.entry(form, "Judul kasus", width=330); self.title_e.grid(row=1, column=0, padx=12, sticky="w")
        self.desc = self.textbox(form, 90); self.desc.grid(row=2, column=0, padx=12, pady=8, sticky="we")
        right = ctk.CTkFrame(form, fg_color="transparent"); right.grid(row=1, column=1, rowspan=2, padx=12, sticky="n")
        self.status_var = ctk.StringVar(value="OPEN")
        ctk.CTkOptionMenu(right, variable=self.status_var, values=["OPEN", "IN_REVIEW", "CLOSED"], width=200,
                          fg_color=C.BG, button_color=C.PANEL_2).pack(pady=2)
        if self.can_create:
            self.button(right, "Buat Kasus Baru", self.create).pack(fill="x", pady=2)
        if self.can_update:
            self.button(right, "Simpan Perubahan", self.save, secondary=True).pack(fill="x", pady=2)
        self.analyst_var = ctk.StringVar(value="")
        if self.can_assign:
            self.analyst_menu = ctk.CTkOptionMenu(right, variable=self.analyst_var, values=["(belum ada analyst)"],
                                                  width=200, fg_color=C.BG, button_color=C.PANEL_2)
            self.analyst_menu.pack(pady=(10, 2))
            self.button(right, "Tugaskan Analyst", self.assign, secondary=True).pack(fill="x", pady=2)
        form.columnconfigure(0, weight=1)
        self._analysts: dict[str, str] = {}

    def refresh(self) -> None:
        ctx, user, q = self.ctx, self.user, self.q.get()
        def work():
            analysts = ctx.users.list_analysts(user) if self.can_assign else []
            return ctx.cases.list_cases(user, q), analysts
        self.app.run(work, self._loaded, self.fail)

    def _loaded(self, data: tuple) -> None:
        cases, analysts = data
        self.table.set_rows([{"id": c["id"], "number": c["case_number"], "title": c["title"], "status": c["status"],
                              "creator": c["creator_name"], "analyst": c["analyst_name"] or "—",
                              "created": to_local(c["created_at"]), "_c": c} for c in cases])
        if self.can_assign:
            self._analysts = {f"{a['full_name']} ({a['username']})": a["id"] for a in analysts}
            names = list(self._analysts) or ["(belum ada analyst)"]
            self.analyst_menu.configure(values=names)
            self.analyst_var.set(names[0])

    def _selected(self, row: dict | None) -> None:
        if not row:
            return
        c = row["_c"]
        self.title_e.delete(0, "end"); self.title_e.insert(0, c["title"])
        self.set_text(self.desc, c["description"] or "")
        self.status_var.set(c["status"])

    def create(self) -> None:
        ctx, user, t, d = self.ctx, self.user, self.title_e.get(), self.get_text(self.desc)
        self.app.run(lambda: ctx.cases.create_case(user, t, d),
                     lambda c: (self.say(f"Kasus {c['case_number']} dibuat.", "ok"), self.refresh()), self.fail)

    def save(self) -> None:
        sel = self.table.selected()
        if not sel:
            return self.say("Pilih kasus pada tabel terlebih dahulu.", "warn")
        ctx, user, t, d, s = self.ctx, self.user, self.title_e.get(), self.get_text(self.desc), self.status_var.get()
        self.app.run(lambda: ctx.cases.update_case(user, sel["id"], title=t, description=d, status=s),
                     lambda c: (self.say(f"Kasus {c['case_number']} diperbarui.", "ok"), self.refresh()), self.fail)

    def assign(self) -> None:
        sel, aid = self.table.selected(), self._analysts.get(self.analyst_var.get())
        if not sel or not aid:
            return self.say("Pilih kasus dan analyst.", "warn")
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.cases.assign_analyst(user, sel["id"], aid),
                     lambda c: (self.say(f"Analyst ditugaskan ke {c['case_number']}.", "ok"), self.refresh()), self.fail)
