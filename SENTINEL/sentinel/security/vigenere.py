"""Educational Vigenere cipher (A-Z / a-z only; every other character is preserved)."""
from __future__ import annotations


def _shifts(key: str) -> list[int]:
    shifts = [ord(c.upper()) - 65 for c in key if "a" <= c.lower() <= "z"]
    if not shifts:
        raise ValueError("Kunci Vigenere harus memuat minimal satu huruf A-Z")
    return shifts


def _apply(text: str, key: str, sign: int) -> str:
    shifts = _shifts(key)
    n, i, out = len(shifts), 0, []
    for ch in text:
        if "A" <= ch <= "Z":
            base = 65
        elif "a" <= ch <= "z":
            base = 97
        else:
            out.append(ch)
            continue
        out.append(chr((ord(ch) - base + sign * shifts[i % n]) % 26 + base))
        i += 1
    return "".join(out)


def vigenere_encrypt(text: str, key: str) -> str:
    return _apply(text, key, +1)


def vigenere_decrypt(text: str, key: str) -> str:
    return _apply(text, key, -1)
