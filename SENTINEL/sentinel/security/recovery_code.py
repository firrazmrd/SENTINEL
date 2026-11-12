"""Recovery codes: 16 symbols from a 32-letter alphabet (80 bits), shown once, stored only as an Argon2id hash."""
from __future__ import annotations

import secrets

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no I, O, 0, 1: easy to copy by hand
GROUPS, GROUP_LEN = 4, 4
CODE_LEN = GROUPS * GROUP_LEN


def generate() -> str:
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(GROUP_LEN)) for _ in range(GROUPS))


def normalize(code: str) -> str:
    """Case, spaces and dashes are not significant when the user types the code back."""
    return "".join(ch for ch in (code or "").upper() if ch not in "- \t\r\n")


def is_well_formed(code: str) -> bool:
    n = normalize(code)
    return len(n) == CODE_LEN and all(ch in ALPHABET for ch in n)
