# Top-level Tk application.

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from . import database as db
from .config import (
    APP_TITLE,
    APP_VERSION,
    C_BG,
    C_PRIMARY,
    MIN_HEIGHT,
    MIN_WIDTH,
    WINDOW_SIZE,
)
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

        try:
            db.init_db()
        except Exception as exc:
            log.exception("DB init failed")
            messagebox.showerror(
                "Database Error",
                f"Could not initialise the database:\n{exc}\n\n" "The application will now exit.",
            )
            self.destroy()
            sys.exit(1)

        _apply_style()

        container = tk.Frame(self, bg=C_BG)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Import here (not at top) so any missing-package errors surface
        # after the window exists and we can show a real error dialog.
        from .screens import (
            EntryScreen,
            HomeScreen,
            ImportScreen,
            QueueScreen,
            SearchScreen,
        )

        self._frames: dict[str, tk.Frame] = {}
        for ScreenClass in (HomeScreen, ImportScreen, QueueScreen, EntryScreen, SearchScreen):
            frame = ScreenClass(container, self)
            frame.grid(row=0, column=0, sticky="nsew")
            self._frames[ScreenClass.__name__] = frame

        self.show_screen("HomeScreen")

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
