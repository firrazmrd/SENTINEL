"""Hide Vigenere+AES-GCM ciphertext in a PNG (LSB). Same message key; AAD bound to the artifact id."""
from __future__ import annotations

import os
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from sentinel.database.connection import Database
from sentinel.database.repositories import CaseRepo, StegoRepo
from sentinel.security import stego_lsb
from sentinel.security.hashing import sha256_file, sha256_hex
from sentinel.security.message_crypto import NONCE_LEN, MessageCrypto
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import DecryptionError, ValidationError
from sentinel.utils.timeutil import now_iso

MAGIC = b"SNTSTG"
VERSION = 1
HEADER_LEN = len(MAGIC) + 1 + 16 + NONCE_LEN + 4


@dataclass(frozen=True)
class EmbedResult:
    artifact_id: str
    output_path: Path
    payload_bytes: int
    capacity_bytes: int


class SteganographyService:
    def __init__(self, db: Database, repo: StegoRepo, cases: CaseRepo, crypto: MessageCrypto,
                 perms: PermissionService, audit: AuditService) -> None:
        self._db, self._repo, self._cases, self._crypto = db, repo, cases, crypto
        self._perms, self._audit = perms, audit

    @staticmethod
    def _open_png(path: Path) -> Image.Image:
        try:
            img = Image.open(path)
            img.load()
        except (OSError, UnidentifiedImageError) as exc:
            raise ValidationError("File gambar tidak dapat dibaca.") from exc
        if img.format != "PNG":
            raise ValidationError("Hanya PNG yang didukung (JPEG bersifat lossy dan merusak LSB).")
        return img

    def capacity(self, actor: CurrentUser, png: Path) -> int:
        self._perms.authorize(actor, Action.USE_STEGO)
        return max(0, stego_lsb.capacity_bytes(stego_lsb.prepare(self._open_png(Path(png)))) - HEADER_LEN - 16)

    def embed(self, actor: CurrentUser, source_png: Path, text: str, output_png: Path,
              case_id: str | None = None, overwrite: bool = False) -> EmbedResult:
        actor = self._perms.authorize(actor, Action.USE_STEGO)
        source_png, output_png = Path(source_png), Path(output_png)
        if not text.strip():
            raise ValidationError("Pesan yang disembunyikan tidak boleh kosong.")
        if case_id:
            self._perms.require_case_view(actor, self._cases.get(case_id))
        if output_png.exists() and (output_png.resolve() == source_png.resolve() or not overwrite):
            raise ValidationError("File tujuan sudah ada. Gambar sumber tidak pernah ditimpa; pilih nama lain.")
        img = self._open_png(source_png)

        artifact_id = str(uuid.uuid4())
        nonce, ct = self._crypto.encrypt(text, "stego", artifact_id)
        payload = (MAGIC + bytes([VERSION]) + uuid.UUID(artifact_id).bytes + nonce
                   + struct.pack(">I", len(ct)) + ct)
        stego = stego_lsb.embed(img, payload)  # raises ValidationError when capacity is insufficient

        tmp = output_png.with_name(output_png.name + ".tmp")
        try:
            stego.save(tmp, format="PNG", optimize=False)
            os.replace(tmp, output_png)
        finally:
            tmp.unlink(missing_ok=True)
        with self._db.transaction():
            self._repo.insert({"id": artifact_id, "case_id": case_id or None,
                               "source_image_name": source_png.name, "output_path": str(output_png),
                               "carrier_sha256": sha256_file(output_png), "payload_sha256": sha256_hex(payload),
                               "created_by": actor.id, "created_at": now_iso()})
            self._audit.record("STEGO_CREATED", actor_id=actor.id, target_type="stego", target_id=artifact_id,
                               case_id=case_id or None, details={"payload_bytes": len(payload)})
        return EmbedResult(artifact_id, output_png, len(payload), stego_lsb.capacity_bytes(stego))

    def extract(self, actor: CurrentUser, png: Path) -> str:
        actor = self._perms.authorize(actor, Action.USE_STEGO)
        img = self._open_png(Path(png))
        if stego_lsb.capacity_bytes(stego_lsb.prepare(img)) < HEADER_LEN:
            raise ValidationError("Gambar terlalu kecil untuk memuat payload SENTINEL.")
        header = stego_lsb.extract(img, HEADER_LEN)
        if not header.startswith(MAGIC):
            raise ValidationError("Tidak ditemukan payload SENTINEL pada gambar ini.")
        if header[len(MAGIC)] != VERSION:
            raise ValidationError("Versi payload tidak didukung.")
        p = len(MAGIC) + 1
        artifact_id = str(uuid.UUID(bytes=header[p:p + 16]))
        nonce = header[p + 16:p + 16 + NONCE_LEN]
        (ct_len,) = struct.unpack(">I", header[p + 16 + NONCE_LEN:])
        ct = stego_lsb.extract(img, ct_len, offset_bytes=HEADER_LEN)  # bounds-checked against capacity
        try:
            text = self._crypto.decrypt(nonce, ct, "stego", artifact_id)
        except DecryptionError as exc:
            raise DecryptionError("Payload gagal diautentikasi (gambar diubah atau key berbeda).") from exc
        self._audit.record("STEGO_EXTRACTED", actor_id=actor.id, target_type="stego", target_id=artifact_id)
        return text
