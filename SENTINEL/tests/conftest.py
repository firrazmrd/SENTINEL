from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from config import Settings
from sentinel import bootstrap
from sentinel.devices.usb_windows import DriveInfo
from sentinel.services.permission_service import CurrentUser
from sentinel.utils.exceptions import BiometricError

PASSWORD = "Correct-Horse-9"


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self.store: dict = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


class FakeUsb:
    def __init__(self, mount: Path) -> None:
        self.mount = mount
        self.drives = [DriveInfo(str(mount) + "/", "DEMO", "AABBCCDD")]

    def list_drives(self):
        return list(self.drives)


class FakeStream:
    def __init__(self, cam) -> None:
        self.cam, self.closed = cam, False

    def latest(self):
        return self.cam.frames[0] if self.cam.frames else None

    def grab(self, count, interval=0.4):
        return list(self.cam.frames[:count])

    def close(self):
        self.closed = True


class FakeCamera:
    def __init__(self) -> None:
        self.frames = ["alice"] * 3

    def open_stream(self):
        if getattr(self, "fail_open", False):
            from sentinel.utils.exceptions import DeviceError
            raise DeviceError("Kamera tidak dapat dibuka (uji).")
        self.opened = getattr(self, "opened", 0) + 1
        st = FakeStream(self)
        self.streams = getattr(self, "streams", []) + [st]
        return st

    def capture_frames(self, count=1, interval=0.4):
        return list(self.frames[:count]) if len(self.frames) >= count else list(self.frames)


class FakeFace:
    model_name, detector_backend, distance_metric = "ArcFace", "opencv", "cosine"

    def _vec(self, seed: str) -> list[float]:
        rnd = random.Random(hashlib.sha256(seed.encode()).digest())
        return [rnd.gauss(0, 1) for _ in range(512)]

    def embed(self, frame):
        if frame == "noface":
            raise BiometricError("Wajah tidak terdeteksi.")
        if frame == "two":
            raise BiometricError("Harus tepat satu wajah; terdeteksi 2.")
        base, _, noise = frame.partition("+")
        v = self._vec(base)
        if noise:
            n = self._vec("noise" + noise)
            v = [a + 0.05 * b for a, b in zip(v, n)]
        return v

    def threshold(self):
        return 0.68, "fake-test-engine"

    def version(self):
        return "test"


@dataclass
class Env:
    ctx: object
    settings: Settings
    admin: CurrentUser
    usb: FakeUsb
    camera: FakeCamera
    tmp: Path

    def make_user(self, role: str, username: str | None = None) -> CurrentUser:
        username = username or f"{role.lower()}_{random.randint(1000, 9999)}"
        self.ctx.users.create_user(self.admin, username, username.title(), PASSWORD, role)
        return self.ctx.auth.login(username, PASSWORD)


@pytest.fixture
def env(tmp_path):
    keyring.set_keyring(MemoryKeyring())
    usb_dir = tmp_path / "usb"
    usb_dir.mkdir()
    settings = Settings(data_dir=tmp_path / "data", deepface_home=tmp_path / "models", lockout_seconds=30)
    usb, cam = FakeUsb(usb_dir), FakeCamera()
    devices = bootstrap.Devices(usb, cam, FakeFace())
    ctx, admin = bootstrap.first_run(settings, "admin", "Admin Utama", PASSWORD, devices)
    ctx.usb.register(admin, usb.drives[0])
    yield Env(ctx, settings, admin, usb, cam, tmp_path)
    ctx.close()
