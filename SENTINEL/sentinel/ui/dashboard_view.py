"""Information-dense dashboard: one status strip, one metrics strip, then tables and panels. No per-metric cards."""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from sentinel.ui import common as C
from sentinel.utils.timeutil import to_local

BAD_EVIDENCE = ("CIPHERTEXT_MODIFIED", "PLAINTEXT_HASH_MISMATCH", "DECRYPTION_FAILED")
SECURITY_EVENTS = {
    "LOGIN_FAILED", "REAUTH_FAILED", "USB_REGISTERED", "USB_REVOKED", "BIOMETRIC_ENROLLMENT",
    "BIOMETRIC_TEMPLATE_DELETED", "AUTH_REQUIREMENTS_UPDATED", "PASSWORD_CHANGED", "PASSWORD_RESET_RECOVERY",
    "RECOVERY_CODE_REGENERATED", "SESSION_USB_DISCONNECTED", "SESSION_USB_RECONNECTED", "SESSION_CLOSED_USB_REMOVED",
}
CELLS = (("security", "STATUS KEAMANAN"), ("auth", "AUTENTIKASI"), ("usb", "USB DONGLE"),
         ("face", "FACE RECOGNITION"), ("ledger", "INTEGRITY LEDGER"))
METRICS = (("cases", "KASUS"), ("evidence", "BUKTI"), ("unread_messages", "PESAN BARU"),
           ("audit_events", "EVENT AUDIT"), ("users", "PENGGUNA"))


def evaluate(ov: dict) -> tuple[str, str, list[str]]:
    """-> (AMAN|PERHATIAN|KRITIS, colour, reasons). Pure function so the rules are unit-testable."""
    critical, warn = [], []
    if not ov["ledger"]["valid"]:
        idx = ov["ledger"]["first_invalid_index"]
        critical.append("Integrity ledger tidak valid" + (f" (blok #{idx})" if idx is not None else ""))
    bad = sum(n for st, n in ov["evidence_status"].items() if st in BAD_EVIDENCE)
    if bad:
        critical.append(f"{bad} bukti gagal verifikasi integritas")
    auth, usb = ov["auth"], ov["usb"]
    if auth["require_usb"] and usb["state"] != "VALID":
        warn.append("USB dongle diwajibkan tetapi belum valid / tidak terpasang")
    if not auth["require_usb"] and not auth["require_face"]:
        warn.append("Login hanya memakai password")
    if not auth["has_recovery_code"]:
        warn.append("Kode pemulihan belum dibuat")
    if critical:
        return "KRITIS", C.ERR, critical + warn
    if warn:
        return "PERHATIAN", C.WARN, warn
    return "AMAN", C.OK, ["Tidak ada temuan."]


