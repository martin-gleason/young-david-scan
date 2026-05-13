"""AuthScreen — passphrase gate for first-run, unlock, locked, and import.

One class, four refresh modes:

- first_run         set a new passphrase (two fields, confirm)
- unlock            enter passphrase against an existing keyfile
- locked            same as unlock, framed as "locked due to inactivity"
- import_plaintext  set a passphrase to encrypt an existing plaintext DB

Built from the shared widget factories in screens/_shared.py.
"""

from __future__ import annotations

import tkinter as tk

from .. import audit, auth, database
from ..config import (
    APP_TITLE,
    C_BG,
    C_DANGER,
    C_MUTED,
    C_PRIMARY,
    C_WHITE,
    FONT_BODY,
    FONT_H2,
    FONT_LABEL,
    FONT_SMALL,
)
from ..logging_setup import get_logger
from ._shared import btn, make_header

log = get_logger(__name__)

MIN_PASSPHRASE_LEN = 12
MAX_UNLOCK_ATTEMPTS = 5


class AuthScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._mode: str = "unlock"
        self._wrong_attempts = 0
        self._build()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        make_header(self, APP_TITLE, "Sign In")

        outer = tk.Frame(self, bg=C_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(outer, bg=C_WHITE, padx=32, pady=28)
        card.place(relx=0.5, rely=0.45, anchor="center")

        self._title_var = tk.StringVar()
        tk.Label(
            card,
            textvariable=self._title_var,
            bg=C_WHITE,
            fg=C_PRIMARY,
            font=FONT_H2,
        ).pack(anchor="w", pady=(0, 6))

        self._subtitle_var = tk.StringVar()
        tk.Label(
            card,
            textvariable=self._subtitle_var,
            bg=C_WHITE,
            fg=C_MUTED,
            font=FONT_SMALL,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        # Primary passphrase field
        tk.Label(card, text="Passphrase", bg=C_WHITE, fg=C_PRIMARY, font=FONT_LABEL).pack(
            anchor="w"
        )
        self._pw1 = tk.Entry(
            card, show="•", font=FONT_BODY, width=36, relief=tk.SOLID, bd=1, bg=C_WHITE
        )
        self._pw1.pack(anchor="w", pady=(2, 10))

        # Confirm field (only shown in modes that need it)
        self._pw2_label = tk.Label(card, text="Confirm", bg=C_WHITE, fg=C_PRIMARY, font=FONT_LABEL)
        self._pw2 = tk.Entry(
            card, show="•", font=FONT_BODY, width=36, relief=tk.SOLID, bd=1, bg=C_WHITE
        )

        # Error label
        self._error_var = tk.StringVar()
        tk.Label(
            card,
            textvariable=self._error_var,
            bg=C_WHITE,
            fg=C_DANGER,
            font=FONT_SMALL,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        # Action button
        self._submit_btn = btn(card, "Sign In", self._on_submit, primary=True, width=20)
        self._submit_btn.pack(anchor="w", pady=(6, 0))

        # Status label (used during PBKDF2 derivation)
        self._status_var = tk.StringVar()
        tk.Label(
            card,
            textvariable=self._status_var,
            bg=C_WHITE,
            fg=C_MUTED,
            font=FONT_SMALL,
        ).pack(anchor="w", pady=(8, 0))

        # Submit on Enter from either field
        self._pw1.bind("<Return>", lambda _e: self._on_submit())
        self._pw2.bind("<Return>", lambda _e: self._on_submit())

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self, mode: str = "unlock", **_) -> None:
        """Reconfigure the screen for the given mode."""
        self._mode = mode
        self._wrong_attempts = 0
        self._error_var.set("")
        self._status_var.set("")
        self._pw1.delete(0, tk.END)
        self._pw2.delete(0, tk.END)

        if mode == "first_run":
            self._title_var.set("Welcome — set a passphrase")
            self._subtitle_var.set(
                "This passphrase encrypts every case record on this machine.\n"
                "If you lose it, the data cannot be recovered. There is no reset."
            )
            self._submit_btn.config(text="Create passphrase")
            self._pw2_label.pack(anchor="w")
            self._pw2.pack(anchor="w", pady=(2, 10))
        elif mode == "import_plaintext":
            self._title_var.set("Encrypt your existing data")
            self._subtitle_var.set(
                "An unencrypted database was detected on this workstation. "
                "Set a passphrase now to encrypt it. The current file will be "
                "preserved as 'cataloguer.db.pre-phase3.bak' in case anything "
                "goes wrong. Losing this passphrase loses the data."
            )
            self._submit_btn.config(text="Encrypt and continue")
            self._pw2_label.pack(anchor="w")
            self._pw2.pack(anchor="w", pady=(2, 10))
        elif mode == "locked":
            self._title_var.set("Locked due to inactivity")
            self._subtitle_var.set("Re-enter your passphrase to continue.")
            self._submit_btn.config(text="Unlock")
            self._pw2_label.pack_forget()
            self._pw2.pack_forget()
        else:  # unlock
            self._title_var.set("Enter passphrase")
            self._subtitle_var.set("")
            self._submit_btn.config(text="Sign In")
            self._pw2_label.pack_forget()
            self._pw2.pack_forget()

        self._pw1.focus_set()

    # ── Submit handlers ───────────────────────────────────────────────────

    def _on_submit(self) -> None:
        pw1 = self._pw1.get()
        pw2 = self._pw2.get()
        self._error_var.set("")

        if self._mode in ("first_run", "import_plaintext"):
            if len(pw1) < MIN_PASSPHRASE_LEN:
                self._error_var.set(f"Passphrase must be at least {MIN_PASSPHRASE_LEN} characters.")
                return
            if pw1 != pw2:
                self._error_var.set("Passphrases do not match.")
                return

        self._status_var.set("Deriving key… (this takes about a second)")
        self._submit_btn.config(state=tk.DISABLED)
        # Let Tk paint the status before we block on PBKDF2.
        self.update_idletasks()

        try:
            if self._mode == "first_run":
                auth.first_run_setup(pw1)
                database.init_db()
                audit.append_standalone("auth.first_run")
            elif self._mode == "import_plaintext":
                auth.import_plaintext(pw1)
                database.init_db()
                audit.append_standalone("auth.first_run", details={"from": "import_plaintext"})
            else:
                # unlock or locked
                try:
                    auth.unlock(pw1)
                except database.WrongPassphraseError:
                    self._wrong_attempts += 1
                    remaining = MAX_UNLOCK_ATTEMPTS - self._wrong_attempts
                    if remaining <= 0:
                        log.warning("Max unlock attempts reached; quitting")
                        self.app.quit()
                        return
                    self._error_var.set(f"Incorrect passphrase. {remaining} attempt(s) remaining.")
                    return
                audit.append_standalone("auth.unlock_success")
        except Exception as exc:
            log.exception("Auth flow failed")
            self._error_var.set(f"Error: {exc}")
            return
        finally:
            self._status_var.set("")
            self._submit_btn.config(state=tk.NORMAL)
            # Wipe passphrase strings from the widgets ASAP.
            self._pw1.delete(0, tk.END)
            self._pw2.delete(0, tk.END)

        # Success — hand off to the app.
        self.app.on_auth_success()
