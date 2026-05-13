"""AuditLogScreen — operator view of the tamper-evident audit log.

Hidden by default. The Home screen only shows the "Audit Log" button
when `COURT_DOC_AUDIT=1` is set in the environment, so the navigator's
day-to-day UI stays uncluttered.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import audit, database
from ..config import (
    C_BG,
    C_DANGER,
    C_MUTED,
    C_SUCCESS,
    C_TEXT,
    FONT_LABEL,
    FONT_SMALL,
)
from ..logging_setup import get_logger
from ._shared import btn, make_header

log = get_logger(__name__)


class AuditLogScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._build()

    def _build(self):
        header = make_header(self, "Audit Log")
        btn(
            header,
            "← Back",
            lambda: self.app.show_screen("HomeScreen"),
            primary=False,
            width=10,
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        # Status bar (chain verified / broken)
        self._status_var = tk.StringVar(value="")
        tk.Label(
            self,
            textvariable=self._status_var,
            bg=C_BG,
            fg=C_TEXT,
            font=FONT_LABEL,
            pady=8,
        ).pack()

        # Treeview of rows
        tree_frame = tk.Frame(self, bg=C_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))

        cols = ("id", "ts_utc", "actor", "action", "target", "details")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("id", text="#")
        self._tree.heading("ts_utc", text="Timestamp (UTC)")
        self._tree.heading("actor", text="Actor")
        self._tree.heading("action", text="Action")
        self._tree.heading("target", text="Target")
        self._tree.heading("details", text="Details")
        self._tree.column("id", width=50, anchor="e")
        self._tree.column("ts_utc", width=180)
        self._tree.column("actor", width=120)
        self._tree.column("action", width=160)
        self._tree.column("target", width=140)
        self._tree.column("details", width=260)

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        # Buttons
        btn_row = tk.Frame(self, bg=C_BG)
        btn_row.pack(pady=10)
        btn(btn_row, "↻ Refresh", self._reload, primary=False, width=12).pack(side=tk.LEFT, padx=8)
        btn(btn_row, "✓ Verify Chain", self._verify, primary=True, width=18).pack(
            side=tk.LEFT, padx=8
        )

        self._count_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._count_var, bg=C_BG, fg=C_MUTED, font=FONT_SMALL).pack(
            pady=(0, 6)
        )

    def refresh(self, **_) -> None:
        self._reload()

    def _reload(self) -> None:
        self._tree.delete(*self._tree.get_children())
        with database._connect() as conn:
            rows = conn.execute(
                """SELECT id, ts_utc, actor, machine, action,
                          target_table, target_id, details_json
                   FROM audit_log
                   ORDER BY id DESC
                   LIMIT 500"""
            ).fetchall()
        for r in rows:
            target = f"{r['target_table']}#{r['target_id']}" if r["target_table"] else ""
            self._tree.insert(
                "",
                tk.END,
                iid=str(r["id"]),
                values=(
                    r["id"],
                    r["ts_utc"],
                    r["actor"],
                    r["action"],
                    target,
                    r["details_json"],
                ),
            )
        self._count_var.set(f"{len(rows)} row(s) shown (most recent first)")
        self._status_var.set("")

    def _verify(self) -> None:
        try:
            result = audit.verify_chain()
        except Exception as exc:
            log.exception("verify_chain raised")
            self._status_var.set(f"Verification error: {exc}")
            return

        if result.ok:
            self._status_var.set(f"✓  Chain verified ({result.row_count} row(s))")
            # Set foreground for emphasis if the framework allows; otherwise
            # rely on the leading checkmark to signal status.
            self.master.update_idletasks()
        else:
            self._status_var.set(
                f"⚠  Chain BROKEN at id={result.first_broken_id}  " f"— {result.reason}"
            )

        # Colour the status bar to match. Re-fetch the label widget via
        # nametowidget would be brittle; easier path is to keep one widget
        # reference.
        for w in self.winfo_children():
            if isinstance(w, tk.Label):
                w.configure(fg=C_SUCCESS if result.ok else C_DANGER)
                break
