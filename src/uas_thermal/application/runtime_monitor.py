from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from .autopilot import RuntimeSnapshot, scan_runtime


@dataclass(frozen=True, slots=True)
class RuntimeUpdate:
    snapshot: RuntimeSnapshot | None
    error: str = ""
    completed_at: float = 0.0


class RuntimeMonitor:
    """Run local runtime discovery off the UI thread and expose polling semantics.

    The monitor coalesces repeated refresh requests, enforces a minimum automatic refresh interval,
    and never blocks the caller while Ollama/model capability discovery or backend checks run.
    """

    def __init__(
        self,
        scanner: Callable[[], RuntimeSnapshot] = scan_runtime,
        *,
        min_interval_s: float = 20.0,
    ) -> None:
        self._scanner = scanner
        self._min_interval_s = max(0.0, float(min_interval_s))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="thermal-runtime")
        self._lock = threading.Lock()
        self._future: Future[RuntimeSnapshot] | None = None
        self._last_started_at = 0.0
        self._last_update: RuntimeUpdate | None = None
        self._closed = False

    @property
    def refreshing(self) -> bool:
        with self._lock:
            return self._future is not None and not self._future.done()

    @property
    def last_update(self) -> RuntimeUpdate | None:
        with self._lock:
            return self._last_update

    def request_refresh(self, *, force: bool = False) -> bool:
        now = time.monotonic()
        with self._lock:
            if self._closed:
                return False
            if self._future is not None and not self._future.done():
                return False
            if not force and now - self._last_started_at < self._min_interval_s:
                return False
            self._last_started_at = now
            self._future = self._executor.submit(self._scanner)
            return True

    def poll(self) -> RuntimeUpdate | None:
        with self._lock:
            future = self._future
            previous = self._last_update
        if future is None or not future.done():
            return None

        try:
            snapshot = future.result()
            update = RuntimeUpdate(snapshot=snapshot, completed_at=time.time())
        except Exception as exc:  # pragma: no cover - scanner boundary
            update = RuntimeUpdate(
                snapshot=None,
                error=f"{type(exc).__name__}: {exc}",
                completed_at=time.time(),
            )

        with self._lock:
            if self._future is future:
                self._future = None
                self._last_update = update
        if previous == update:
            return None
        return update

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
