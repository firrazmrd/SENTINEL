"""ChaCha20-Poly1305 one-shot file encryption. File = MAGIC | version | nonce(12) | ciphertext+tag."""
from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from sentinel.utils.exceptions import DecryptionError

MAGIC = b"SNTENC"
VERSION = 1
NONCE_LEN = 12
HEADER_LEN = len(MAGIC) + 1 + NONCE_LEN


def _aad(evidence_id: str) -> bytes:
    return f"SNT-EVD|v{VERSION}|{evidence_id}".encode("utf-8")


class FileCrypto:
    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("file_key harus 32 byte")
        self._aead = ChaCha20Poly1305(key)

    def encrypt(self, plaintext: bytes, evidence_id: str) -> bytes:
        nonce = os.urandom(NONCE_LEN)
        ct = self._aead.encrypt(nonce, plaintext, _aad(evidence_id))
        return MAGIC + bytes([VERSION]) + nonce + ct

    def decrypt(self, blob: bytes, evidence_id: str) -> bytes:
        if len(blob) < HEADER_LEN + 16 or not blob.startswith(MAGIC):
            raise DecryptionError("Format file bukti tidak dikenali.")
        if blob[len(MAGIC)] != VERSION:
            raise DecryptionError("Versi format file bukti tidak didukung.")
        nonce = blob[len(MAGIC) + 1:HEADER_LEN]
        try:
            return self._aead.decrypt(nonce, blob[HEADER_LEN:], _aad(evidence_id))
        except InvalidTag as exc:
            raise DecryptionError("Autentikasi ChaCha20-Poly1305 gagal.") from exc
