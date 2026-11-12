from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import customtkinter as ctk

BG, PANEL, PANEL_2 = "#0b1220", "#111a2e", "#16223b"
ACCENT, ACCENT_HOVER = "#14b8a6", "#0d9488"
TEXT, MUTED, OK, WARN, ERR = "#e6edf7", "#8a9bb8", "#34d399", "#fbbf24", "#f87171"
# Settings page (blue/navy scheme from the design reference)
BLUE, BLUE_HOVER = "#2f81ed", "#2468c9"
NAVY_DEEP, NAVY_BTN, NAVY_BTN_HOVER, BORDER = "#0d1320", "#1a2540", "#22324f", "#1e2b47"
FONT = "Segoe UI"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def short(h: str | None, n: int = 12) -> str:
    return (h or "")[:n] + ("…" if h and len(h) > n else "")


def human_size(n: int) -> str:
    return f"{n / 1048576:.2f} MB" if n >= 1048576 else f"{n / 1024:.1f} KB" if n >= 1024 else f"{n} B"


class DataTable(ctk.CTkFrame):
    """ttk.Treeview styled for the dark theme. Rows are dicts; `columns` = [(key, title, width)]."""
    _styled = False

    def __init__(self, master: Any, columns: list[tuple[str, str, int]], height: int = 10,
                 on_select: Callable[[dict | None], None] | None = None) -> None:
        super().__init__(master, fg_color=PANEL, corner_radius=8)
        if not DataTable._styled:
            st = ttk.Style()
            st.theme_use("clam")
            st.configure("S.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, borderwidth=0,
                         rowheight=26, font=(FONT, 10))
            st.configure("S.Treeview.Heading", background=PANEL_2, foreground=TEXT, relief="flat", font=(FONT, 10, "bold"))
            st.map("S.Treeview", background=[("selected", ACCENT_HOVER)], foreground=[("selected", "white")])
            st.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL, arrowcolor=TEXT,
                         bordercolor=PANEL, lightcolor=PANEL_2, darkcolor=PANEL_2)
            st.layout("S.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
            DataTable._styled = True
        self._keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self._keys, show="headings", height=height,
                                 selectmode="browse", style="S.Treeview")
        for key, title, width in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=40, anchor="w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="right", fill="y", pady=4)
        self._rows: dict[str, dict] = {}
        self._on_select = on_select
        self.tree.bind("<<TreeviewSelect>>", lambda _e: on_select and on_select(self.selected()))

    def set_rows(self, rows: list[dict], key: str = "id") -> None:
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for i, r in enumerate(rows):
            iid = str(r.get(key, i))
            self._rows[iid] = r
            self.tree.insert("", "end", iid=iid, values=[r.get(k, "") for k in self._keys])
        if keep and keep[0] in self._rows:
            self.tree.selection_set(keep[0])

    def selected(self) -> dict | None:
        sel = self.tree.selection()
        return self._rows.get(sel[0]) if sel else None


class BaseView(ctk.CTkFrame):
    """A page. `app` provides ctx, user, run(), report_error(). Subclasses implement build() and refresh()."""
    title = ""

    def __init__(self, master: Any, app: Any) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.ctx, self.user = app.ctx, app.user
        ctk.CTkLabel(self, text=self.title, font=font(22, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 10))
        self._status = ctk.CTkLabel(self, text="", font=font(12), text_color=MUTED, anchor="w", justify="left",
                                    wraplength=900)
        self.build()
        self._status.pack(anchor="w", pady=(8, 0), fill="x")

    def build(self) -> None: ...
    def refresh(self) -> None: ...

    def say(self, text: str, level: str = "info") -> None:
        self._status.configure(text=text, text_color={"ok": OK, "error": ERR, "warn": WARN}.get(level, MUTED))

    def fail(self, exc: BaseException) -> None:
        self.say(self.app.describe_error(exc), "error")

    def card(self, parent: Any | None = None, **kw: Any) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent or self, fg_color=PANEL, corner_radius=10, **kw)

    def button(self, parent: Any, text: str, cmd: Callable[[], None], secondary: bool = False, **kw: Any) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, command=cmd, font=font(12, "bold"),
                             fg_color=PANEL_2 if secondary else ACCENT, hover_color="#22324f" if secondary else ACCENT_HOVER,
                             text_color=TEXT if secondary else "#04211f", **kw)

    def entry(self, parent: Any, placeholder: str = "", show: str | None = None, width: int = 220) -> ctk.CTkEntry:
        return ctk.CTkEntry(parent, placeholder_text=placeholder, show=show, width=width, fg_color=BG,
                            border_color=PANEL_2, font=font(12))

    def label(self, parent: Any, text: str, muted: bool = False, size: int = 12, bold: bool = False) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=font(size, "bold" if bold else "normal"),
                            text_color=MUTED if muted else TEXT, anchor="w", justify="left")

    def textbox(self, parent: Any, height: int = 120, readonly: bool = False) -> ctk.CTkTextbox:
        tb = ctk.CTkTextbox(parent, height=height, fg_color=BG, border_color=PANEL_2, border_width=1, font=font(12))
        return tb

    @staticmethod
    def set_text(tb: ctk.CTkTextbox, text: str) -> None:
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.insert("1.0", text)

    @staticmethod
    def get_text(tb: ctk.CTkTextbox) -> str:
        return tb.get("1.0", "end").strip()


def tk_messagebox() -> Any:
    from tkinter import messagebox
    return messagebox


def tk_filedialog() -> Any:
    from tkinter import filedialog
    return filedialog


__all__ = ["tk"]
