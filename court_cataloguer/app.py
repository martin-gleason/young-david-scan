# Top-level Tk application.

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from . import audit, auth, database
from .config import (
    APP_TITLE,
    APP_VERSION,
    C_BG,
    C_PRIMARY,
    LOCK_TIMEOUT_MIN,
    MIN_HEIGHT,
    MIN_WIDTH,
    WINDOW_SIZE,
)
from .idle import IdleLock
from .logging_setup import get_logger

log = get_logger(__name__)


def _apply_style() -> None:
    """Apply a clean, consistent ttk theme across the app."""
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(
        "Treeview", background="white", fieldbackground="white", rowheight=26, font=("Segoe UI", 10)
    )
    style.configure(
        "Treeview.Heading",
        background=C_PRIMARY,
        foreground="white",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", "#2a5080")])
    style.map("Treeview", background=[("selected", "#1a3a5c")], foreground=[("selected", "white")])

    style.configure("TScrollbar", background="#cccccc", troughcolor="#f0f0f0", arrowcolor="#666666")
    style.configure("TSeparator", background="#dddddd")


class CourtDocApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE}  v{APP_VERSION}")
        self.geometry(WINDOW_SIZE)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.configure(bg=C_BG)

        _apply_style()

        container = tk.Frame(self, bg=C_BG)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Import here (not at top) so any missing-package errors surface
        # after the window exists and we can show a real error dialog.
        from .screens import (
            AuditLogScreen,
            AuthScreen,
            EntryScreen,
            HomeScreen,
            ImportScreen,
            QueueScreen,
            SearchScreen,
        )

        self._frames: dict[str, tk.Frame] = {}
        for ScreenClass in (
            AuthScreen,
            HomeScreen,
            ImportScreen,
            QueueScreen,
            EntryScreen,
            SearchScreen,
            AuditLogScreen,
        ):
            frame = ScreenClass(container, self)
            frame.grid(row=0, column=0, sticky="nsew")
            self._frames[ScreenClass.__name__] = frame

        # IdleLock is created lazily on first auth success (so the
        # passphrase screen itself doesn't trigger a re-lock).
        self._idle_lock: IdleLock | None = None

        # Route to AuthScreen with the right mode for this launch.
        mode = auth.determine_startup_mode()
        log.info("Startup mode: %s", mode.value)
        self.show_screen("AuthScreen", mode=mode.value)

    def show_screen(self, name: str, **kwargs) -> None:
        """Raise a screen and call its refresh(**kwargs) if defined."""
        frame = self._frames.get(name)
        if frame is None:
            messagebox.showerror("Navigation Error", f"Unknown screen: {name}")
            return
        if hasattr(frame, "refresh"):
            try:
                frame.refresh(**kwargs)
            except Exception as exc:
                log.exception("Refresh failed for %s", name)
                messagebox.showerror("Screen Error", f"Error loading {name}:\n{exc}")
        frame.tkraise()

    def on_auth_success(self) -> None:
        """Called by AuthScreen after the master key is installed."""
        # Arm or re-arm the idle lock.
        if self._idle_lock is None:
            self._idle_lock = IdleLock(self, timeout_min=LOCK_TIMEOUT_MIN, on_lock=self.lock_now)
        self._idle_lock.start()
        self.show_screen("HomeScreen")

    def lock_now(self) -> None:
        """Clear the master key and route back to AuthScreen as 'locked'."""
        # Append the audit row BEFORE clearing the key — once cleared we
        # can't sign anything.
        try:
            audit.append_standalone("auth.locked")
        except Exception:
            log.exception("Failed to append auth.locked audit row")
        database.clear_master_key()
        if self._idle_lock is not None:
            self._idle_lock.stop()
        # Defer the screen switch to a Tk idle callback so we don't switch
        # frames while a different event handler is mid-execution.
        self.after(0, lambda: self.show_screen("AuthScreen", mode="locked"))


def main() -> None:
    try:
        app = CourtDocApp()
        app.mainloop()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log.exception("Fatal error")
        try:
            messagebox.showerror(
                "Unexpected Error", f"The application encountered an error:\n{exc}"
            )
        except Exception:
            print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)
