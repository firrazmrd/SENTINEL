"""Four random 256-bit keys per installation, stored only in the OS keyring (Windows Credential Manager)."""
from __future__ import annotations

import secrets

import keyring
from keyring.errors import KeyringError

from sentinel.utils.exceptions import KeyMissingError, KeyringUnavailableError

KEY_NAMES = ("db_key", "message_key", "file_key", "biometric_key")


class KeyManager:
    def __init__(self, service: str) -> None:
        self._service = service

    def ensure_backend(self) -> str:
        kr = keyring.get_keyring()
        module = type(kr).__module__
        if ".fail" in module or ".null" in module:
            raise KeyringUnavailableError(
                "Keyring OS tidak tersedia. SENTINEL tidak menyimpan key di file; periksa Windows Credential Manager."
            )
        return f"{module}.{type(kr).__name__}"

    def _read(self, name: str) -> str | None:
        try:
            return keyring.get_password(self._service, name)
        except KeyringError as exc:
            raise KeyringUnavailableError(f"Gagal membaca keyring: {exc}") from exc

    def missing(self) -> list[str]:
        return [n for n in KEY_NAMES if self._read(n) is None]

    def has_all(self) -> bool:
        return not self.missing()

    def has_any(self) -> bool:
        return len(self.missing()) < len(KEY_NAMES)

    def generate_all(self, overwrite: bool = False) -> None:
        if self.has_any() and not overwrite:
            raise KeyringUnavailableError("Key SENTINEL sudah ada di keyring; tidak ditimpa.")
        try:
            for name in KEY_NAMES:
                keyring.set_password(self._service, name, secrets.token_hex(32))
        except KeyringError as exc:
            raise KeyringUnavailableError(f"Gagal menyimpan key ke keyring: {exc}") from exc

    def get(self, name: str) -> bytes:
        if name not in KEY_NAMES:
            raise KeyError(name)
        value = self._read(name)
        if value is None:
            raise KeyMissingError(
                f"Key '{name}' tidak ditemukan di keyring. Data terenkripsi tidak dapat dibuka; "
                "database tidak akan ditimpa."
            )
        return bytes.fromhex(value)
