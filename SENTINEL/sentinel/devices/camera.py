"""Webcam capture. Frames stay in memory only; the camera opens only when a biometric action asks for it."""
from __future__ import annotations

import time
from typing import Any, Protocol

from sentinel.utils.exceptions import DeviceError


class CameraSource(Protocol):
    def capture_frames(self, count: int = 1, interval: float = 0.4) -> list[Any]: ...


class OpenCvCamera:
    def __init__(self, index: int = 0) -> None:
        self._index = index

    def capture_frames(self, count: int = 1, interval: float = 0.4) -> list[Any]:
        try:
            import cv2
        except ImportError as exc:
            raise DeviceError("OpenCV belum terpasang. Pasang requirements-biometric.txt.") from exc
        cap = None
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):  # DSHOW first: MSMF can open slowly
            cap = cv2.VideoCapture(self._index, backend)
            if cap.isOpened():
                break
            cap.release()
            cap = None
        if cap is None:
            raise DeviceError("Kamera tidak dapat dibuka. Periksa koneksi kamera dan izin privasi kamera Windows.")
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
