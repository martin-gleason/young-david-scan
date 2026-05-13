# Import screen — scan USB drives, list PDFs, copy into archive.

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import utils
from ..config import C_BG, C_MUTED, C_SUCCESS, C_TEXT, FONT_BODY, FONT_LABEL
from ..logging_setup import get_logger
from ._shared import btn, make_header

log = get_logger(__name__)


class ImportScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._pdf_paths: list[Path] = []
        self._build()

    def _build(self):
        header = make_header(self, "Import from USB", "Plug in the USB drive, then scan for PDFs")
        btn(
            header, "← Back", lambda: self.app.show_screen("HomeScreen"), primary=False, width=10
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        scan_bar = tk.Frame(self, bg=C_BG)
        scan_bar.pack(fill=tk.X, padx=20, pady=12)

        btn(scan_bar, "🔍  Scan for USB Drives", self._scan_drives, primary=True, width=22).pack(
            side=tk.LEFT
        )

        self._drive_var = tk.StringVar()
        tk.Label(scan_bar, textvariable=self._drive_var, bg=C_BG, fg=C_MUTED, font=FONT_BODY).pack(
            side=tk.LEFT, padx=12
        )

        list_frame = tk.Frame(self, bg=C_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))

        tk.Label(list_frame, text="PDFs found on drive:", bg=C_BG, fg=C_TEXT, font=FONT_LABEL).pack(
            anchor="w"
        )

        tree_wrap = tk.Frame(list_frame, bg=C_BG)
        tree_wrap.pack(fill=tk.BOTH, expand=True, pady=4)

        cols = ("filename", "size", "folder")
        self._tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", selectmode="extended")
        self._tree.heading("filename", text="Filename")
        self._tree.heading("size", text="Size")
        self._tree.heading("folder", text="Folder on Drive")
        self._tree.column("filename", width=260)
        self._tree.column("size", width=80, anchor="e")
        self._tree.column("folder", width=300)

        sb = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(self, bg=C_BG)
        btn_row.pack(pady=10)

        btn(btn_row, "Import Selected", self._import_selected, primary=False, width=18).pack(
            side=tk.LEFT, padx=8
        )
        btn(btn_row, "Import ALL PDFs", self._import_all, primary=True, width=18).pack(
            side=tk.LEFT, padx=8
        )

        self._status_var = tk.StringVar()
        tk.Label(self, textvariable=self._status_var, bg=C_BG, fg=C_SUCCESS, font=FONT_BODY).pack(
            pady=4
        )

    def refresh(self, **_):
        self._tree.delete(*self._tree.get_children())
        self._pdf_paths = []
        self._drive_var.set("")
        self._status_var.set("")

    def _scan_drives(self):
        self._tree.delete(*self._tree.get_children())
        self._pdf_paths = []

        drives = utils.get_removable_drives()
        if not drives:
            self._drive_var.set("No removable drives found. Check USB connection.")
            return

        drive_str = "  |  ".join(drives)
        self._drive_var.set(f"Found: {drive_str}")

        all_pdfs: list[Path] = []
        for drive in drives:
            all_pdfs.extend(utils.find_pdfs_on_path(drive))

        if not all_pdfs:
            self._drive_var.set(f"Drive found ({drive_str}) but no PDF files on it.")
            return

        self._pdf_paths = all_pdfs
        for pdf in all_pdfs:
            size_kb = pdf.stat().st_size // 1024 if pdf.exists() else 0
            self._tree.insert(
                "",
                tk.END,
                values=(
                    pdf.name,
                    f"{size_kb} KB",
                    str(pdf.parent),
                ),
            )

        self._status_var.set(f"{len(all_pdfs)} PDF(s) found. Select rows or click Import ALL.")

    def _import_selected(self):
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("Nothing Selected", "Click one or more rows in the list first.")
            return
        indices = [self._tree.index(row) for row in selected]
        paths = [self._pdf_paths[i] for i in indices]
        self._do_import(paths)

    def _import_all(self):
        if not self._pdf_paths:
            messagebox.showinfo("No Files", "No PDFs found. Click Scan first.")
            return
        self._do_import(self._pdf_paths)

    def _do_import(self, paths: list[Path]):
        if not paths:
            return
        try:
            doc_ids = utils.import_pdfs(paths)
            messagebox.showinfo(
                "Import Complete",
                f"{len(doc_ids)} document(s) imported and ready to process.\n\n"
                "You can now unplug the USB drive.",
            )
            self.app.show_screen("QueueScreen")
        except Exception as exc:
            log.exception("Import failed")
            messagebox.showerror("Import Error", f"Could not import files:\n{exc}")
