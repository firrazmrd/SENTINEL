"""Design tokens + shared widgets. TACTICAL SECURITY / INDUSTRIAL PREMIUM: deep navy surfaces, hairline borders,
small radii, one primary accent (electric blue) and cyan only for technical/live data."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Callable

import customtkinter as ctk

# ---- colour tokens ------------------------------------------------------------------------------------------
BG = "#0B1220"            # deep navy (window)
PANEL = "#151F30"         # panel background
PANEL_2 = "#1B293D"       # secondary surface (inputs, secondary buttons)
PANEL_ALT = "#18243A"     # zebra rows
BORDER = "#26354D"        # hairline
ACCENT, ACCENT_HOVER = "#3182E8", "#2468C9"     # electric blue = primary action
CYAN = "#55C9D5"          # muted cyan = live/technical data (camera, hashes)
OK, WARN, ERR = "#24B47E", "#E5A43B", "#E05252"
TEXT, MUTED = "#DCE5F1", "#94A3B8"
ON_ACCENT = "#FFFFFF"
HOVER_2 = "#243652"       # hover for secondary surfaces
# aliases kept for older call sites
BLUE, BLUE_HOVER = ACCENT, ACCENT_HOVER
NAVY_DEEP, NAVY_BTN, NAVY_BTN_HOVER = BG, PANEL_2, HOVER_2

# ---- spacing / shape tokens (4-pt grid) ------------------------------------------------------------------------
SP_XS, SP_S, SP_M, SP_L, SP_XL = 4, 8, 12, 16, 24
RADIUS, RADIUS_S = 8, 6

FONT = "Segoe UI"          # replaced by IBM Plex Sans once init_fonts() succeeds
MONO = "Consolas"          # replaced by Cascadia Code when installed (ships with Windows 11)
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def init_fonts(root: Any = None) -> tuple[str, str]:
    """Load the bundled IBM Plex Sans (OFL) for this process and pick the best installed fonts.
    Needs a Tk root. Falls back to Segoe UI / Consolas, so a missing font never breaks the app."""
    global FONT, MONO
    for ttf in sorted(_FONT_DIR.glob("*.ttf")) if _FONT_DIR.is_dir() else []:
        try:
            ctk.FontManager.load_font(str(ttf))
        except Exception:  # noqa: BLE001 - cosmetic only
            pass
    try:
        fams = {f.lower() for f in tkfont.families(root)}
    except tk.TclError:
        fams = set()
    FONT = next((f for f in ("IBM Plex Sans", "Segoe UI", "Arial") if f.lower() in fams), FONT)
    MONO = next((f for f in ("Cascadia Code", "Cascadia Mono", "Consolas", "Courier New") if f.lower() in fams), MONO)
    return FONT, MONO


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def mono(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    """Hashes, IDs, fingerprints, codes."""
    return ctk.CTkFont(family=MONO, size=size, weight=weight)


def short(h: str | None, n: int = 12) -> str:
    return (h or "")[:n] + ("…" if h and len(h) > n else "")


def human_size(n: int) -> str:
    return f"{n / 1048576:.2f} MB" if n >= 1048576 else f"{n / 1024:.1f} KB" if n >= 1024 else f"{n} B"


# ---- animation helpers ----------------------------------------------------------------------------------------
def _rgb(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def blend(c1: str, c2: str, t: float) -> str:
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class StatusDot(tk.Canvas):
    """Status indicator. Colour changes tween over ~160 ms; `pulse=True` breathes gently (live/scanning states)."""

    def __init__(self, master: Any, color: str = MUTED, size: int = 10, bg: str = PANEL) -> None:
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._shown, self._target, self._pulse, self._phase, self._bg = color, color, False, 0, bg
        self._oval = self.create_oval(1, 1, size - 1, size - 1, fill=color, outline="")
        self._job: str | None = None

    def set(self, color: str, pulse: bool = False) -> None:
        self._target, self._pulse = color, pulse
        if self._job is None:
            self._step()

    def _step(self) -> None:
        self._job = None
        try:
            if not self.winfo_exists():
                return
            self._shown = blend(self._shown, self._target, 0.35) if self._shown != self._target else self._target
            shade = self._shown
            if self._pulse:
                self._phase = (self._phase + 1) % 28
                shade = blend(self._shown, self._bg, 0.55 * abs(14 - self._phase) / 14)
            self.itemconfigure(self._oval, fill=shade)
            if self._pulse or self._shown != self._target:
                self._job = self.after(55, self._step)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        super().destroy()


class StatusPill(ctk.CTkFrame):
    """[dot] LABEL in mono caps, e.g. CAMERA ACTIVE."""

    def __init__(self, master: Any, text: str = "", color: str = MUTED, bg: str = PANEL_2) -> None:
        super().__init__(master, fg_color=bg, corner_radius=RADIUS_S, height=28)
        self.dot = StatusDot(self, color, bg=bg)
        self.dot.pack(side="left", padx=(SP_M, SP_S), pady=SP_S)
        self.text = ctk.CTkLabel(self, text=text, font=mono(11, "bold"), text_color=TEXT)
        self.text.pack(side="left", padx=(0, SP_M))

    def set(self, text: str, color: str, pulse: bool = False) -> None:
        self.text.configure(text=text)
        self.dot.set(color, pulse)


class Panel(ctk.CTkFrame):
    """Bordered panel with a caps header strip; put content in `.body`."""

    def __init__(self, master: Any, title: str = "", right: str = "") -> None:
        super().__init__(master, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=RADIUS)
        if title:
            head = ctk.CTkFrame(self, fg_color="transparent")
            head.pack(fill="x", padx=SP_L, pady=(SP_M, 0))
            ctk.CTkLabel(head, text=title.upper(), font=mono(10, "bold"), text_color=MUTED).pack(side="left")
            self.right = ctk.CTkLabel(head, text=right, font=mono(10), text_color=MUTED)
            self.right.pack(side="right")
            ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=SP_L, pady=(SP_S, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=SP_L, pady=SP_M)


def kv_row(parent: Any, row: int, key: str, value: str, color: str | None = None, mono_value: bool = False) -> StatusDot | None:
    """key | [dot] value, laid out on a 2-column grid (column 1 stretches)."""
    ctk.CTkLabel(parent, text=key, font=font(12), text_color=MUTED, anchor="w").grid(row=row, column=0, sticky="w", pady=3)
    cell = ctk.CTkFrame(parent, fg_color="transparent")
    cell.grid(row=row, column=1, sticky="w", padx=(SP_L, 0), pady=3)
    dot = None
    if color:
        dot = StatusDot(cell, color)
        dot.pack(side="left", padx=(0, SP_S))
    ctk.CTkLabel(cell, text=value, font=mono(12) if mono_value else font(12, "bold"), text_color=TEXT,
                 anchor="w").pack(side="left")
    parent.grid_columnconfigure(1, weight=1)
    return dot


class DataTable(ctk.CTkFrame):
    """ttk.Treeview styled for the dark theme. Rows are dicts; `columns` = [(key, title, width)].
    Shows a loading text until the first set_rows(), and an empty-state text when there are no rows."""
    _styled_font: str | None = None

    def __init__(self, master: Any, columns: list[tuple[str, str, int]], height: int = 10,
                 on_select: Callable[[dict | None], None] | None = None, empty_text: str = "Belum ada data.") -> None:
        super().__init__(master, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=RADIUS)
        if DataTable._styled_font != FONT:
            st = ttk.Style()
            st.theme_use("clam")
            st.configure("S.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, borderwidth=0,
                         rowheight=28, font=(FONT, 10))
            st.configure("S.Treeview.Heading", background=PANEL_2, foreground=MUTED, relief="flat", font=(FONT, 9, "bold"))
            st.map("S.Treeview", background=[("selected", ACCENT)], foreground=[("selected", ON_ACCENT)])
            st.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL, arrowcolor=MUTED,
                         bordercolor=PANEL, lightcolor=PANEL_2, darkcolor=PANEL_2)
            st.map("Vertical.TScrollbar", background=[("disabled", PANEL), ("active", HOVER_2), ("!active", PANEL_2)],
                   troughcolor=[("disabled", PANEL), ("!disabled", PANEL)], arrowcolor=[("disabled", PANEL), ("!disabled", MUTED)])
            st.layout("S.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
            DataTable._styled_font = FONT
        self._keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self._keys, show="headings", height=height,
                                 selectmode="browse", style="S.Treeview")
        self.tree.tag_configure("alt", background=PANEL_ALT)
        for key, title, width in columns:
            self.tree.heading(key, text=title.upper(), anchor="w")
            self.tree.column(key, width=width, minwidth=40, anchor="w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(SP_XS, 0), pady=SP_XS)
        sb.pack(side="right", fill="y", pady=SP_XS)
        self._rows: dict[str, dict] = {}
        self._on_select, self._empty_text = on_select, empty_text
        self._note = ctk.CTkLabel(self, text="Memuat data…", font=font(12), text_color=MUTED, fg_color=PANEL)
        self._note.place(relx=0.5, rely=0.55, anchor="center")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: on_select and on_select(self.selected()))

    def set_rows(self, rows: list[dict], key: str = "id") -> None:
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for i, r in enumerate(rows):
            iid = str(r.get(key, i))
            self._rows[iid] = r
            self.tree.insert("", "end", iid=iid, values=[r.get(k, "") for k in self._keys],
                             tags=("alt",) if i % 2 else ())
        if rows:
            self._note.place_forget()
        else:
            self._note.configure(text=self._empty_text)
            self._note.place(relx=0.5, rely=0.55, anchor="center")
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
        ctk.CTkLabel(self, text=self.title, font=font(22, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, SP_M))
        self._status = ctk.CTkLabel(self, text="", font=font(12), text_color=MUTED, anchor="w", justify="left",
                                    wraplength=900)
        self.build()
        self._status.pack(anchor="w", pady=(SP_S, 0), fill="x")

    def build(self) -> None: ...
    def refresh(self) -> None: ...

    def say(self, text: str, level: str = "info") -> None:
        self._status.configure(text=text, text_color={"ok": OK, "error": ERR, "warn": WARN}.get(level, MUTED))

    def fail(self, exc: BaseException) -> None:
        self.say(self.app.describe_error(exc), "error")

    def card(self, parent: Any | None = None, **kw: Any) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent or self, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=RADIUS, **kw)

    def button(self, parent: Any, text: str, cmd: Callable[[], None], secondary: bool = False, **kw: Any) -> ctk.CTkButton:
        kw.setdefault("height", 34)
        return ctk.CTkButton(parent, text=text, command=cmd, font=font(12, "bold"), corner_radius=RADIUS_S,
                             fg_color=PANEL_2 if secondary else ACCENT, hover_color=HOVER_2 if secondary else ACCENT_HOVER,
                             text_color=TEXT if secondary else ON_ACCENT, **kw)

    def entry(self, parent: Any, placeholder: str = "", show: str | None = None, width: int = 220) -> ctk.CTkEntry:
        return ctk.CTkEntry(parent, placeholder_text=placeholder, show=show, width=width, height=34, fg_color=BG,
                            border_color=BORDER, corner_radius=RADIUS_S, font=font(12))

    def label(self, parent: Any, text: str, muted: bool = False, size: int = 12, bold: bool = False) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=font(size, "bold" if bold else "normal"),
                            text_color=MUTED if muted else TEXT, anchor="w", justify="left")

    def textbox(self, parent: Any, height: int = 120, readonly: bool = False) -> ctk.CTkTextbox:
        tb = ctk.CTkTextbox(parent, height=height, fg_color=BG, border_color=BORDER, border_width=1, corner_radius=RADIUS_S, font=font(12))
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
