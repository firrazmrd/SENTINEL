"""RBAC (SRS 4.2). Every service method calls authorize(); GUI menu hiding is cosmetic only."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from sentinel.database.repositories import UserRepo
from sentinel.utils.exceptions import PermissionDeniedError

ADMIN, INVESTIGATOR, ANALYST, AUDITOR = "ADMIN", "INVESTIGATOR", "FORENSIC_ANALYST", "AUDITOR"
ROLES = (ADMIN, INVESTIGATOR, ANALYST, AUDITOR)
ROLE_LABEL = {ADMIN: "Admin", INVESTIGATOR: "Investigator", ANALYST: "Forensic Analyst", AUDITOR: "Auditor"}


class Action(str, Enum):
    VIEW_ALL_CASES = "view_all_cases"
    VIEW_OWN_CASES = "view_own_cases"
    CREATE_CASE = "create_case"
    UPDATE_CASE = "update_case"
    ASSIGN_ANALYST = "assign_analyst"
    UPLOAD_EVIDENCE = "upload_evidence"
    VIEW_EVIDENCE_META = "view_evidence_meta"
    DECRYPT_EVIDENCE = "decrypt_evidence"
    VERIFY_PLAINTEXT = "verify_plaintext"
    VERIFY_CIPHERTEXT = "verify_ciphertext"
    SEND_MESSAGE = "send_message"
    READ_MESSAGE = "read_message"
    USE_STEGO = "use_stego"
    MANAGE_USERS = "manage_users"
    MANAGE_USB = "manage_usb"
    VIEW_AUDIT = "view_audit"
    VERIFY_LEDGER = "verify_ledger"
    MANAGE_OWN_FACE = "manage_own_face"
    RESET_FACE = "reset_face"
    MANAGE_OWN_SECURITY = "manage_own_security"
    ADD_NOTE = "add_note"


_COMMON = {Action.VIEW_OWN_CASES, Action.VERIFY_LEDGER, Action.VIEW_AUDIT, Action.MANAGE_OWN_FACE,
           Action.MANAGE_OWN_SECURITY}
ROLE_ACTIONS: dict[str, frozenset[Action]] = {
    ADMIN: frozenset(_COMMON | {
        Action.VIEW_ALL_CASES, Action.CREATE_CASE, Action.UPDATE_CASE, Action.ASSIGN_ANALYST,
        Action.VIEW_EVIDENCE_META, Action.VERIFY_CIPHERTEXT, Action.SEND_MESSAGE, Action.READ_MESSAGE,
        Action.USE_STEGO, Action.MANAGE_USERS, Action.MANAGE_USB, Action.RESET_FACE}),
    INVESTIGATOR: frozenset(_COMMON | {
        Action.CREATE_CASE, Action.UPDATE_CASE, Action.UPLOAD_EVIDENCE, Action.VIEW_EVIDENCE_META,
        Action.VERIFY_CIPHERTEXT, Action.SEND_MESSAGE, Action.READ_MESSAGE, Action.USE_STEGO}),
    ANALYST: frozenset(_COMMON | {
        Action.VIEW_EVIDENCE_META, Action.DECRYPT_EVIDENCE, Action.VERIFY_PLAINTEXT, Action.VERIFY_CIPHERTEXT,
        Action.SEND_MESSAGE, Action.READ_MESSAGE, Action.USE_STEGO, Action.ADD_NOTE}),
    AUDITOR: frozenset(_COMMON | {
        Action.VIEW_ALL_CASES, Action.VIEW_EVIDENCE_META, Action.VERIFY_CIPHERTEXT}),
}


@dataclass(frozen=True)
class CurrentUser:
    id: str
    username: str
    full_name: str
    role: str

    @property
    def role_label(self) -> str:
        return ROLE_LABEL.get(self.role, self.role)


class PermissionService:
    def __init__(self, users: UserRepo) -> None:
        self._users = users

    @staticmethod
    def role_allows(role: str, action: Action) -> bool:
        return action in ROLE_ACTIONS.get(role, frozenset())

    def authorize(self, actor: CurrentUser | None, action: Action) -> CurrentUser:
        """Re-read the account so a disabled/demoted user is refused even with a stale session."""
        if actor is None:
            raise PermissionDeniedError("Anda harus login.")
        row = self._users.get(actor.id)
        if row is None or row["status"] != "ACTIVE":
            raise PermissionDeniedError("Akun tidak aktif.")
        if action not in ROLE_ACTIONS.get(row["role"], frozenset()):
            raise PermissionDeniedError("Role Anda tidak berhak melakukan tindakan ini.")
        return CurrentUser(row["id"], row["username"], row["full_name"], row["role"])

    @staticmethod
    def case_scope(user: CurrentUser) -> str:
        """'all' (Admin, Auditor), 'created' (Investigator) or 'assigned' (Analyst)."""
        if user.role in (ADMIN, AUDITOR):
            return "all"
        return "created" if user.role == INVESTIGATOR else "assigned"

    def can_view_case(self, user: CurrentUser, case: dict[str, Any]) -> bool:
        scope = self.case_scope(user)
        return (scope == "all"
                or (scope == "created" and case["created_by"] == user.id)
                or (scope == "assigned" and case["assigned_analyst_id"] == user.id))

    def require_case_view(self, user: CurrentUser, case: dict[str, Any] | None) -> None:
        # Same message for "missing" and "not yours" so ids cannot be probed.
        if case is None or not self.can_view_case(user, case):
            raise PermissionDeniedError("Kasus tidak ditemukan atau Anda tidak berhak mengaksesnya.")
