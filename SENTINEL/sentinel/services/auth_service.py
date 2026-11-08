"""Login = password (Argon2id) + USB + optional face verification. Session state lives in the UI layer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel.database.connection import Database
from sentinel.database.repositories import UserRepo
from sentinel.security.password_hasher import PasswordHasher
from sentinel.services.audit_service import AuditService
from sentinel.services.biometric_service import BiometricService
from sentinel.services.permission_service import ADMIN, CurrentUser
from sentinel.services.usb_service import UsbService
from sentinel.utils.exceptions import AccountLockedError, AuthenticationError, BiometricError, UsbValidationError
from sentinel.utils.timeutil import now_iso, parse_iso

GENERIC_FAIL = "Username atau password salah."


class AuthService:
    def __init__(self, db: Database, users: UserRepo, hasher: PasswordHasher, usb: UsbService,
                 biometric: BiometricService, audit: AuditService, max_attempts: int, lockout_seconds: int) -> None:
        self._db, self._users, self._hasher = db, users, hasher
        self._usb, self._bio, self._audit = usb, biometric, audit
        self._max, self._lockout = max_attempts, lockout_seconds

    def _fail(self, user: dict | None, stage: str, reason: str) -> None:
        # Never log the typed username/password: a user may paste a password into the username box.
        self._audit.record("LOGIN_FAILED", actor_id=user["id"] if user else None,
                           details={"stage": stage, "reason": reason})

    def login(self, username: str, password: str, biometric_enabled: bool = True) -> CurrentUser:
        user = self._users.get_by_username(username.strip())
        if user is None:
            self._hasher.burn_time(password)
            self._fail(None, "password", "unknown_user")
            raise AuthenticationError(GENERIC_FAIL)

        if user["locked_until"] and parse_iso(user["locked_until"]) > datetime.now(timezone.utc):
            remaining = int((parse_iso(user["locked_until"]) - datetime.now(timezone.utc)).total_seconds()) + 1
            self._fail(user, "password", "locked")
            raise AccountLockedError(f"Terlalu banyak percobaan gagal. Coba lagi dalam {remaining} detik.")

        if not self._hasher.verify(user["password_hash"], password):
            attempts = user["failed_attempts"] + 1
            fields: dict = {"failed_attempts": attempts}
            if attempts >= self._max:
                until = datetime.now(timezone.utc) + timedelta(seconds=self._lockout)
                fields.update(failed_attempts=0, locked_until=until.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
            with self._db.transaction():
                self._users.update(user["id"], **fields)
                self._fail(user, "password", "bad_password")
            raise AuthenticationError(GENERIC_FAIL)

        if user["status"] != "ACTIVE":
            self._fail(user, "account", "disabled")
            raise AuthenticationError("Akun dinonaktifkan. Hubungi Admin.")

        try:
            self._usb.validate_for_login()
        except UsbValidationError:
            self._fail(user, "usb", "usb_invalid")
            raise

        if biometric_enabled:
            try:
                self._bio.verify(user["id"])
            except BiometricError:
                self._fail(user, "biometric", "face_failed")
                raise
            mode = "VERIFIED"
        else:
            self._audit.record("BIOMETRIC_SKIPPED", actor_id=user["id"])
            mode = "SKIPPED"

        with self._db.transaction():
            fields = {"failed_attempts": 0, "locked_until": None, "last_login_at": now_iso()}
            if self._hasher.needs_rehash(user["password_hash"]):
                fields["password_hash"] = self._hasher.hash(password)
            self._users.update(user["id"], **fields)
            self._audit.record("LOGIN_SUCCESS", actor_id=user["id"], details={"biometric": mode})
        return CurrentUser(user["id"], user["username"], user["full_name"], user["role"])

    def logout(self, actor: CurrentUser) -> None:
        self._audit.record("LOGOUT", actor_id=actor.id)

    def verify_admin_credentials(self, username: str, password: str) -> CurrentUser:
        """Password-only check used solely to (re)register the USB when none is active (recovery)."""
        user = self._users.get_by_username(username.strip())
        if user is None or user["status"] != "ACTIVE" or user["role"] != ADMIN \
                or not self._hasher.verify(user["password_hash"], password):
            if user is None:
                self._hasher.burn_time(password)
            raise AuthenticationError("Kredensial Admin salah.")
        return CurrentUser(user["id"], user["username"], user["full_name"], user["role"])
