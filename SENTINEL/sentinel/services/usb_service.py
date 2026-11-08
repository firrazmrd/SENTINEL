"""One global USB flash drive acting as a simple possession factor (clonable; not a hardware token)."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

from sentinel.database.connection import Database
from sentinel.database.repositories import UsbRepo
from sentinel.devices.usb_windows import DriveInfo, UsbDetector
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import DeviceError, UsbValidationError, ValidationError
from sentinel.utils.timeutil import now_iso


@dataclass(frozen=True)
class UsbCheck:
    state: str      # NONE_REGISTERED | NO_DRIVE | NOT_VALID | VALID
    message: str
    mount: str | None = None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UsbService:
    def __init__(self, db: Database, repo: UsbRepo, detector: UsbDetector, perms: PermissionService,
                 audit: AuditService, token_filename: str) -> None:
        self._db, self._repo, self._detector = db, repo, detector
        self._perms, self._audit, self._filename = perms, audit, token_filename

    def has_active_device(self) -> bool:
        return self._repo.active() is not None

    def list_drives(self) -> list[DriveInfo]:
        return self._detector.list_drives()

    def active_device(self, actor: CurrentUser) -> dict | None:
        self._perms.authorize(actor, Action.MANAGE_USB)
        dev = self._repo.active()
        return None if dev is None else {k: dev[k] for k in ("id", "label", "volume_identifier", "registered_at", "last_seen_at")}

    # -- registration ------------------------------------------------------
    def register(self, actor: CurrentUser, drive: DriveInfo) -> None:
        actor = self._perms.authorize(actor, Action.MANAGE_USB)
        self._register(actor.id, drive)

    def _register(self, actor_id: str, drive: DriveInfo) -> None:
        if drive.volume_id not in {d.volume_id for d in self._detector.list_drives()}:
            raise DeviceError("Flash drive tidak lagi terdeteksi. Pasang kembali lalu coba lagi.")
        token = secrets.token_hex(32)
        marker = Path(drive.mount) / self._filename
        try:
            marker.write_text(json.dumps({"app": "SENTINEL", "v": 1, "token": token}), encoding="utf-8")
        except OSError as exc:
            raise DeviceError(f"Tidak dapat menulis marker ke flash drive: {exc}") from exc
        with self._db.transaction():
            revoked = self._repo.revoke_all()
            usb_id = str(uuid.uuid4())
            self._repo.insert({"id": usb_id, "token_hash": _hash_token(token),
                               "volume_identifier": drive.volume_id, "label": drive.label,
                               "registered_at": now_iso()})
            self._audit.record("USB_REGISTERED", actor_id=actor_id, target_type="usb", target_id=usb_id,
                               details={"volume": drive.volume_id, "replaced_previous": revoked > 0})

    def revoke(self, actor: CurrentUser) -> None:
        actor = self._perms.authorize(actor, Action.MANAGE_USB)
        with self._db.transaction():
            dev = self._repo.active()
            if dev is None:
                raise ValidationError("Tidak ada USB aktif untuk dicabut.")
            self._repo.revoke_all()
            self._audit.record("USB_REVOKED", actor_id=actor.id, target_type="usb", target_id=dev["id"])

    # -- validation --------------------------------------------------------
    def _read_token(self, mount: str) -> str | None:
        try:
            data = json.loads((Path(mount) / self._filename).read_text(encoding="utf-8"))
            tok = data.get("token")
            return tok if isinstance(tok, str) else None
        except (OSError, ValueError):
            return None

    def check(self) -> UsbCheck:
        """Non-privileged status used by the login screen indicator. Never reveals the token."""
        dev = self._repo.active()
        if dev is None:
            return UsbCheck("NONE_REGISTERED", "Belum ada USB terdaftar.")
        drives = self._detector.list_drives()
        if not drives:
            return UsbCheck("NO_DRIVE", "USB belum terdeteksi.")
        for d in drives:
            token = self._read_token(d.mount)
            if token is None or d.volume_id != dev["volume_identifier"]:
                continue
            if hmac.compare_digest(_hash_token(token), dev["token_hash"]):
                return UsbCheck("VALID", f"USB valid ({d.mount})", d.mount)
        return UsbCheck("NOT_VALID", "Flash drive terdeteksi tetapi tidak terdaftar / marker tidak valid.")

    def validate_for_login(self) -> UsbCheck:
        result = self.check()
        if result.state != "VALID":
            raise UsbValidationError(result.message)
        dev = self._repo.active()
        self._repo.touch(dev["id"], now_iso())
        return result

    def register_when_none_active(self, actor: CurrentUser, drive: DriveInfo) -> None:
        """Setup/recovery path: only allowed while NO usb is active (otherwise use the Admin page)."""
        actor = self._perms.authorize(actor, Action.MANAGE_USB)
        if self.has_active_device():
            raise ValidationError("Sudah ada USB aktif; kelola dari halaman User Management.")
        self._register(actor.id, drive)
