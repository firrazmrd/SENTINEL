"""Login = password (Argon2id) + USB + optional face verification. Session state lives in the UI layer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel.database.connection import Database
from sentinel.database.repositories import UserRepo
from sentinel.security import recovery_code
from sentinel.security.password_hasher import PasswordHasher
from sentinel.services.audit_service import AuditService
from sentinel.services.biometric_service import BiometricService
from sentinel.services.permission_service import ADMIN, CurrentUser
from sentinel.services.usb_service import UsbService
from sentinel.services.user_service import check_password_policy
from sentinel.utils.exceptions import AccountLockedError, AuthenticationError, BiometricError, UsbValidationError
from sentinel.utils.timeutil import now_iso, parse_iso

GENERIC_FAIL = "Username atau password salah."
RECOVERY_FAIL = "Username atau kode pemulihan salah."


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

    def _register_failure(self, user: dict, stage: str, reason: str) -> None:
        attempts = user["failed_attempts"] + 1
        fields: dict = {"failed_attempts": attempts}
        if attempts >= self._max:
            until = datetime.now(timezone.utc) + timedelta(seconds=self._lockout)
            fields.update(failed_attempts=0, locked_until=until.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        with self._db.transaction():
            self._users.update(user["id"], **fields)
            self._fail(user, stage, reason)

    def _raise_if_locked(self, user: dict, stage: str) -> None:
        if user["locked_until"] and parse_iso(user["locked_until"]) > datetime.now(timezone.utc):
            remaining = int((parse_iso(user["locked_until"]) - datetime.now(timezone.utc)).total_seconds()) + 1
            self._fail(user, stage, "locked")
            raise AccountLockedError(f"Terlalu banyak percobaan gagal. Coba lagi dalam {remaining} detik.")

    def login(self, username: str, password: str, on_stage=None, on_stream=None) -> CurrentUser:
        """Password always; USB and face only when THIS account's stored settings require them (Settings page)."""
        user = self._users.get_by_username(username.strip())
        if user is None:
            self._hasher.burn_time(password)
            self._fail(None, "password", "unknown_user")
            raise AuthenticationError(GENERIC_FAIL)

        self._raise_if_locked(user, "password")

        if not self._hasher.verify(user["password_hash"], password):
            self._register_failure(user, "password", "bad_password")
            raise AuthenticationError(GENERIC_FAIL)

        if user["status"] != "ACTIVE":
            self._fail(user, "account", "disabled")
            raise AuthenticationError("Akun dinonaktifkan. Hubungi Admin.")

        usb_mode = "NOT_REQUIRED"
        if user["require_usb"]:
            try:
                self._usb.validate_for_login()
            except UsbValidationError:
                self._fail(user, "usb", "usb_invalid")
                raise
            usb_mode = "VERIFIED"

        face_mode = "NOT_REQUIRED"
        if user["require_face"]:
            try:
                self._bio.verify(user["id"], on_stage, on_stream)
            except BiometricError:
                self._fail(user, "biometric", "face_failed")
                raise
            face_mode = "VERIFIED"

        with self._db.transaction():
            fields = {"failed_attempts": 0, "locked_until": None, "last_login_at": now_iso()}
            if self._hasher.needs_rehash(user["password_hash"]):
                fields["password_hash"] = self._hasher.hash(password)
            self._users.update(user["id"], **fields)
            self._audit.record("LOGIN_SUCCESS", actor_id=user["id"], details={"biometric": face_mode, "usb": usb_mode})
        return CurrentUser(user["id"], user["username"], user["full_name"], user["role"])

    def reset_password_with_recovery_code(self, username: str, code: str, new_password: str) -> str:
        """Forgot-password path (no session). The code is single-use: success rotates it and returns the NEW
        code, which the caller must show once. Does not bypass USB/face at the next login."""
        user = self._users.get_by_username(username.strip())
        check_password_policy(new_password)  # a typo in the new password must not burn the code
        stored = user["recovery_code_hash"] if user else None
        if user is None or user["status"] != "ACTIVE" or not stored or not recovery_code.is_well_formed(code):
            self._hasher.burn_time(code or "")
            self._fail(user, "recovery", "unavailable")
            raise AuthenticationError(RECOVERY_FAIL)
        self._raise_if_locked(user, "recovery")
        if not self._hasher.verify(stored, recovery_code.normalize(code)):
            self._register_failure(user, "recovery", "bad_code")
            raise AuthenticationError(RECOVERY_FAIL)
        fresh = recovery_code.generate()
        with self._db.transaction():
            self._users.update(user["id"], password_hash=self._hasher.hash(new_password),
                               recovery_code_hash=self._hasher.hash(recovery_code.normalize(fresh)),
                               recovery_code_created_at=now_iso(), failed_attempts=0, locked_until=None)
            self._audit.record("PASSWORD_RESET_RECOVERY", actor_id=user["id"], target_type="user",
                               target_id=user["id"], details={"recovery_code_rotated": True})
        return fresh

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
