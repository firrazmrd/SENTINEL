"""SQLCipher access. One connection per thread (never shared); nested-safe transactions."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any, Iterator, Sequence

from sentinel.utils.exceptions import DatabaseKeyError, SqlCipherUnavailableError

try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError as exc:  # never fall back to plaintext sqlite3
    raise SqlCipherUnavailableError(
        "Package sqlcipher3 tidak terpasang. SENTINEL tidak akan memakai SQLite tanpa enkripsi."
    ) from exc


class Database:
    def __init__(self, path: Path, key: bytes) -> None:
        self._path = Path(path)
        self._hexkey = key.hex()
        self._local = threading.local()
        self._all: list[Any] = []
        self._lock = threading.Lock()

    # -- connections -------------------------------------------------------
    def _open(self) -> Any:
        conn = sqlcipher.connect(str(self._path), isolation_level=None, check_same_thread=False)
        conn.execute(f"PRAGMA key = \"x'{self._hexkey}'\"")  # must be the first statement
        version = conn.execute("PRAGMA cipher_version").fetchone()
        if not version or not version[0]:
            conn.close()
            raise SqlCipherUnavailableError("Binding database bukan SQLCipher (cipher_version kosong).")
        try:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlcipher.DatabaseError as exc:
            conn.close()
            raise DatabaseKeyError(
                "Database tidak dapat dibuka: key salah atau database rusak. Database tidak ditimpa."
            ) from exc
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlcipher.Row
        with self._lock:
            self._all.append(conn)
        return conn

    def conn(self) -> Any:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = self._local.conn = self._open()
            self._local.depth = 0
        return c

    def cipher_version(self) -> str:
        return self.conn().execute("PRAGMA cipher_version").fetchone()[0]

    def close_all(self) -> None:
        with self._lock:
            for c in self._all:
                try:
                    c.close()
                except Exception:  # noqa: BLE001
                    pass
            self._all.clear()
        self._local = threading.local()

    def init_schema(self) -> None:
        sql = resources.files("sentinel.database").joinpath("schema.sql").read_text(encoding="utf-8")
        self.conn().executescript(sql)

    # -- transactions ------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[Any]:
        conn = self.conn()
        outer = self._local.depth == 0
        if outer:
            conn.execute("BEGIN IMMEDIATE")
        self._local.depth += 1
        try:
            yield conn
        except BaseException:
            self._local.depth -= 1
            if outer:
                conn.execute("ROLLBACK")
            raise
        else:
            self._local.depth -= 1
            if outer:
                conn.execute("COMMIT")

    # -- helpers -----------------------------------------------------------
    def run(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> None:
        self.conn().execute(sql, params)

    def one(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> dict[str, Any] | None:
        row = self.conn().execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def all(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn().execute(sql, params).fetchall()]

    def scalar(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> Any:
        row = self.conn().execute(sql, params).fetchone()
        return row[0] if row is not None else None
