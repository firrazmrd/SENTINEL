from __future__ import annotations

from datetime import datetime, timezone

_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_iso() -> str:
    """UTC timestamp with fixed width (safe for canonical hashing and string comparison)."""
    return datetime.now(timezone.utc).strftime(_FMT)


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, _FMT).replace(tzinfo=timezone.utc)


def to_local(value: str | None) -> str:
    """Stored UTC ISO string -> local 'YYYY-MM-DD HH:MM' for display."""
    if not value:
        return ""
    try:
        return parse_iso(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value
