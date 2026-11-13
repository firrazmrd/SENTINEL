"""Live camera view used by the login screen and the face enrollment dialog (same widget, same status vocabulary)."""
from __future__ import annotations

import tkinter as tk
from typing import Any

from sentinel.ui import common as C

# stage -> (label, colour, animated)
STATUS = {
    "IDLE": ("CAMERA OFF", C.MUTED, False),
    "CAMERA_INITIALIZING": ("CAMERA INITIALIZING", C.WARN, True),
    "CAMERA_ACTIVE": ("CAMERA ACTIVE", C.OK, True),
    "SCANNING": ("SCANNING", C.CYAN, True),
    "VERIFYING": ("VERIFYING", C.ACCENT, True),
    "VERIFIED": ("VERIFIED", C.OK, False),
    "FAILED": ("FAILED", C.ERR, False),
    "CAMERA_UNAVAILABLE": ("CAMERA UNAVAILABLE", C.ERR, False),
}


def frame_to_image(frame: Any, max_size: tuple[int, int]) -> Any | None:
    """BGR ndarray -> mirrored PIL image; None for anything that is not a real camera frame (e.g. test doubles)."""
    if not hasattr(frame, "shape"):
        return None
    try:
        import cv2
        from PIL import Image
        img = Image.fromarray(cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB))
        img.thumbnail(max_size)
        return img
    except Exception:  # noqa: BLE001
        return None


class CameraPanel(tk.Canvas):
    def __init__(self, master: Any, width: int = 440, height: int = 330) -> None:
        super().__init__(master, width=width, height=height, bg="#070C16", highlightthickness=1,
                         highlightbackground=C.BORDER, bd=0)
        self._stream: Any = None
        self._photo: Any = None
        self._stage, self._sweep, self._job = "IDLE", 0, None
        self._idle_text = ("KAMERA NONAKTIF", "Aktif otomatis bila akun mewajibkan verifikasi wajah")
        self.bind("<Configure>", lambda _e: self._draw())
        self._draw()

    # -- public API ----------------------------------------------------------------
    @property
    def stage(self) -> str:
        return self._stage

    def set_stage(self, stage: str) -> None:
        self._stage = stage if stage in STATUS else "IDLE"
        self._draw()

    def attach(self, stream: Any) -> None:
        self._stream = stream
        if self._job is None:
            self._tick()

    def detach(self, stage: str | None = None) -> None:
        """Stop rendering and drop the last frame (nothing from the camera is kept)."""
        self._stream, self._photo = None, None
        if stage:
            self._stage = stage
        self._draw()

    def set_idle_text(self, title: str, sub: str = "") -> None:
        self._idle_text = (title, sub)
        self._draw()

    # -- rendering -----------------------------------------------------------------
    def _tick(self) -> None:
        self._job = None
        try:
            if self._stream is None or not self.winfo_exists():
                return
            img = frame_to_image(self._stream.latest(), (max(self.winfo_width(), 80), max(self.winfo_height(), 60)))
            if img is not None:
                from PIL import ImageTk
                self._photo = ImageTk.PhotoImage(img)
            self._sweep = (self._sweep + 6) % 100
            self._draw()
            self._job = self.after(40, self._tick)
        except tk.TclError:
            pass

    def _draw(self) -> None:
        try:
            self.delete("all")
            w, h = self.winfo_width() or int(self["width"]), self.winfo_height() or int(self["height"])
            label, color, animated = STATUS[self._stage]
            if self._photo is not None:
                self.create_image(w // 2, h // 2, image=self._photo)
            elif self._stream is not None:
                self.create_text(w // 2, h // 2, text="MENUNGGU FRAME…", fill=C.MUTED, font=C.mono(11))
            else:
                self.create_text(w // 2, h // 2 - 10, text=self._idle_text[0], fill=C.MUTED, font=C.mono(13, "bold"))
                self.create_text(w // 2, h // 2 + 14, text=self._idle_text[1], fill=C.MUTED, font=C.font(10),
                                 width=max(w - 60, 100), justify="center")
            if animated and self._stage in ("SCANNING", "VERIFYING") and self._stream is not None:
                y = int(h * self._sweep / 100)
                self.create_line(8, y, w - 8, y, fill=C.CYAN, width=1)
            m, n = 10, 26  # tactical corner brackets in the status colour
            for x0, y0, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
                self.create_line(x0, y0, x0 + dx * n, y0, fill=color, width=2)
                self.create_line(x0, y0, x0, y0 + dy * n, fill=color, width=2)
            self.create_rectangle(m + 6, m + 6, m + 14 + 8 * len(label), m + 26, fill="#070C16", outline="")
            self.create_text(m + 10, m + 16, text=label, anchor="w", fill=color, font=C.mono(10, "bold"))
        except tk.TclError:
            pass

    def destroy(self) -> None:
        self._stream = None
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        super().destroy()
