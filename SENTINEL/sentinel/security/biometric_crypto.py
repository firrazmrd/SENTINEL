"""AES-256-GCM encryption of face embeddings (float32 little-endian) with the biometric key."""
from __future__ import annotations

import os
import struct
from typing import Sequence

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sentinel.utils.exceptions import DecryptionError


def _aad(user_id: str) -> bytes:
    return f"SNT-BIO|v1|{user_id}".encode("utf-8")


class BiometricCrypto:
    def __init__(self, key: bytes) -> None:
        self._aes = AESGCM(key)

    def encrypt(self, embedding: Sequence[float], user_id: str) -> tuple[bytes, bytes]:
        raw = struct.pack(f"<{len(embedding)}f", *embedding)
        nonce = os.urandom(12)
        return nonce, self._aes.encrypt(nonce, raw, _aad(user_id))

    def decrypt(self, nonce: bytes, blob: bytes, user_id: str) -> list[float]:
        try:
            raw = self._aes.decrypt(nonce, blob, _aad(user_id))
        except InvalidTag as exc:
            raise DecryptionError("Template wajah tidak dapat diautentikasi.") from exc
        return list(struct.unpack(f"<{len(raw) // 4}f", raw))
