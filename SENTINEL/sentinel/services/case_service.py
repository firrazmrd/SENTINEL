from __future__ import annotations

import uuid

from sentinel.database.connection import Database
from sentinel.database.repositories import CaseRepo, UserRepo
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import INVESTIGATOR, Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from sentinel.utils.timeutil import now_iso

STATUSES = ("OPEN", "IN_REVIEW", "CLOSED")


class CaseService:
    def __init__(self, db: Database, repo: CaseRepo, users: UserRepo, perms: PermissionService,
                 audit: AuditService) -> None:
        self._db, self._repo, self._users, self._perms, self._audit = db, repo, users, perms, audit

    def create_case(self, actor: CurrentUser, title: str, description: str = "") -> dict:
        actor = self._perms.authorize(actor, Action.CREATE_CASE)
        title = title.strip()
        if not title:
            raise ValidationError("Judul kasus wajib diisi.")
        case_id = str(uuid.uuid4())
        with self._db.transaction():
            number = f"CASE-{self._repo.count() + 1:03d}"
            self._repo.insert({"id": case_id, "case_number": number, "title": title,
                               "description": description.strip(), "created_by": actor.id, "now": now_iso()})
            self._audit.record("CASE_CREATED", actor_id=actor.id, target_type="case", target_id=case_id,
                               case_id=case_id, details={"case_number": number})
        return self._repo.get(case_id)

    def list_cases(self, actor: CurrentUser, query: str = "") -> list[dict]:
        actor = self._perms.authorize(actor, Action.VIEW_OWN_CASES)
        return self._repo.list(self._perms.case_scope(actor), actor.id, query.strip())

    def get_case(self, actor: CurrentUser, case_id: str) -> dict:
        actor = self._perms.authorize(actor, Action.VIEW_OWN_CASES)
        case = self._repo.get(case_id)
        self._perms.require_case_view(actor, case)
        return case

    def update_case(self, actor: CurrentUser, case_id: str, *, title: str | None = None,
                    description: str | None = None, status: str | None = None) -> dict:
        actor = self._perms.authorize(actor, Action.UPDATE_CASE)
        case = self._repo.get(case_id)
        self._perms.require_case_view(actor, case)
        if actor.role == INVESTIGATOR and case["status"] != "OPEN":
            raise PermissionDeniedError("Investigator hanya dapat mengubah kasus yang berstatus OPEN.")
        fields: dict = {}
        if title is not None:
            if not title.strip():
                raise ValidationError("Judul kasus wajib diisi.")
            fields["title"] = title.strip()
        if description is not None:
            fields["description"] = description.strip()
        if status is not None:
            if status not in STATUSES:
                raise ValidationError("Status tidak valid.")
            fields["status"] = status
        fields = {k: v for k, v in fields.items() if v != case[k]}
        if not fields:
            return case
        with self._db.transaction():
            self._repo.update(case_id, updated_at=now_iso(), **fields)
            self._audit.record("CASE_UPDATED", actor_id=actor.id, target_type="case", target_id=case_id,
                               case_id=case_id, details={"changed": sorted(fields)})
        return self._repo.get(case_id)

    def assign_analyst(self, actor: CurrentUser, case_id: str, analyst_id: str) -> dict:
        actor = self._perms.authorize(actor, Action.ASSIGN_ANALYST)
        case = self._repo.get(case_id)
        if case is None:
            raise NotFoundError("Kasus tidak ditemukan.")
        analyst = self._users.get(analyst_id)
        if analyst is None or analyst["role"] != "FORENSIC_ANALYST" or analyst["status"] != "ACTIVE":
            raise ValidationError("Pengguna yang dipilih bukan Forensic Analyst aktif.")
        with self._db.transaction():
            self._repo.update(case_id, assigned_analyst_id=analyst_id, updated_at=now_iso())
            self._audit.record("CASE_ANALYST_ASSIGNED", actor_id=actor.id, target_type="case", target_id=case_id,
                               case_id=case_id, details={"analyst_id": analyst_id})
        return self._repo.get(case_id)
