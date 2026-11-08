"""LSB steganography on PNG (1 bit per R/G/B byte; the alpha channel is never touched)."""
from __future__ import annotations

from PIL import Image

from sentinel.utils.exceptions import ValidationError


def prepare(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "RGBA"):
        return img
    has_alpha = img.mode in ("LA", "PA") or "transparency" in img.info
    return img.convert("RGBA" if has_alpha else "RGB")


def capacity_bytes(img: Image.Image) -> int:
    w, h = img.size
    return (w * h * 3) // 8


def _idx(bit: int, rgba: bool) -> int:
    return (bit // 3) * 4 + bit % 3 if rgba else bit


def embed(img: Image.Image, payload: bytes) -> Image.Image:
    img = prepare(img)
    if len(payload) > capacity_bytes(img):
        raise ValidationError(f"Kapasitas gambar {capacity_bytes(img)} byte tidak cukup untuk {len(payload)} byte.")
    rgba = img.mode == "RGBA"
    data = bytearray(img.tobytes())
    bit = 0
    for byte in payload:
        for shift in range(7, -1, -1):
            i = _idx(bit, rgba)
            data[i] = (data[i] & 0xFE) | ((byte >> shift) & 1)
            bit += 1
    return Image.frombytes(img.mode, img.size, bytes(data))


def extract(img: Image.Image, nbytes: int, offset_bytes: int = 0) -> bytes:
    img = prepare(img)
    if (offset_bytes + nbytes) > capacity_bytes(img):
        raise ValidationError("Gambar tidak memuat payload SENTINEL (ukuran tidak sesuai kapasitas).")
    rgba = img.mode == "RGBA"
    data = img.tobytes()
    out = bytearray()
    bit = offset_bytes * 8
    for _ in range(nbytes):
        v = 0
        for _ in range(8):
            v = (v << 1) | (data[_idx(bit, rgba)] & 1)
            bit += 1
        out.append(v)
    return bytes(out)
