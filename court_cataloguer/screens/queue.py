# Queue screen — shows pending documents and lets the user open one for entry.

import tkinter as tk
from tkinter import messagebox, ttk

from .. import database as db
from ..config import C_BG, C_PENDING, C_TEXT, FONT_BODY
from ._shared import btn, make_header


class QueueScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._build()

    def _build(self):
        header = make_header(self, "Processing Queue")
        btn(
            header, "← Back", lambda: self.app.show_screen("HomeScreen"), primary=False, width=10
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        self._summary_var = tk.StringVar()
        tk.Label(
            self, textvariable=self._summary_var, bg=C_BG, fg=C_TEXT, font=FONT_BODY, pady=8
        ).pack()

        tree_frame = tk.Frame(self, bg=C_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))

        cols = ("id", "filename", "imported", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("id", text="#")
        self._tree.heading("filename", text="Filename")
        self._tree.heading("imported", text="Imported")
        self._tree.heading("status", text="Status")
        self._tree.column("id", width=40, anchor="center")
        self._tree.column("filename", width=320)
        self._tree.column("imported", width=200)
        self._tree.column("status", width=100, anchor="center")

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        self._tree.bind("<Double-1>", lambda _: self._open_selected())

        btn_row = tk.Frame(self, bg=C_BG)
        btn_row.pack(pady=10)
        btn(
            btn_row, "▶  Process Selected Document", self._open_selected, primary=True, width=28
        ).pack(side=tk.LEFT, padx=8)
        btn(btn_row, "↻  Refresh", self.refresh, primary=False, width=12).pack(side=tk.LEFT, padx=8)

    def refresh(self, **_):
        self._tree.delete(*self._tree.get_children())
        summary = db.get_queue_summary()
        self._summary_var.set(
            f"Total: {summary['total']}   |   "
            f"Pending: {summary['pending']}   |   "
            f"Complete: {summary['complete']}   |   "
            f"Skipped: {summary['skipped']}"
        )
        for doc in db.get_pending_documents():
            self._tree.insert(
                "",
                tk.END,
                iid=str(doc["id"]),
                values=(
                    doc["id"],
                    doc["original_filename"],
                    doc["imported_at"],
                    doc["status"].upper(),
                ),
                tags=("pending",),
            )
        self._tree.tag_configure("pending", foreground=C_PENDING)

    def _open_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a document first.")
            return
        doc_id = int(sel[0])
        self.app.show_screen("EntryScreen", doc_id=doc_id)
