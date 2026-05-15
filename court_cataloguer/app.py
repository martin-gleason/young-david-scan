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


def _run_selftest() -> int:
    # Used by the CI build pipeline to fail fast if PyInstaller dropped a
    # required native binary, OR if the frozen bundle behaves differently
    # from a source checkout (e.g. pkgutil.iter_modules returning empty
    # against the PYZ archive — the bug that broke young david's first run).
    # Runs without opening a window so it works on headless Windows runners.
    # Exits 0 on success, non-zero on failure.
    print("court_cataloguer self-test starting", flush=True)

    # SQLCipher: read PRAGMA cipher_version to prove the native cipher
    # library (statically linked into sqlcipher3-wheels) actually loaded.
    # An import alone doesn't catch a missing-DLL failure on Windows.
    from sqlcipher3 import dbapi2 as sqlite

    conn = sqlite.connect(":memory:")
    try:
        conn.execute("PRAGMA key = 'selftest-key';")
        row = conn.execute("PRAGMA cipher_version;").fetchone()
        if not row or not row[0]:
            print("FAIL: sqlcipher PRAGMA cipher_version returned nothing", flush=True)
            return 2
        print(f"  sqlcipher cipher_version: {row[0]}", flush=True)

        # Exercise the cipher: write, close, reopen with the same key,
        # read back. A miswired cipher would fail decryption here.
        conn.execute("CREATE TABLE t (x INTEGER);")
        conn.execute("INSERT INTO t VALUES (42);")
        conn.commit()
        (val,) = conn.execute("SELECT x FROM t").fetchone()
        if val != 42:
            print(f"FAIL: sqlcipher round-trip returned {val!r}", flush=True)
            return 3
    finally:
        conn.close()

    # PyMuPDF: open a blank PDF in memory. Catches missing-DLL failures on
    # Windows that an import-only check would miss.
    import fitz

    doc = fitz.open()
    doc.new_page()
    if doc.page_count != 1:
        print(f"FAIL: fitz blank doc has {doc.page_count} pages", flush=True)
        return 4
    doc.close()
    print("  fitz: ok", flush=True)

    # tkinter: import only — headless CI runners have no display, so we
    # can't actually construct a Tk root here.
    import tkinter  # noqa: F401

    print("  tkinter: ok", flush=True)

    # cryptography: the HMAC + HKDF primitives used by Phase 3 (key
    # derivation) and Phase 4 (audit-log chain) need these.
    from cryptography.hazmat.primitives import hashes, hmac  # noqa: F401

    print("  cryptography: ok", flush=True)

    # Migration discovery: the explicit MIGRATIONS tuple must be non-empty
    # AND every name in it must be importable as a submodule. The whole
    # point of switching off pkgutil was that PyInstaller's frozen-PYZ
    # archive returned nothing — this asserts we found the modules anyway.
    from court_cataloguer.migrations import MIGRATIONS

    if not MIGRATIONS:
        print("FAIL: MIGRATIONS list is empty", flush=True)
        return 5
    import importlib

    for name in MIGRATIONS:
        try:
            mod = importlib.import_module(f"court_cataloguer.migrations.{name}")
        except ImportError as exc:
            print(f"FAIL: migration {name} not importable: {exc}", flush=True)
            return 6
        if not hasattr(mod, "run"):
            print(f"FAIL: migration {name} has no run() function", flush=True)
            return 7
    print(f"  migrations: {len(MIGRATIONS)} module(s) importable", flush=True)

    # End-to-end first-run flow: write keyfile, init the encrypted DB, run
    # ALL migrations, append the audit row, unlock with the same passphrase,
    # read it back. This is the scenario that broke at runtime under PR #5
    # — the cipher worked and modules imported, but the migration step
    # silently no-op'd and the next line tried to insert into a nonexistent
    # audit_log table. This block exercises that full path.
    import os
    import tempfile
    from pathlib import Path

    from court_cataloguer import auth, config, database

    tmp_data = Path(tempfile.mkdtemp(prefix="court-selftest-"))
    os.environ["COURT_DOC_DIR"] = str(tmp_data)
    # config was imported earlier (transitively) so its module-level paths
    # are already frozen. Repoint them explicitly for this run.
    config.APP_DATA_DIR = tmp_data
    config.DB_PATH = tmp_data / "cataloguer.db"
    config.KEYFILE_PATH = tmp_data / "keyfile.json"
    database.APP_DATA_DIR = tmp_data
    database.DB_PATH = tmp_data / "cataloguer.db"
    auth.DB_PATH = tmp_data / "cataloguer.db"
    auth.KEYFILE_PATH = tmp_data / "keyfile.json"

    try:
        from court_cataloguer import audit

        passphrase = "selftest-passphrase-not-real"
        auth.first_run_setup(passphrase)
        database.init_db()
        # The audit append is the line that failed in production — keep it.
        audit.append_standalone("auth.first_run")

        # Round-trip: lock + unlock with the same passphrase.
        database.clear_master_key()
        auth.unlock(passphrase)
        rows = database.get_all_cases()
        if rows != []:
            print(f"FAIL: fresh DB had unexpected rows: {rows!r}", flush=True)
            return 8
        print("  first-run + unlock round trip: ok", flush=True)
    finally:
        import shutil as _shutil

        database.clear_master_key()
        _shutil.rmtree(tmp_data, ignore_errors=True)

    print("court_cataloguer self-test passed", flush=True)
    return 0


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(_run_selftest())

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