class DashboardView(C.BaseView):
    title = "Dashboard"

    def build(self) -> None:
        root = ctk.CTkScrollableFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True)
        # -- status strip
        strip = C.Panel(root, "Status Keamanan & Autentikasi")
        strip.pack(fill="x", pady=(0, C.SP_M))
        self._cells: dict[str, tuple[C.StatusDot, ctk.CTkLabel, ctk.CTkLabel]] = {}
        for i, (key, caption) in enumerate(CELLS):
            strip.body.grid_columnconfigure(i, weight=1, uniform="cells")
            cell = ctk.CTkFrame(strip.body, fg_color="transparent")
            cell.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else C.SP_M, 0))
            ctk.CTkLabel(cell, text=caption, font=C.mono(9, "bold"), text_color=C.MUTED, anchor="w").pack(anchor="w")
            line = ctk.CTkFrame(cell, fg_color="transparent")
            line.pack(anchor="w", pady=(2, 0))
            dot = C.StatusDot(line, C.MUTED)
            dot.pack(side="left", padx=(0, C.SP_S))
            value = ctk.CTkLabel(line, text="…", font=C.font(13, "bold"), text_color=C.TEXT, wraplength=135, justify="left", anchor="w")
            value.pack(side="left")
            sub = ctk.CTkLabel(cell, text="", font=C.font(10), text_color=C.MUTED, anchor="w", justify="left", wraplength=150)
            sub.pack(anchor="w")
            self._cells[key] = (dot, value, sub)
        self.reason = ctk.CTkLabel(strip.body, text="", font=C.font(11), text_color=C.MUTED, anchor="w", justify="left", wraplength=860)
        self.reason.grid(row=1, column=0, columnspan=len(CELLS), sticky="w", pady=(C.SP_M, 0))
        # -- metrics strip (inline numbers, hairline separated)
        self.metrics = C.Panel(root, "Ringkasan Data")
        self.metrics.pack(fill="x", pady=(0, C.SP_M))
        # -- two columns
        cols = ctk.CTkFrame(root, fg_color="transparent")
        cols.pack(fill="x", pady=(0, C.SP_M))
        cols.grid_columnconfigure(0, weight=3, uniform="dash")
        cols.grid_columnconfigure(1, weight=2, uniform="dash")
        left = C.Panel(cols, "Aktivitas Terbaru", right="8 EVENT TERAKHIR")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, C.SP_M))
        self.table = C.DataTable(left.body, [("time", "Waktu", 130), ("actor", "Aktor", 100), ("event", "Event", 200),
                                             ("case", "Kasus", 80)], height=9, empty_text="Belum ada aktivitas.")
        self.table.pack(fill="both", expand=True)
        right = ctk.CTkFrame(cols, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.user_panel = C.Panel(right, "Pengguna & Sesi")
        self.user_panel.pack(fill="x", pady=(0, C.SP_M))
        self.file_panel = C.Panel(right, "Integritas File")
        self.file_panel.pack(fill="x")
        # -- security events
        sec = C.Panel(root, "Event Keamanan Terbaru", right="LOGIN GAGAL · USB · BIOMETRIK · PEMULIHAN")
        sec.pack(fill="x")
        self.sec_table = C.DataTable(sec.body, [("time", "Waktu", 130), ("actor", "Aktor", 100), ("event", "Event", 240),
                                                ("detail", "Detail", 220)], height=5, empty_text="Tidak ada event keamanan.")
        self.sec_table.pack(fill="both", expand=True)

    def refresh(self) -> None:
        ctx, user = self.ctx, self.user
        self.app.run(lambda: (ctx.dashboard.summary(user), ctx.dashboard.security_overview(user),
                              ctx.audit.search(user, limit=80)), self._show, self.fail)

    # -- rendering ------------------------------------------------------------------------------------------
    def _set(self, key: str, value: str, color: str, sub: str = "", pulse: bool = False) -> None:
        dot, label, subl = self._cells[key]
        dot.set(color, pulse)
        label.configure(text=value)
        subl.configure(text=sub)

    def _show(self, data: tuple) -> None:
        summary, ov, events = data
        level, color, reasons = evaluate(ov)
        auth, usb, face, led = ov["auth"], ov["usb"], ov["auth"], ov["ledger"]
        self._set("security", level, color, f"{len(reasons)} temuan" if level != "AMAN" else "", level != "AMAN")
        self.reason.configure(text="  ·  ".join(reasons), text_color=color if level != "AMAN" else C.MUTED)
        factors = ["PASSWORD"] + (["USB"] if auth["require_usb"] else []) + (["WAJAH"] if auth["require_face"] else [])
        self._set("auth", " + ".join(factors), C.OK if len(factors) > 1 else C.WARN, "faktor wajib akun ini")
        usb_view = {"VALID": ("TERHUBUNG", C.OK), "NONE_REGISTERED": ("BELUM TERDAFTAR", C.WARN),
                    "NO_DRIVE": ("TIDAK TERPASANG", C.ERR if auth["require_usb"] else C.WARN),
                    "NOT_VALID": ("TIDAK VALID", C.ERR)}.get(usb["state"], (usb["state"], C.WARN))
        self._set("usb", usb_view[0], usb_view[1], usb["message"])
        self._set("face", "TERDAFTAR" if face["has_face"] else "BELUM TERDAFTAR", C.OK if face["has_face"] else C.WARN,
                  "wajib saat login" if face["require_face"] else "tidak diwajibkan")
        self._set("ledger", "VALID" if led["valid"] else "TIDAK VALID", C.OK if led["valid"] else C.ERR,
                  f"{led['blocks']} blok terverifikasi" if led["valid"] else led["reason"])
        self._metrics(summary, led["blocks"])
        self.table.set_rows([{"id": e["id"], "time": to_local(e["created_at"]), "actor": e["actor_username"] or "—",
                              "event": e["event_type"], "case": e["case_number"] or ""} for e in events[:8]])
        self.sec_table.set_rows([{"id": e["id"], "time": to_local(e["created_at"]), "actor": e["actor_username"] or "—",
                                  "event": e["event_type"], "detail": self._detail(e)}
                                 for e in events if e["event_type"] in SECURITY_EVENTS][:5])
        self._user_panel(ov)
        self._file_panel(ov)

    @staticmethod
    def _detail(e: Any) -> str:
        raw = e["details_json"] or ""
        return raw if len(raw) <= 40 else raw[:39] + "…"

    def _metrics(self, summary: dict, blocks: int) -> None:
        body = self.metrics.body
        for w in body.winfo_children():
            w.destroy()
        items = [(label, summary[key]) for key, label in METRICS if key in summary] + [("BLOK LEDGER", blocks)]
        for i, (label, value) in enumerate(items):
            body.grid_columnconfigure(i * 2, weight=1, uniform="met")
            cell = ctk.CTkFrame(body, fg_color="transparent")
            cell.grid(row=0, column=i * 2, sticky="w")
            ctk.CTkLabel(cell, text=str(value), font=C.mono(26, "bold"), text_color=C.CYAN).pack(anchor="w")
            ctk.CTkLabel(cell, text=label, font=C.mono(9, "bold"), text_color=C.MUTED).pack(anchor="w")
            if i < len(items) - 1:
                ctk.CTkFrame(body, fg_color=C.BORDER, width=1, height=1).grid(row=0, column=i * 2 + 1, sticky="ns", padx=C.SP_M)

    def _user_panel(self, ov: dict) -> None:
        body, u = self.user_panel.body, ov["user"]
        for w in body.winfo_children():
            w.destroy()
        C.kv_row(body, 0, "Nama", u["full_name"])
        C.kv_row(body, 1, "Username", u["username"], mono_value=True)
        C.kv_row(body, 2, "Role", self.app.user.role_label)
        C.kv_row(body, 3, "Sesi dimulai", to_local(u["last_login_at"]) if u["last_login_at"] else "—", mono_value=True)
        C.kv_row(body, 4, "Kode pemulihan", "sudah dibuat" if ov["auth"]["has_recovery_code"] else "belum dibuat",
                 C.OK if ov["auth"]["has_recovery_code"] else C.WARN)

    def _file_panel(self, ov: dict) -> None:
        body, st = self.file_panel.body, ov["evidence_status"]
        for w in body.winfo_children():
            w.destroy()
        total = sum(st.values())
        bad = sum(n for k, n in st.items() if k in BAD_EVIDENCE)
        if total == 0:
            ctk.CTkLabel(body, text="Belum ada bukti yang tersimpan.", font=C.font(12), text_color=C.MUTED).pack(anchor="w")
            return
        C.kv_row(body, 0, "Terverifikasi", str(st.get("VALID", 0)), C.OK, mono_value=True)
        C.kv_row(body, 1, "Belum diverifikasi", str(sum(n for k, n in st.items() if k not in BAD_EVIDENCE and k != "VALID")),
                 C.MUTED, mono_value=True)
        C.kv_row(body, 2, "Bermasalah", str(bad), C.ERR if bad else C.OK, mono_value=True)
        C.kv_row(body, 3, "Total bukti", str(total), mono_value=True)
