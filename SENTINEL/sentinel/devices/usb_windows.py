"""Removable-drive detection on Windows via kernel32 (ctypes; no pywin32 needed)."""
from __future__ import annotations

import string
import sys
from dataclasses import dataclass
from typing import Protocol

DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3


@dataclass(frozen=True)
class DriveInfo:
    mount: str      # e.g. "E:\\"
    label: str
    volume_id: str  # volume serial number, hex

    def display(self) -> str:
        return f"{self.mount} [{self.label or 'tanpa label'}] serial {self.volume_id}"


class UsbDetector(Protocol):
    def list_drives(self) -> list[DriveInfo]: ...


class WindowsUsbDetector:
    def __init__(self, include_fixed: bool = False) -> None:
        self._include_fixed = include_fixed

    def list_drives(self) -> list[DriveInfo]:
        if sys.platform != "win32":
            return []
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        old_mode = k32.SetErrorMode(0x0001)  # SEM_FAILCRITICALERRORS: no "insert disk" dialogs
        drives: list[DriveInfo] = []
        try:
            mask = k32.GetLogicalDrives()
            for i, letter in enumerate(string.ascii_uppercase):
                if not mask & (1 << i):
                    continue
                root = f"{letter}:\\"
                dtype = k32.GetDriveTypeW(root)
                ok_type = dtype == DRIVE_REMOVABLE or (self._include_fixed and dtype == DRIVE_FIXED and letter != "C")
                if not ok_type:
                    continue
                label, fs = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(261)
                serial, maxlen, flags = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                if k32.GetVolumeInformationW(root, label, 261, ctypes.byref(serial), ctypes.byref(maxlen),
                                             ctypes.byref(flags), fs, 261):
                    drives.append(DriveInfo(root, label.value, f"{serial.value:08X}"))
        finally:
            k32.SetErrorMode(old_mode)
        return drives
