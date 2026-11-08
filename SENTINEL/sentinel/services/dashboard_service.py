from __future__ import annotations

from sentinel.database.repositories import AuditRepo, CaseRepo, EvidenceRepo, MessageRepo, UserRepo
from sentinel.services.permission_service import Action, CurrentUser, PermissionService


class DashboardService:
    def __init__(self, cases: CaseRepo, evidence: EvidenceRepo, messages: MessageRepo, audit: AuditRepo,
                 users: UserRepo, perms: PermissionService) -> None:
        self._cases, self._evidence, self._messages = cases, evidence, messages
        self._audit, self._users, self._perms = audit, users, perms

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
