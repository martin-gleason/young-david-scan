"""Inactivity timer that locks the app after N minutes of no input.

Binds keyboard / mouse events at the Tk root. Any event resets a single
`after()` timer. When the timer fires, `on_lock` is invoked — typically
to clear the master key and route back to AuthScreen.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .logging_setup import get_logger

log = get_logger(__name__)


class IdleLock:
    """Tk-event-bound inactivity watchdog.

    Usage:
        lock = IdleLock(root, timeout_min=10, on_lock=lambda: app.lock_now())
        lock.start()    # after the user has successfully authenticated

    The watchdog can be paused (e.g. while the AuthScreen itself is up)
    with `stop()` and resumed with `start()`.
    """

    EVENTS = ("<Any-Key>", "<Button>", "<Motion>")

    def __init__(
        self,
        root: tk.Tk,
        timeout_min: int,
        on_lock: Callable[[], None],
    ):
        if timeout_min <= 0:
            raise ValueError(f"timeout_min must be positive, got {timeout_min}")
        self._root = root
        self._timeout_ms = timeout_min * 60 * 1000
        self._on_lock = on_lock
        self._after_id: str | None = None
        self._bind_ids: list[str] = []
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        for evt in self.EVENTS:
            bind_id = self._root.bind_all(evt, self._on_activity, add="+")
            self._bind_ids.append(bind_id)
        self._arm()
        self._running = True
        log.info("Idle lock armed (%d ms)", self._timeout_ms)

    def stop(self) -> None:
        if not self._running:
            return
        for evt in self.EVENTS:
            self._root.unbind_all(evt)
        self._bind_ids.clear()
        self._cancel()
        self._running = False
        log.info("Idle lock disarmed")

    def _on_activity(self, _event: tk.Event) -> None:
        self._cancel()
        self._arm()

    def _arm(self) -> None:
        self._after_id = self._root.after(self._timeout_ms, self._fire)

    def _cancel(self) -> None:
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None

    def _fire(self) -> None:
        self._after_id = None
        log.info("Idle timeout reached; invoking on_lock")
        # Stop ourselves so we don't double-fire while the lock screen is up.
        self.stop()
        try:
            self._on_lock()
        except Exception:
            log.exception("on_lock callback raised")
