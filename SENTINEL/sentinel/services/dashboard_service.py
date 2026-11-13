from __future__ import annotations

from sentinel.database.repositories import AuditRepo, CaseRepo, EvidenceRepo, MessageRepo, UserRepo
from sentinel.services.permission_service import Action, CurrentUser, PermissionService


class DashboardService:
    def __init__(self, cases: CaseRepo, evidence: EvidenceRepo, messages: MessageRepo, audit: AuditRepo,
                 users: UserRepo, perms: PermissionService, ledger=None, usb=None, bio=None) -> None:
        self._cases, self._evidence, self._messages = cases, evidence, messages
        self._audit, self._users, self._perms = audit, users, perms
        self._ledger, self._usb, self._bio = ledger, usb, bio

    def security_overview(self, actor: CurrentUser) -> dict:
        """Read-only snapshot for the dashboard status panels (no secrets, nothing that needs a key)."""
        actor = self._perms.authorize(actor, Action.VIEW_OWN_CASES)
        row = self._users.get(actor.id)
        scope = self._perms.case_scope(actor)
        usb = self._usb.check()
        chain = self._ledger.check_chain()
        return {
            "user": {"username": row["username"], "full_name": row["full_name"], "role": row["role"],
                     "last_login_at": row["last_login_at"], "created_at": row["created_at"]},
            "auth": {"require_face": bool(row["require_face"]), "require_usb": bool(row["require_usb"]),
                     "has_face": self._bio.has_template(actor.id), "has_recovery_code": bool(row["recovery_code_hash"])},
            "usb": {"state": usb.state, "message": usb.message},
            "ledger": {"valid": chain.valid, "blocks": chain.blocks_checked, "reason": chain.reason,
                       "first_invalid_index": chain.first_invalid_index},
            "evidence_status": self._evidence.status_counts(scope, actor.id),
        }

    def summary(self, actor: CurrentUser) -> dict:
        actor = self._perms.authorize(actor, Action.VIEW_OWN_CASES)
        scope = self._perms.case_scope(actor)
        out: dict = {
            "cases": len(self._cases.list(scope, actor.id)),
            "evidence": self._evidence.count_visible(scope, actor.id),
        }
        if self._perms.role_allows(actor.role, Action.READ_MESSAGE):
            out["unread_messages"] = self._messages.unread_count(actor.id)
        if scope == "all":
            out["audit_events"] = self._audit.count()
        if actor.role == "ADMIN":
            out["users"] = self._users.count()
        return out
