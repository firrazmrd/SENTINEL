"""Wires everything together and implements first-run behaviour (SRS 11.1)."""
from __future__ import annotations

from dataclasses import dataclass

from config import Settings
from sentinel.database import repositories as R
from sentinel.database.connection import Database
from sentinel.devices.camera import CameraSource, OpenCvCamera
from sentinel.devices.face_engine import DeepFaceEngine, FaceEngine
from sentinel.devices.usb_windows import UsbDetector, WindowsUsbDetector
from sentinel.security.biometric_crypto import BiometricCrypto
from sentinel.security.file_crypto import FileCrypto
from sentinel.security.key_manager import KeyManager
from sentinel.security.message_crypto import MessageCrypto
from sentinel.security.password_hasher import PasswordHasher
from sentinel.services.audit_service import AuditService
from sentinel.services.auth_service import AuthService
from sentinel.services.biometric_service import BiometricService
from sentinel.services.case_service import CaseService
from sentinel.services.dashboard_service import DashboardService
from sentinel.services.evidence_service import EvidenceService
from sentinel.services.ledger_service import LedgerService
from sentinel.services.message_service import MessageService
from sentinel.services.permission_service import CurrentUser, PermissionService
from sentinel.services.steganography_service import SteganographyService
from sentinel.services.usb_service import UsbService
from sentinel.services.user_service import UserService
from sentinel.utils.exceptions import KeyMissingError, StartupError
from sentinel.utils.timeutil import now_iso


@dataclass
class Devices:
    usb: UsbDetector
    camera: CameraSource
    face: FaceEngine


def default_devices(settings: Settings) -> Devices:
    return Devices(WindowsUsbDetector(settings.usb_include_fixed), OpenCvCamera(settings.camera_index),
                   DeepFaceEngine(settings.face_model, settings.face_detector, settings.face_metric))


class AppContext:
    """Service container. Holds the keys only inside the crypto helpers (loaded from the keyring)."""

    def __init__(self, settings: Settings, keys: KeyManager, db: Database, devices: Devices) -> None:
        self.settings, self.keys, self.db, self.devices = settings, keys, db, devices
        users, usb_r, bio_r = R.UserRepo(db), R.UsbRepo(db), R.BiometricRepo(db)
        cases, evid, msgs = R.CaseRepo(db), R.EvidenceRepo(db), R.MessageRepo(db)
        audit_r, ledger_r, set_r = R.AuditRepo(db), R.LedgerRepo(db), R.SettingsRepo(db)

        self.hasher = PasswordHasher()
        self.perms = PermissionService(users)
        self.ledger = LedgerService(ledger_r, self.perms)
        self.audit = AuditService(db, audit_r, self.ledger, self.perms)
        self.ledger.bind_audit(self.audit)
        msg_crypto = MessageCrypto(keys.get("message_key"), settings.vigenere_key)
        self.users = UserService(db, users, self.hasher, self.perms, self.audit)
        self.usb = UsbService(db, usb_r, devices.usb, self.perms, self.audit, settings.usb_token_filename)
        self.biometric = BiometricService(db, bio_r, set_r, BiometricCrypto(keys.get("biometric_key")),
                                          devices.face, devices.camera, self.perms, self.audit, users)
        self.auth = AuthService(db, users, self.hasher, self.usb, self.biometric, self.audit,
                                settings.max_login_attempts, settings.lockout_seconds)
        self.cases = CaseService(db, cases, users, self.perms, self.audit)
        self.evidence = EvidenceService(db, evid, cases, FileCrypto(keys.get("file_key")), self.perms, self.audit,
                                        settings.evidence_dir, settings.max_file_bytes, _ext(settings))
        self.messages = MessageService(db, msgs, users, cases, msg_crypto, self.perms, self.audit)
        self.stego = SteganographyService(db, R.StegoRepo(db), cases, msg_crypto, self.perms, self.audit)
        self.dashboard = DashboardService(cases, evid, msgs, audit_r, users, self.perms)
        self._users_repo = users

    def needs_usb_setup(self) -> bool:
        """DB + admin exist but no USB is registered (interrupted first-run, or USB revoked)."""
        return self._users_repo.count() > 0 and not self.usb.has_active_device()

    def close(self) -> None:
        self.db.close_all()


def _ext(settings: Settings) -> tuple[str, ...]:
    from config import ALLOWED_EXTENSIONS
    return ALLOWED_EXTENSIONS


def is_first_run(settings: Settings) -> bool:
    return not settings.db_path.exists()


def open_existing(settings: Settings, devices: Devices | None = None) -> AppContext:
    """Open an existing installation. Never creates or overwrites a database."""
    settings.ensure_dirs()
    keys = KeyManager(settings.keyring_service)
    keys.ensure_backend()
    missing = keys.missing()
    if missing:
        raise KeyMissingError(
            "Database ditemukan tetapi key berikut hilang dari keyring: " + ", ".join(missing) +
            ". Data terenkripsi tidak dapat dibuka dan database TIDAK ditimpa. Pulihkan keyring Windows "
            "yang sama atau pindahkan folder data lama sebelum setup ulang.")
    db = Database(settings.db_path, keys.get("db_key"))
    db.conn()  # fail fast: verifies SQLCipher + key
    return AppContext(settings, keys, db, devices or default_devices(settings))


def first_run(settings: Settings, username: str, full_name: str, password: str,
              devices: Devices | None = None) -> tuple[AppContext, CurrentUser]:
    """Steps 1-5 and 8 of SRS 11.1. USB registration is the wizard's next step (needs the Admin object)."""
    if settings.db_path.exists():
        raise StartupError("Database sudah ada; first-run tidak dijalankan ulang.")
    settings.ensure_dirs()
    keys = KeyManager(settings.keyring_service)
    keys.ensure_backend()
    if keys.has_any():
        if any(settings.evidence_dir.rglob("*.sntenc")):
            raise StartupError("Key lama ada di keyring dan folder evidence berisi data; setup baru dibatalkan "
                               "agar data lama tidak menjadi tidak terbaca.")
        keys.generate_all(overwrite=True)  # leftovers from an aborted setup with no data
    else:
        keys.generate_all()
    db = Database(settings.db_path, keys.get("db_key"))
    db.init_schema()
    ctx = AppContext(settings, keys, db, devices or default_devices(settings))
    ctx.audit.record("LEDGER_GENESIS", details={"note": "genesis block"})
    admin = ctx.users.create_initial_admin(username, full_name, password)
    R.SettingsRepo(db).set("schema_version", "1", now_iso())
    ctx.audit.record("FIRST_RUN_COMPLETED", actor_id=admin.id)
    return ctx, admin


def open_or_first_run_state(settings: Settings) -> str:
    return "FIRST_RUN" if is_first_run(settings) else "READY"
