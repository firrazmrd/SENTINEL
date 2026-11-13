"""Run slow work (Argon2, camera, crypto, file IO) off the Tk thread; callbacks return on the Tk thread."""
from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable


class AsyncRunner:
    def __init__(self, root: Any) -> None:
        self._root, self._q = root, queue.Queue()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sentinel")  # bounded => bounded DB connections
        self._alive = True
        self.pending = 0          # jobs submitted but whose callback has not run yet (drives the loading bar)
        self._poll()

    def submit(self, fn: Callable[[], Any], on_ok: Callable[[Any], None] | None = None,
               on_err: Callable[[BaseException], None] | None = None) -> None:
        self.pending += 1

        def job() -> None:
            try:
                self._q.put((on_ok, fn(), None))
            except BaseException as exc:  # noqa: BLE001 - forwarded to the UI thread
                self._q.put((on_err, None, exc))
        self._pool.submit(job)

    def _poll(self) -> None:
        if not self._alive:
            return
        try:
            while True:
                cb, result, exc = self._q.get_nowait()
                self.pending = max(0, self.pending - 1)
                if cb is not None:
                    cb(exc) if exc is not None else cb(result)
        except queue.Empty:
            pass
        try:
            self._root.after(40, self._poll)
        except Exception:  # noqa: BLE001 - window destroyed
            self._alive = False

    def shutdown(self) -> None:
        self._alive = False
        self._pool.shutdown(wait=False, cancel_futures=True)
