"""Super encryption: Vigenere (educational) then AES-256-GCM (real protection). Used for messages and stego."""
from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sentinel.security.vigenere import vigenere_decrypt, vigenere_encrypt
from sentinel.utils.exceptions import DecryptionError

FORMAT_VERSION = 1
NONCE_LEN = 12


def _aad(context: str, object_id: str) -> bytes:
    return f"SNT|v{FORMAT_VERSION}|{context}|{object_id}".encode("utf-8")


class MessageCrypto:
    def __init__(self, key: bytes, vigenere_key: str) -> None:
        if len(key) != 32:
            raise ValueError("message_key harus 32 byte")
        self._aes = AESGCM(key)
        self._vkey = vigenere_key

    def encrypt(self, plaintext: str, context: str, object_id: str) -> tuple[bytes, bytes]:
        """Return (nonce, ciphertext+tag). `context` is 'message' or 'stego'."""
        layer1 = vigenere_encrypt(plaintext, self._vkey).encode("utf-8")
        nonce = os.urandom(NONCE_LEN)
        return nonce, self._aes.encrypt(nonce, layer1, _aad(context, object_id))

    def decrypt(self, nonce: bytes, ciphertext: bytes, context: str, object_id: str) -> str:
        try:
            layer1 = self._aes.decrypt(nonce, ciphertext, _aad(context, object_id))
        except InvalidTag as exc:
            raise DecryptionError("Autentikasi AES-GCM gagal: data rusak, diubah, atau key tidak cocok.") from exc
        return vigenere_decrypt(layer1.decode("utf-8"), self._vkey)
