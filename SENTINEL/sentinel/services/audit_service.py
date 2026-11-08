"""Single source of audit events; every event is also chained into the ledger in one transaction."""
from __future__ import annotations

import json
import uuid
from typing import Any

from sentinel.database.connection import Database
from sentinel.database.repositories import AuditRepo
from sentinel.services.ledger_service import LedgerService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService

_FORBIDDEN = ("password", "token", "secret", "plaintext", "embedding", "key")


class AuditService:
    def __init__(self, db: Database, repo: AuditRepo, ledger: LedgerService, perms: PermissionService) -> None:
        self._db, self._repo, self._ledger, self._perms = db, repo, ledger, perms

    def record(self, event_type: str, *, actor_id: str | None = None, target_type: str | None = None,
               target_id: str | None = None, case_id: str | None = None,
               details: dict[str, Any] | None = None) -> str:
        details = details or {}
        for k in details:
            if any(bad in k.lower() for bad in _FORBIDDEN):
                raise ValueError(f"Field audit '{k}' dilarang (berpotensi secret/plaintext)")
        from sentinel.utils.timeutil import now_iso
        row = {
            "id": str(uuid.uuid4()), "actor_id": actor_id, "event_type": event_type,
            "target_type": target_type, "target_id": target_id, "case_id": case_id,
            "details_json": json.dumps(details, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            "created_at": now_iso(),
        }
        with self._db.transaction():
            self._repo.insert(row)
            self._ledger.append(row)
        return row["id"]

    def search(self, actor: CurrentUser, *, event_type: str | None = None, actor_id: str | None = None,
               case_id: str | None = None, date_from: str | None = None, date_to: str | None = None,
               limit: int = 300) -> list[dict]:
        actor = self._perms.authorize(actor, Action.VIEW_AUDIT)
        scope = self._perms.case_scope(actor)
        restrict_user = None if scope == "all" else actor.id
        restrict_scope = None if scope == "all" else (scope, actor.id)
        return self._repo.search(
            restrict_user_id=restrict_user, restrict_case_scope=restrict_scope, event_type=event_type,
            actor_id=actor_id, case_id=case_id, date_from=date_from, date_to=date_to, limit=limit)

    def event_types(self, actor: CurrentUser) -> list[str]:
        self._perms.authorize(actor, Action.VIEW_AUDIT)
        return self._repo.event_types()
