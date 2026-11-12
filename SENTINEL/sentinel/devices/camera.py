"""Webcam capture. Frames stay in memory only; the camera opens only when a biometric action asks for it."""
from __future__ import annotations

import threading
import time
from typing import Any, Protocol

from sentinel.utils.exceptions import DeviceError


class FrameStream(Protocol):
    """A live camera session used for the enrollment preview. `latest()` is cheap and never blocks."""

    def latest(self) -> Any | None: ...
    def grab(self, count: int, interval: float = 0.4) -> list[Any]: ...
    def close(self) -> None: ...


class CameraSource(Protocol):
    def capture_frames(self, count: int = 1, interval: float = 0.4) -> list[Any]: ...
    def open_stream(self) -> FrameStream: ...


def _open_capture(index: int) -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise DeviceError("OpenCV belum terpasang. Pasang requirements-biometric.txt.") from exc
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):  # DSHOW first: MSMF can open slowly
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            return cap
        cap.release()
    raise DeviceError("Kamera tidak dapat dibuka. Periksa koneksi kamera dan izin privasi kamera Windows.")


class OpenCvStream:
    """Reads the camera continuously on a daemon thread so the Tk thread only ever copies the newest frame."""

    def __init__(self, cap: Any) -> None:
        self._cap, self._lock, self._stop = cap, threading.Lock(), threading.Event()
        self._frame: Any | None = None
        self._error: str | None = None
        self._thread = threading.Thread(target=self._loop, name="sentinel-camera", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if ok and frame is not None:
                failures = 0
                with self._lock:
                    self._frame = frame
            else:
                failures += 1
                if failures > 40:
                    self._error = "Kamera berhenti mengirim gambar (terlepas atau dipakai aplikasi lain)."
                    return
            time.sleep(0.02)

    def latest(self) -> Any | None:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def grab(self, count: int, interval: float = 0.4) -> list[Any]:
        frames: list[Any] = []
        for i in range(count):
            deadline = time.monotonic() + 3.0
            frame = self.latest()
            while frame is None:
                if self._error or time.monotonic() > deadline:
                    raise DeviceError(self._error or "Gagal membaca frame dari kamera.")
                time.sleep(0.05)
                frame = self.latest()
            frames.append(frame)
            if i < count - 1:
                time.sleep(interval)
        return frames

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        try:
            self._cap.release()
        except Exception:  # noqa: BLE001
            pass


class OpenCvCamera:
    def __init__(self, index: int = 0) -> None:
        self._index = index

    def open_stream(self) -> FrameStream:
        return OpenCvStream(_open_capture(self._index))

    def capture_frames(self, count: int = 1, interval: float = 0.4) -> list[Any]:
        cap = _open_capture(self._index)
        frames: list[Any] = []
        try:
            for _ in range(8):  # warm-up for auto exposure
                cap.read()
            for i in range(count):
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise DeviceError("Gagal membaca frame dari kamera.")
                frames.append(frame)
                if i < count - 1:
                    time.sleep(interval)
        finally:
            cap.release()
        return frames
