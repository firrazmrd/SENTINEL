"""Messages between accounts of the same installation. Vigenere + AES-256-GCM; DB stores ciphertext only."""
from __future__ import annotations

import uuid

from sentinel.database.connection import Database
from sentinel.database.repositories import CaseRepo, MessageRepo, UserRepo
from sentinel.security.message_crypto import MessageCrypto
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import PermissionDeniedError, ValidationError
from sentinel.utils.timeutil import now_iso

MAX_LEN = 5000


class MessageService:
    def __init__(self, db: Database, repo: MessageRepo, users: UserRepo, cases: CaseRepo, crypto: MessageCrypto,
                 perms: PermissionService, audit: AuditService) -> None:
        self._db, self._repo, self._users, self._cases = db, repo, users, cases
        self._crypto, self._perms, self._audit = crypto, perms, audit

    def send(self, actor: CurrentUser, receiver_id: str, body: str, case_id: str | None = None) -> str:
        actor = self._perms.authorize(actor, Action.SEND_MESSAGE)
        if not body.strip():
            raise ValidationError("Pesan tidak boleh kosong.")
        if len(body) > MAX_LEN:
            raise ValidationError(f"Pesan maksimum {MAX_LEN} karakter.")
        receiver = self._users.get(receiver_id)
        if receiver is None or receiver["status"] != "ACTIVE" or receiver["id"] == actor.id:
            raise ValidationError("Penerima tidak valid.")
        if not PermissionService.role_allows(receiver["role"], Action.READ_MESSAGE):
            raise ValidationError("Role penerima tidak berhak membaca pesan.")
        if case_id:
            self._perms.require_case_view(actor, self._cases.get(case_id))
        message_id = str(uuid.uuid4())
        nonce, ct = self._crypto.encrypt(body, "message", message_id)
        with self._db.transaction():
            self._repo.insert({"id": message_id, "case_id": case_id or None, "sender_id": actor.id,
                               "receiver_id": receiver_id, "ciphertext": ct, "nonce": nonce,
                               "algorithm": "VIGENERE+AES-256-GCM", "created_at": now_iso()})
            self._audit.record("MESSAGE_SENT", actor_id=actor.id, target_type="message", target_id=message_id,
                               case_id=case_id or None, details={"receiver_id": receiver_id})
        return message_id

    @staticmethod
    def _meta(row: dict) -> dict:
        return {k: v for k, v in row.items() if k not in ("ciphertext", "nonce")}

    def inbox(self, actor: CurrentUser) -> list[dict]:
        actor = self._perms.authorize(actor, Action.READ_MESSAGE)
        return [self._meta(r) for r in self._repo.inbox(actor.id)]

    def sent(self, actor: CurrentUser) -> list[dict]:
        actor = self._perms.authorize(actor, Action.READ_MESSAGE)
        return [self._meta(r) for r in self._repo.sent(actor.id)]

    def unread_count(self, actor: CurrentUser) -> int:
        actor = self._perms.authorize(actor, Action.READ_MESSAGE)
        return self._repo.unread_count(actor.id)

    def read(self, actor: CurrentUser, message_id: str) -> str:
        """Only the sender or receiver can decrypt. A failed GCM tag never yields plaintext."""
        actor = self._perms.authorize(actor, Action.READ_MESSAGE)
        row = self._repo.get(message_id)
        if row is None or actor.id not in (row["sender_id"], row["receiver_id"]):
            raise PermissionDeniedError("Pesan tidak ditemukan atau bukan untuk Anda.")
        text = self._crypto.decrypt(row["nonce"], row["ciphertext"], "message", message_id)
        if actor.id == row["receiver_id"] and row["read_at"] is None:
            with self._db.transaction():
                self._repo.mark_read(message_id, now_iso())
                self._audit.record("MESSAGE_READ", actor_id=actor.id, target_type="message",
                                   target_id=message_id, case_id=row["case_id"])
        return text
