from __future__ import annotations

import re
import uuid

from sentinel.database.connection import Database
from sentinel.database.repositories import UserRepo
from sentinel.security.password_hasher import PasswordHasher
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import ROLES, Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import NotFoundError, ValidationError
from sentinel.utils.timeutil import now_iso

_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValidationError(f"Password minimal {MIN_PASSWORD} karakter.")


def public_user(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "username", "full_name", "role", "status", "created_at", "last_login_at")}


class UserService:
    def __init__(self, db: Database, repo: UserRepo, hasher: PasswordHasher, perms: PermissionService,
                 audit: AuditService) -> None:
        self._db, self._repo, self._hasher, self._perms, self._audit = db, repo, hasher, perms, audit

    def _new_row(self, username: str, full_name: str, password: str, role: str) -> dict:
        username, full_name = username.strip(), full_name.strip()
        if not _USERNAME.match(username):
            raise ValidationError("Username 3-32 karakter: huruf, angka, titik, garis bawah, atau strip.")
        if not full_name:
            raise ValidationError("Nama lengkap wajib diisi.")
        if role not in ROLES:
            raise ValidationError("Role tidak valid.")
        _check_password(password)
        if self._repo.get_by_username(username):
            raise ValidationError("Username sudah dipakai.")
        return {"id": str(uuid.uuid4()), "username": username, "password_hash": self._hasher.hash(password),
                "full_name": full_name, "role": role, "status": "ACTIVE", "created_at": now_iso()}

    def create_initial_admin(self, username: str, full_name: str, password: str) -> CurrentUser:
        """First-run only: allowed solely while the users table is empty."""
        if self._repo.count() != 0:
            raise ValidationError("Admin pertama sudah dibuat.")
        row = self._new_row(username, full_name, password, "ADMIN")
        with self._db.transaction():
            self._repo.insert(row)
            self._audit.record("USER_CREATED", actor_id=row["id"], target_type="user", target_id=row["id"],
                               details={"role": "ADMIN", "initial_admin": True})
        return CurrentUser(row["id"], row["username"], row["full_name"], "ADMIN")

    def create_user(self, actor: CurrentUser, username: str, full_name: str, password: str, role: str) -> dict:
        actor = self._perms.authorize(actor, Action.MANAGE_USERS)
        row = self._new_row(username, full_name, password, role)
        with self._db.transaction():
            self._repo.insert(row)
            self._audit.record("USER_CREATED", actor_id=actor.id, target_type="user", target_id=row["id"],
                               details={"role": role})
        return public_user(row)

    def list_users(self, actor: CurrentUser) -> list[dict]:
        self._perms.authorize(actor, Action.MANAGE_USERS)
        return [public_user(r) for r in self._repo.list()]

    def list_recipients(self, actor: CurrentUser) -> list[dict]:
        """Active accounts that may receive messages (everyone except Auditors and the caller)."""
        self._perms.authorize(actor, Action.SEND_MESSAGE)
        return [public_user(r) for r in self._repo.list()
                if r["status"] == "ACTIVE" and r["role"] != "AUDITOR" and r["id"] != actor.id]

    def list_analysts(self, actor: CurrentUser) -> list[dict]:
        self._perms.authorize(actor, Action.ASSIGN_ANALYST)
        return [public_user(r) for r in self._repo.by_role("FORENSIC_ANALYST")]

    def update_user(self, actor: CurrentUser, user_id: str, *, full_name: str | None = None,
                    role: str | None = None, status: str | None = None, new_password: str | None = None) -> dict:
        actor = self._perms.authorize(actor, Action.MANAGE_USERS)
        target = self._repo.get(user_id)
        if target is None:
            raise NotFoundError("Pengguna tidak ditemukan.")
        fields: dict = {}
        if full_name is not None and full_name.strip():
            fields["full_name"] = full_name.strip()
        if role is not None and role != target["role"]:
            if role not in ROLES:
                raise ValidationError("Role tidak valid.")
            fields["role"] = role
        if status is not None and status != target["status"]:
            if status not in ("ACTIVE", "DISABLED"):
                raise ValidationError("Status tidak valid.")
            fields["status"] = status
            if status == "ACTIVE":
                fields.update(failed_attempts=0, locked_until=None)
        if new_password:
            _check_password(new_password)
            fields["password_hash"] = self._hasher.hash(new_password)
            fields.update(failed_attempts=0, locked_until=None)
        if not fields:
            return public_user(target)
        losing_admin = target["role"] == "ADMIN" and target["status"] == "ACTIVE" and (
            fields.get("role", "ADMIN") != "ADMIN" or fields.get("status", "ACTIVE") != "ACTIVE")
        with self._db.transaction():
            if losing_admin and self._repo.count_active_admins() <= 1:
                raise ValidationError("Tidak boleh menghapus/menonaktifkan Admin aktif terakhir.")
            self._repo.update(user_id, **fields)
            self._audit.record("USER_UPDATED", actor_id=actor.id, target_type="user", target_id=user_id,
                               details={"changed": sorted(k.replace("password_hash", "credential") for k in fields)})
        return public_user(self._repo.get(user_id))
