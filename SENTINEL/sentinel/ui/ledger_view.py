from __future__ import annotations

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local


class LedgerView(C.BaseView):
    title = "Integrity Ledger (local hash chain)"

    def build(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent"); bar.pack(fill="x")
        self.button(bar, "Verifikasi Integritas Ledger", self.verify).pack(side="left")
        self.result = ctk.CTkLabel(bar, text="", font=C.font(14, "bold")); self.result.pack(side="left", padx=16)
        self.table = C.DataTable(self, [("idx", "Block", 60), ("at", "Waktu", 140), ("event", "Event", 200),
                                        ("hash", "block_hash", 160), ("prev", "previous_hash", 160)], height=14)
        self.table.pack(fill="x", pady=12)
        self.label(self, "Hash chain lokal: mendeteksi perubahan/penghapusan di tengah rantai. Bukan blockchain terdistribusi; "
                   "pemotongan di ujung rantai tidak terdeteksi tanpa jangkar eksternal.", muted=True, size=11).pack(anchor="w")

    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: ctx.ledger.recent_blocks(user), lambda rows: self.table.set_rows(
            [{"id": b["block_index"], "idx": b["block_index"], "at": to_local(b["timestamp_utc"]), "event": b["event_type"],
              "hash": C.short(b["block_hash"], 18), "prev": C.short(b["previous_hash"], 18)} for b in rows]), self.fail)

    def verify(self) -> None:
        ctx, user = self.ctx, self.user
        self.result.configure(text="Memverifikasi…", text_color=C.MUTED)
        def show(r) -> None:
            if r.valid:
                self.result.configure(text=f"VALID — {r.blocks_checked} block terverifikasi", text_color=C.OK)
            else:
                where = f" pada block #{r.first_invalid_index}" if r.first_invalid_index is not None else ""
                self.result.configure(text=f"TIDAK VALID{where}: {r.reason}", text_color=C.ERR)
            self.refresh()
        self.app.run(lambda: ctx.ledger.verify(user), show, self.fail)
