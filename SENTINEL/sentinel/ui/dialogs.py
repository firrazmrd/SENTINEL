"""Modal dialogs: generic form (runs its work off the Tk thread), one-time recovery code display, face enrollment."""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from sentinel.ui import common as C


class _Modal(ctk.CTkToplevel):
    def __init__(self, app: Any, title: str, width: int = 440) -> None:
        super().__init__(app)
        self.app, self._closed = app, False
        self.title(title)
        self.configure(fg_color=C.BG)
        self.resizable(False, False)
        self.geometry(f"{width}x1")  # height is set by content in _fit()
        self._width = width
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(60, self._modal)

    def _fit(self) -> None:
        self.update_idletasks()
        h = self.winfo_reqheight()
        try:  # center over the main window
            x = self.master.winfo_rootx() + max(0, (self.master.winfo_width() - self._width) // 2)
            y = self.master.winfo_rooty() + max(0, (self.master.winfo_height() - h) // 3)
            self.geometry(f"{self._width}x{h}+{x}+{y}")
        except Exception:  # noqa: BLE001
            self.geometry(f"{self._width}x{h}")

    def _modal(self) -> None:
        try:
            self.transient(self.master)
            self.grab_set()
            self.focus_force()
        except Exception:  # noqa: BLE001 - grab can fail while the window is not yet viewable
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()


class FormDialog(_Modal):
    """fields = [(key, placeholder, secret)]. validate(values)->error|None runs first; work(values) runs in the
    worker pool; errors are shown inline so the user can retry without losing the dialog."""

    def __init__(self, app: Any, title: str, intro: str, fields: list[tuple[str, str, bool]], submit_text: str,
                 work: Callable[[dict], Any], on_success: Callable[[Any], None],
                 validate: Callable[[dict], str | None] | None = None) -> None:
        super().__init__(app, title)
        self._work, self._ok, self._validate = work, on_success, validate
        box = ctk.CTkFrame(self, fg_color=C.NAVY_DEEP, border_width=1, border_color=C.BORDER, corner_radius=10)
        box.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkLabel(box, text=title, font=C.font(15, "bold"), text_color=C.TEXT).pack(anchor="w", padx=14, pady=(12, 2))
        if intro:
            ctk.CTkLabel(box, text=intro, font=C.font(11), text_color=C.MUTED, wraplength=380, justify="left"
                         ).pack(anchor="w", padx=14, pady=(0, 8))
        self.entries: dict[str, ctk.CTkEntry] = {}
        for key, ph, secret in fields:
            e = ctk.CTkEntry(box, placeholder_text=ph, show="•" if secret else None, height=36, fg_color=C.NAVY_BTN,
                             border_color=C.BORDER, font=C.font(12))
            e.pack(fill="x", padx=14, pady=4)
            e.bind("<Return>", lambda _e: self.submit())
            self.entries[key] = e
        self.btn = ctk.CTkButton(box, text=submit_text, height=36, font=C.font(12, "bold"), fg_color=C.BLUE,
                                 hover_color=C.BLUE_HOVER, command=self.submit)
        self.btn.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkButton(box, text="Batal", height=34, font=C.font(12, "bold"), fg_color=C.NAVY_BTN,
                      hover_color=C.NAVY_BTN_HOVER, text_color=C.TEXT, command=self.close).pack(fill="x", padx=14, pady=(0, 6))
        self.msg = ctk.CTkLabel(box, text="", font=C.font(11), text_color=C.ERR, wraplength=380, justify="left")
        self.msg.pack(anchor="w", padx=14, pady=(0, 12))
        self._fit()
        if self.entries:
            self.after(120, next(iter(self.entries.values())).focus_set)

    def values(self) -> dict:
        return {k: e.get() for k, e in self.entries.items()}

    def submit(self) -> None:
        vals = self.values()
        problem = self._validate(vals) if self._validate else None
        if problem:
            self.msg.configure(text=problem, text_color=C.ERR)
            return
        self.btn.configure(state="disabled")
        self.msg.configure(text="Memproses…", text_color=C.MUTED)

        def ok(result: Any) -> None:
            if self._closed:
                return
            self.close()
            self._ok(result)

        def err(exc: BaseException) -> None:
            if self._closed:
                return
            self.btn.configure(state="normal")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self.app.run(lambda: self._work(vals), ok, err)


class RecoveryCodeDialog(_Modal):
    def __init__(self, app: Any, code: str, intro: str) -> None:
        super().__init__(app, "Kode Pemulihan", 460)
        box = ctk.CTkFrame(self, fg_color=C.NAVY_DEEP, border_width=1, border_color=C.BORDER, corner_radius=10)
        box.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkLabel(box, text="Simpan Kode Pemulihan Anda", font=C.font(15, "bold"), text_color=C.TEXT
                     ).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(box, text=intro, font=C.font(11), text_color=C.MUTED, wraplength=410, justify="left"
                     ).pack(anchor="w", padx=14, pady=(0, 8))
        self.code = code
        ctk.CTkLabel(box, text=code, font=ctk.CTkFont(family="Consolas", size=22, weight="bold"), text_color=C.TEXT,
                     fg_color=C.NAVY_BTN, corner_radius=8, height=56).pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(box, text="Kode hanya ditampilkan sekali dan hanya bisa dipakai satu kali. Simpan di tempat "
                     "aman (bukan di komputer ini saja).", font=C.font(11), text_color=C.WARN, wraplength=410,
                     justify="left").pack(anchor="w", padx=14, pady=(2, 6))
        self.copy_btn = ctk.CTkButton(box, text="Salin Kode", height=36, font=C.font(12, "bold"), fg_color=C.NAVY_BTN,
                                      hover_color=C.NAVY_BTN_HOVER, text_color=C.TEXT, command=self.copy)
        self.copy_btn.pack(fill="x", padx=14, pady=(4, 4))
        ctk.CTkButton(box, text="Saya sudah menyimpan kode ini", height=36, font=C.font(12, "bold"), fg_color=C.BLUE,
                      hover_color=C.BLUE_HOVER, command=self.close).pack(fill="x", padx=14, pady=(0, 14))
        self._fit()

    def copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.code)
        self.copy_btn.configure(text="Tersalin ✓")


def frame_to_image(frame: Any, max_size: tuple[int, int]) -> Any | None:
    """BGR ndarray -> mirrored PIL image for the preview; None for anything that is not a real camera frame."""
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


class FaceEnrollDialog(_Modal):
    """Live webcam preview. 'Ambil & Daftarkan' grabs frames from the running stream and hands them to the
    existing BiometricService (same embedding/encryption pipeline as before)."""
    PREVIEW = (440, 330)

    def __init__(self, app: Any, on_done: Callable[[], None]) -> None:
        super().__init__(app, "Daftarkan / Perbarui Wajah", 480)
        from sentinel.services.biometric_service import ENROLL_FRAMES
        self._frames_needed, self._on_done = ENROLL_FRAMES, on_done
        self._stream: Any = None
        self._img: Any = None
        box = ctk.CTkFrame(self, fg_color=C.NAVY_DEEP, border_width=1, border_color=C.BORDER, corner_radius=10)
        box.pack(fill="both", expand=True, padx=14, pady=14)
        self.view = ctk.CTkLabel(box, text="Membuka kamera…", width=self.PREVIEW[0], height=self.PREVIEW[1],
                                 fg_color="#05080f", corner_radius=8, text_color=C.MUTED)
        self.view.pack(padx=14, pady=(14, 8))
        ctk.CTkLabel(box, text="Hadap kamera dengan pencahayaan cukup; hanya satu wajah yang boleh terlihat. "
                     f"{self._frames_needed} frame diambil; hanya embedding terenkripsi yang disimpan, bukan foto.",
                     font=C.font(11), text_color=C.MUTED, wraplength=430, justify="left").pack(anchor="w", padx=14)
        self.btn = ctk.CTkButton(box, text="Ambil & Daftarkan", height=36, font=C.font(12, "bold"), fg_color=C.BLUE,
                                 hover_color=C.BLUE_HOVER, state="disabled", command=self.capture)
        self.btn.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkButton(box, text="Batal", height=34, font=C.font(12, "bold"), fg_color=C.NAVY_BTN,
                      hover_color=C.NAVY_BTN_HOVER, text_color=C.TEXT, command=self.close).pack(fill="x", padx=14, pady=(0, 6))
        self.msg = ctk.CTkLabel(box, text="", font=C.font(11), text_color=C.MUTED, wraplength=430, justify="left")
        self.msg.pack(anchor="w", padx=14, pady=(0, 12))
        self._fit()
        ctx, user = app.ctx, app.user
        app.run(lambda: ctx.biometric.open_preview(user), self._opened, self._open_failed)

    def _opened(self, stream: Any) -> None:
        if self._closed:  # dialog was closed while the camera was opening
            self.app.run(stream.close)
            return
        self._stream = stream
        self.btn.configure(state="normal")
        self._tick()

    def _open_failed(self, exc: BaseException) -> None:
        if not self._closed:
            self.view.configure(text="Kamera tidak tersedia")
            self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)

    def _tick(self) -> None:
        if self._closed or self._stream is None:
            return
        img = frame_to_image(self._stream.latest(), self.PREVIEW)
        if img is not None:
            self._img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.view.configure(image=self._img, text="")
        elif self._img is None:
            self.view.configure(text="Pratinjau tidak tersedia")
        self.after(40, self._tick)

    def capture(self) -> None:
        self.btn.configure(state="disabled")
        self.msg.configure(text="Mengambil frame dan memproses wajah… (pertama kali dapat lebih lama)", text_color=C.MUTED)
        ctx, user, stream, n = self.app.ctx, self.app.user, self._stream, self._frames_needed

        def work() -> None:
            ctx.biometric.enroll_from_frames(user, stream.grab(n, 0.4))

        def ok(_r: Any) -> None:
            if not self._closed:
                self.close()
                self._on_done()

        def err(exc: BaseException) -> None:
            if not self._closed:
                self.btn.configure(state="normal")
                self.msg.configure(text=self.app.describe_error(exc), text_color=C.ERR)
        self.app.run(work, ok, err)

    def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            self.app.run(stream.close)  # joining the camera thread must not block the Tk thread
        super().close()
