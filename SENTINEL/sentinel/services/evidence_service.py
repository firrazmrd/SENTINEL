"""Evidence intake -> SHA-256 -> ChaCha20-Poly1305 one-shot (<=100 MB) -> ciphertext-only storage."""
from __future__ import annotations

import mimetypes
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from sentinel.database.connection import Database
from sentinel.database.repositories import CaseRepo, EvidenceRepo
from sentinel.security.file_crypto import FileCrypto
from sentinel.security.hashing import sha256_hex
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import DecryptionError, NotFoundError, PermissionDeniedError, ValidationError
from sentinel.utils.timeutil import now_iso

VALID, CT_MODIFIED, PT_MISMATCH, DEC_FAILED = (
    "VALID", "CIPHERTEXT_MODIFIED", "PLAINTEXT_HASH_MISMATCH", "DECRYPTION_FAILED")


@dataclass(frozen=True)
class IntegrityResult:
    status: str
    detail: str = ""


def _atomic_write(dest: Path, data: bytes) -> None:
    tmp = dest.with_name(dest.name + ".tmp")  # same directory/volume so os.replace is atomic
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


class EvidenceService:
    def __init__(self, db: Database, repo: EvidenceRepo, cases: CaseRepo, crypto: FileCrypto,
                 perms: PermissionService, audit: AuditService, evidence_dir: Path, max_bytes: int,
                 allowed_ext: tuple[str, ...]) -> None:
        self._db, self._repo, self._cases, self._crypto = db, repo, cases, crypto
        self._perms, self._audit = perms, audit
        self._dir, self._max, self._ext = Path(evidence_dir), max_bytes, allowed_ext

    # -- helpers -----------------------------------------------------------
    def _load(self, actor: CurrentUser, evidence_id: str, action: Action) -> tuple[CurrentUser, dict, dict]:
        actor = self._perms.authorize(actor, action)
        ev = self._repo.get(evidence_id)
        if ev is None:
            raise NotFoundError("Bukti tidak ditemukan.")
        case = self._cases.get(ev["case_id"])
        self._perms.require_case_view(actor, case)
        return actor, ev, case

    def _cipher_path(self, ev: dict) -> Path:
        return self._dir / ev["encrypted_path"]

    # -- queries -----------------------------------------------------------
    def list_for_case(self, actor: CurrentUser, case_id: str) -> list[dict]:
        actor = self._perms.authorize(actor, Action.VIEW_EVIDENCE_META)
        self._perms.require_case_view(actor, self._cases.get(case_id))
        return self._repo.list_for_case(case_id)

    # -- upload ------------------------------------------------------------
    def upload(self, actor: CurrentUser, case_id: str, source: Path) -> dict:
        actor = self._perms.authorize(actor, Action.UPLOAD_EVIDENCE)
        case = self._cases.get(case_id)
        self._perms.require_case_view(actor, case)
        if case["status"] == "CLOSED":
            raise ValidationError("Kasus sudah CLOSED; bukti baru tidak dapat ditambahkan.")
        source = Path(source)
        if not source.is_file():
            raise ValidationError("File sumber tidak ditemukan.")
        if source.suffix.lower() not in self._ext:
            raise ValidationError(f"Ekstensi tidak diizinkan. Diizinkan: {', '.join(self._ext)}")
        size = source.stat().st_size
        if size > self._max:
            raise ValidationError(f"File terlalu besar ({size / 1048576:.1f} MB). Maksimum {self._max // 1048576} MB.")
        data = source.read_bytes()  # read-only: the original is never modified
        if len(data) > self._max:
            raise ValidationError("File melebihi batas ukuran.")
        original_sha = sha256_hex(data)

        evidence_id = str(uuid.uuid4())
        blob = self._crypto.encrypt(data, evidence_id)
        del data
        encrypted_sha = sha256_hex(blob)

        with self._db.transaction():
            seq = self._repo.count_for_case(case_id) + 1
            code = f"EV-{case['case_number']}-{seq:03d}"
            rel = f"{case['case_number']}/{code}.sntenc"
            dest = self._dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(dest, blob)
            try:
                self._repo.insert({
                    "id": evidence_id, "evidence_code": code, "case_id": case_id,
                    "original_filename": source.name, "mime_type": mimetypes.guess_type(source.name)[0],
                    "original_size": size, "encrypted_path": rel, "encryption_algorithm": "CHACHA20-POLY1305",
                    "original_sha256": original_sha, "encrypted_sha256": encrypted_sha,
                    "uploaded_by": actor.id, "created_at": now_iso()})
                self._audit.record("EVIDENCE_UPLOADED", actor_id=actor.id, target_type="evidence",
                                   target_id=evidence_id, case_id=case_id,
                                   details={"code": code, "size": size, "sha256": original_sha})
            except BaseException:
                dest.unlink(missing_ok=True)  # do not leave orphan ciphertext behind
                raise
        return self._repo.get(evidence_id)

    # -- integrity ---------------------------------------------------------
    def _record_status(self, ev: dict, actor: CurrentUser, status: str, mode: str) -> None:
        with self._db.transaction():
            if status != "CIPHERTEXT_OK":
                self._repo.set_status(ev["id"], status)
            elif ev["status"] == CT_MODIFIED:
                self._repo.set_status(ev["id"], "STORED")
            self._audit.record("EVIDENCE_HASH_VERIFIED", actor_id=actor.id, target_type="evidence",
                               target_id=ev["id"], case_id=ev["case_id"], details={"mode": mode, "result": status})

    def _read_ciphertext(self, ev: dict) -> bytes | None:
        try:
            return self._cipher_path(ev).read_bytes()
        except OSError:
            return None

    def verify_ciphertext(self, actor: CurrentUser, evidence_id: str) -> IntegrityResult:
        """No key is used: only compares SHA-256 of the stored file with the hash recorded at intake."""
        actor, ev, _ = self._load(actor, evidence_id, Action.VERIFY_CIPHERTEXT)
        blob = self._read_ciphertext(ev)
        ok = blob is not None and sha256_hex(blob) == ev["encrypted_sha256"]
        status = "CIPHERTEXT_OK" if ok else CT_MODIFIED
        self._record_status(ev, actor, status, "ciphertext")
        return IntegrityResult(status, "Hash ciphertext cocok." if ok else
                               "Hash ciphertext berbeda atau file hilang.")

    def _decrypt(self, ev: dict) -> tuple[IntegrityResult, bytes | None]:
        blob = self._read_ciphertext(ev)
        if blob is None or sha256_hex(blob) != ev["encrypted_sha256"]:
            return IntegrityResult(CT_MODIFIED, "Ciphertext berubah atau hilang; dekripsi dibatalkan."), None
        try:
            plain = self._crypto.decrypt(blob, ev["id"])
        except DecryptionError as exc:
            return IntegrityResult(DEC_FAILED, str(exc)), None
        if sha256_hex(plain) != ev["original_sha256"]:
            return IntegrityResult(PT_MISMATCH, "SHA-256 plaintext berbeda dari hash saat intake."), None
        return IntegrityResult(VALID, "Tag autentikasi valid dan hash plaintext cocok."), plain

    def verify_plaintext(self, actor: CurrentUser, evidence_id: str) -> IntegrityResult:
        """Decrypts in memory only (nothing is written) and compares with the intake hash."""
        actor, ev, _ = self._load(actor, evidence_id, Action.VERIFY_PLAINTEXT)
        result, _plain = self._decrypt(ev)
        self._record_status(ev, actor, result.status, "plaintext")
        return result

    def export(self, actor: CurrentUser, evidence_id: str, dest: Path, overwrite: bool = False) -> IntegrityResult:
        actor, ev, _ = self._load(actor, evidence_id, Action.DECRYPT_EVIDENCE)
        dest = Path(dest)
        if self._dir.resolve() in dest.resolve().parents:
            raise PermissionDeniedError("Tujuan ekspor tidak boleh berada di folder evidence internal.")
        if dest.exists() and not overwrite:
            raise FileExistsError(str(dest))
        result, plain = self._decrypt(ev)
        with self._db.transaction():
            if result.status != VALID:
                self._repo.set_status(ev["id"], result.status)
            self._audit.record("EVIDENCE_DECRYPTED", actor_id=actor.id, target_type="evidence", target_id=ev["id"],
                               case_id=ev["case_id"], details={"result": result.status})
        if plain is None:
            return result
        _atomic_write(dest, plain)
        with self._db.transaction():
            self._repo.set_status(ev["id"], VALID)
            self._audit.record("EVIDENCE_EXPORTED", actor_id=actor.id, target_type="evidence", target_id=ev["id"],
                               case_id=ev["case_id"], details={"sha256": ev["original_sha256"]})
        return result

    def add_note(self, actor: CurrentUser, evidence_id: str, note: str) -> None:
        actor, ev, _ = self._load(actor, evidence_id, Action.ADD_NOTE)
        note = note.strip()
        if len(note) > 1000:
            raise ValidationError("Catatan maksimum 1000 karakter.")
        with self._db.transaction():
            self._repo.set_note(ev["id"], note)
            self._audit.record("EVIDENCE_NOTE_ADDED", actor_id=actor.id, target_type="evidence",
                               target_id=ev["id"], case_id=ev["case_id"])
