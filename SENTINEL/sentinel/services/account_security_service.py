"""Self-service account security (Settings page): required login factors, password change, recovery code.

Every method acts on the *caller's own* account. Sensitive changes re-check the current password and share the
login lockout counters, so an unattended session cannot be used to guess the password or weaken the login."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel.database.connection import Database
from sentinel.database.repositories import BiometricRepo, UsbRepo, UserRepo
from sentinel.security import recovery_code
from sentinel.security.password_hasher import PasswordHasher
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.services.user_service import check_password_policy
from sentinel.utils.exceptions import AccountLockedError, AuthenticationError, ValidationError
from sentinel.utils.timeutil import now_iso, parse_iso


class AccountSecurityService:
    def __init__(self, db: Database, users: UserRepo, bio: BiometricRepo, usb: UsbRepo, hasher: PasswordHasher,
                 perms: PermissionService, audit: AuditService, max_attempts: int, lockout_seconds: int) -> None:
        self._db, self._users, self._bio, self._usb = db, users, bio, usb
        self._hasher, self._perms, self._audit = hasher, perms, audit
        self._max, self._lockout = max_attempts, lockout_seconds

    # -- read ------------------------------------------------------------------
    def overview(self, actor: CurrentUser) -> dict:
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_SECURITY)
        row = self._users.get(actor.id)
        return {
            "has_face": self._bio.get(actor.id) is not None,
            "usb_registered": self._usb.active() is not None,
            "require_face": bool(row["require_face"]),
            "require_usb": bool(row["require_usb"]),
            "has_recovery_code": bool(row["recovery_code_hash"]),
            "recovery_code_created_at": row["recovery_code_created_at"],
            "can_manage_usb": PermissionService.role_allows(actor.role, Action.MANAGE_USB),
        }

    # -- re-authentication --------------------------------------------------------
    def _confirm_password(self, row: dict, password: str | None, purpose: str) -> None:
        until = row["locked_until"]
        if until and parse_iso(until) > datetime.now(timezone.utc):
            raise AccountLockedError("Terlalu banyak percobaan gagal. Coba lagi beberapa saat lagi.")
        if password and self._hasher.verify(row["password_hash"], password):
            return
        attempts = row["failed_attempts"] + 1
        fields: dict = {"failed_attempts": attempts}
        if attempts >= self._max:
            lock = datetime.now(timezone.utc) + timedelta(seconds=self._lockout)
            fields.update(failed_attempts=0, locked_until=lock.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        with self._db.transaction():
            self._users.update(row["id"], **fields)
            self._audit.record("REAUTH_FAILED", actor_id=row["id"], details={"purpose": purpose})
        raise AuthenticationError("Password saat ini salah.")

    # -- required login factors -----------------------------------------------------
    def apply_auth_requirements(self, actor: CurrentUser, *, require_face: bool, require_usb: bool,
                                current_password: str | None = None) -> dict:
        """Persist which factors this account must pass at login. Enabling needs the factor to exist;
        disabling one needs the current password (an open session alone must not weaken the login)."""
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_SECURITY)
        row = self._users.get(actor.id)
        had_face, had_usb = bool(row["require_face"]), bool(row["require_usb"])
        if require_face and not had_face and self._bio.get(actor.id) is None:
            raise ValidationError("Daftarkan wajah terlebih dahulu sebelum mewajibkan verifikasi wajah.")
        if require_usb and not had_usb and self._usb.active() is None:
            raise ValidationError("Belum ada USB dongle terdaftar. Buat USB dongle terlebih dahulu.")
        if (had_face, had_usb) == (require_face, require_usb):
            return self.overview(actor)
        if (had_face and not require_face) or (had_usb and not require_usb):
            self._confirm_password(row, current_password, "weaken_login")
        with self._db.transaction():
            self._users.update(actor.id, require_face=int(require_face), require_usb=int(require_usb))
            self._audit.record("AUTH_REQUIREMENTS_UPDATED", actor_id=actor.id, target_type="user", target_id=actor.id,
                               details={"require_face": require_face, "require_usb": require_usb})
        return self.overview(actor)

    # -- password ----------------------------------------------------------------------
    def change_password(self, actor: CurrentUser, current_password: str, new_password: str) -> None:
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_SECURITY)
        row = self._users.get(actor.id)
        self._confirm_password(row, current_password, "change_password")
        check_password_policy(new_password)
        if new_password == current_password:
            raise ValidationError("Password baru harus berbeda dari password saat ini.")
        with self._db.transaction():
            self._users.update(actor.id, password_hash=self._hasher.hash(new_password),
                               failed_attempts=0, locked_until=None)
            self._audit.record("PASSWORD_CHANGED", actor_id=actor.id, target_type="user", target_id=actor.id)

    # -- recovery code -----------------------------------------------------------------
    def regenerate_recovery_code(self, actor: CurrentUser, current_password: str) -> str:
        """Create a new code and return it (the only time it is visible). The previous code stops working
        immediately because only the newest hash is kept."""
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_SECURITY)
        row = self._users.get(actor.id)
        self._confirm_password(row, current_password, "regenerate_recovery_code")
        code = recovery_code.generate()
        with self._db.transaction():
            self._users.update(actor.id, recovery_code_hash=self._hasher.hash(recovery_code.normalize(code)),
                               recovery_code_created_at=now_iso())
            self._audit.record("RECOVERY_CODE_REGENERATED", actor_id=actor.id, target_type="user", target_id=actor.id,
                               details={"replaced_previous": bool(row["recovery_code_hash"])})
        return code
