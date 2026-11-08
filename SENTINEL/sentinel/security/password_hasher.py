from __future__ import annotations

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    """Argon2id via argon2-cffi (library defaults, RFC 9106 low-memory profile)."""

    def __init__(self) -> None:
        self._ph = _Argon2()
        # Used to equalise timing when the username does not exist.
        self._dummy = self._ph.hash("sentinel-dummy-password")

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        try:
            return self._ph.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, encoded: str) -> bool:
        return self._ph.check_needs_rehash(encoded)

    def burn_time(self, password: str) -> None:
        self.verify(self._dummy, password)
