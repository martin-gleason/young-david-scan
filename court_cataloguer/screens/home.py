# Home screen — entry point with pending-docs badge and main action buttons.

import os
import tkinter as tk
from tkinter import messagebox

from .. import database as db
from .. import utils
from ..config import (
    APP_TITLE,
    C_BG,
    C_MUTED,
    C_PENDING,
    FONT_H2,
    FONT_SMALL,
)
from ..logging_setup import get_logger
from ._shared import btn, make_header

log = get_logger(__name__)


class HomeScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._build()

    def _build(self):
        make_header(self, APP_TITLE, "Dependency / Neglect Court")

        badge_frame = tk.Frame(self, bg=C_BG)
        badge_frame.pack(pady=(24, 4))

        self._pending_var = tk.StringVar(value="0 documents pending review")
        tk.Label(
            badge_frame,
            textvariable=self._pending_var,
            bg=C_PENDING,
            fg="white",
            font=FONT_H2,
            padx=20,
            pady=6,
            relief=tk.FLAT,
        ).pack()

        grid = tk.Frame(self, bg=C_BG)
        grid.pack(pady=30)

        buttons = [
            ("📥  Import from USB", "ImportScreen", True),
            ("📋  Open Processing Queue", "QueueScreen", True),
            ("💾  Export to Excel", None, False),
            ("🔍  Search Cases", "SearchScreen", True),
        ]

        for i, (label, screen, is_primary) in enumerate(buttons):
            if screen:
                cmd = lambda s=screen: self.app.show_screen(s)
            else:
                cmd = self._export_excel
            b = btn(grid, label, cmd, primary=is_primary, width=26)
            b.grid(row=i // 2, column=i % 2, padx=16, pady=10)

        self._status_var = tk.StringVar()
        tk.Label(self, textvariable=self._status_var, bg=C_BG, fg=C_MUTED, font=FONT_SMALL).pack(
            side=tk.BOTTOM, pady=6
        )

    def refresh(self, **_):
        count = db.get_pending_count()
        if count == 0:
            self._pending_var.set("✓  No documents pending")
        else:
            self._pending_var.set(f"⚠  {count} document(s) pending review")
        self._status_var.set("")

    def _export_excel(self):
        try:
            path = utils.export_master_xlsx()
            if messagebox.askyesno(
                "Export Complete",
                f"Master spreadsheet saved to:\n{path}\n\nOpen it now?",
            ):
                os.startfile(str(path))
        except PermissionError as exc:
            messagebox.showerror("Cannot Export", str(exc))
        except Exception as exc:
            log.exception("Excel export failed")
            messagebox.showerror("Export Error", f"Unexpected error:\n{exc}")
