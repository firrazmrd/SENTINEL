"""Local SHA-256 hash chain over audit events. Not a blockchain; tail truncation is not detectable."""
from __future__ import annotations

from dataclasses import dataclass

from sentinel.database.repositories import LedgerRepo
from sentinel.security.hashing import canonical_json, sha256_hex
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.timeutil import now_iso

ZERO_HASH = "0" * 64


@dataclass(frozen=True)
class LedgerVerification:
    valid: bool
    blocks_checked: int
    first_invalid_index: int | None = None
    reason: str = ""


def audit_payload_hash(a: dict) -> str:
    return sha256_hex(canonical_json({
        "id": a["id"], "actor_id": a["actor_id"], "event_type": a["event_type"],
        "target_type": a["target_type"], "target_id": a["target_id"], "case_id": a["case_id"],
        "details_json": a["details_json"], "created_at": a["created_at"]}))


def block_hash(b: dict) -> str:
    return sha256_hex(canonical_json({
        "block_index": b["block_index"], "audit_log_id": b["audit_log_id"],
        "timestamp_utc": b["timestamp_utc"], "actor_id": b["actor_id"], "event_type": b["event_type"],
        "target_id": b["target_id"], "payload_hash": b["payload_hash"], "previous_hash": b["previous_hash"]}))


class LedgerService:
    def __init__(self, repo: LedgerRepo, perms: PermissionService) -> None:
        self._repo, self._perms = repo, perms
        self._audit = None  # bound after AuditService exists (they depend on each other)

    def bind_audit(self, audit) -> None:
        self._audit = audit

    def append(self, audit_row: dict) -> dict:
        """Call inside the same transaction that inserted `audit_row` (serialised by BEGIN IMMEDIATE)."""
        last = self._repo.last()
        block = {
            "block_index": 0 if last is None else last["block_index"] + 1,
            "audit_log_id": audit_row["id"],
            "timestamp_utc": now_iso(),
            "actor_id": audit_row["actor_id"],
            "event_type": audit_row["event_type"],
            "target_id": audit_row["target_id"],
            "payload_hash": audit_payload_hash(audit_row),
            "previous_hash": ZERO_HASH if last is None else last["block_hash"],
        }
        block["block_hash"] = block_hash(block)
        self._repo.insert(block)
        return block

    def check_chain(self) -> LedgerVerification:
        """Recompute everything from genesis. Reports the first failing block index."""
        prev_hash, expected, checked = ZERO_HASH, 0, 0
        for row in self._repo.blocks_with_audit():
            idx = row["block_index"]
            if idx != expected:
                return LedgerVerification(False, checked, expected, "Urutan block tidak berurutan / ada block hilang")
            if row["a_id"] is None:
                return LedgerVerification(False, checked, idx, "Audit log yang ditautkan hilang")
            audit = {k[2:]: row[k] for k in row if k.startswith("a_")}
            if audit_payload_hash(audit) != row["payload_hash"]:
                return LedgerVerification(False, checked, idx, "Payload hash tidak cocok dengan audit log")
            if row["previous_hash"] != prev_hash:
                return LedgerVerification(False, checked, idx, "previous_hash tidak cocok dengan block sebelumnya")
            if block_hash(row) != row["block_hash"]:
                return LedgerVerification(False, checked, idx, "block_hash tidak cocok (data block diubah)")
            prev_hash, expected, checked = row["block_hash"], expected + 1, checked + 1
        if checked == 0:
            return LedgerVerification(False, 0, None, "Ledger kosong: genesis block tidak ditemukan")
        return LedgerVerification(True, checked)

    def verify(self, actor: CurrentUser) -> LedgerVerification:
        actor = self._perms.authorize(actor, Action.VERIFY_LEDGER)
        result = self.check_chain()
        self._audit.record("LEDGER_VERIFIED", actor_id=actor.id, details={
            "valid": result.valid, "blocks_checked": result.blocks_checked,
            "first_invalid_index": result.first_invalid_index})
        return result

    def recent_blocks(self, actor: CurrentUser, limit: int = 200) -> list[dict]:
        self._perms.authorize(actor, Action.VERIFY_LEDGER)
        return self._repo.recent(limit)
