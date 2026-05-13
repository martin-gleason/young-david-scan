# Search screen — query cases and inspect their documents.

import contextlib
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import audit, utils
from .. import database as db
from ..config import (
    C_BG,
    C_MUTED,
    C_PRIMARY,
    C_ROW_ALT,
    C_TEXT,
    C_WHITE,
    FONT_BODY,
    FONT_H2,
    FONT_LABEL,
    FONT_SMALL,
)
from ..dates import DateParseError, format_us_date, parse_us_date
from ._shared import btn, entry, make_header


class SearchScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._fields: dict[str, tk.Entry] = {}
        self._build()

    def _build(self):
        header = make_header(self, "Search Cases")
        btn(
            header, "← Back", lambda: self.app.show_screen("HomeScreen"), primary=False, width=10
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        form = tk.Frame(self, bg=C_WHITE, padx=16, pady=12)
        form.pack(fill=tk.X, padx=20, pady=12)

        row1 = tk.Frame(form, bg=C_WHITE)
        row1.pack(fill=tk.X, pady=4)

        for label, key in [
            ("Last Name", "last_name"),
            ("Docket #", "docket"),
            ("Courtroom", "courtroom"),
        ]:
            tk.Label(
                row1, text=label, bg=C_WHITE, fg=C_TEXT, font=FONT_LABEL, width=12, anchor="e"
            ).pack(side=tk.LEFT, padx=(8, 4))
            e = entry(row1, width=18)
            e.pack(side=tk.LEFT, padx=(0, 12))
            self._fields[key] = e

        row2 = tk.Frame(form, bg=C_WHITE)
        row2.pack(fill=tk.X, pady=4)
        tk.Label(
            row2, text="Date From", bg=C_WHITE, fg=C_TEXT, font=FONT_LABEL, width=12, anchor="e"
        ).pack(side=tk.LEFT, padx=(8, 4))
        self._fields["date_from"] = entry(row2, width=14)
        self._fields["date_from"].pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(
            row2, text="Date To", bg=C_WHITE, fg=C_TEXT, font=FONT_LABEL, width=10, anchor="e"
        ).pack(side=tk.LEFT, padx=(8, 4))
        self._fields["date_to"] = entry(row2, width=14)
        self._fields["date_to"].pack(side=tk.LEFT, padx=(0, 12))

        btn(row2, "🔍  Search", self._run_search, primary=True, width=14).pack(
            side=tk.LEFT, padx=16
        )
        btn(row2, "Clear", self._clear_search, primary=False, width=8).pack(side=tk.LEFT)

        tree_frame = tk.Frame(self, bg=C_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))

        self._count_var = tk.StringVar(value="")
        tk.Label(
            tree_frame, textvariable=self._count_var, bg=C_BG, fg=C_MUTED, font=FONT_SMALL
        ).pack(anchor="w")

        cols = ("last_name", "courtroom", "docket", "case_date", "docs")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        headers = {
            "last_name": ("Last Name", 160),
            "courtroom": ("Courtroom", 130),
            "docket": ("Docket #", 160),
            "case_date": ("Case Date", 120),
            "docs": ("# Docs", 70),
        }
        for col, (text, width) in headers.items():
            self._tree.heading(col, text=text)
            anchor = "center" if col == "docs" else "w"
            self._tree.column(col, width=width, anchor=anchor)

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        self._tree.bind("<Double-1>", lambda _: self._view_case())

        btn_row = tk.Frame(self, bg=C_BG)
        btn_row.pack(pady=8)
        btn(btn_row, "View Documents for Case", self._view_case, primary=True, width=26).pack()

    def refresh(self, **_):
        self._run_search()

    def _run_search(self):
        date_from, date_to = self._parsed_date_bounds()
        if (
            date_from is None
            and date_to is None
            and (self._fields["date_from"].get().strip() or self._fields["date_to"].get().strip())
        ):
            # Bad input already reported via _count_var; stop.
            return

        results = db.search_cases(
            last_name=self._fields["last_name"].get().strip(),
            docket=self._fields["docket"].get().strip(),
            courtroom=self._fields["courtroom"].get().strip(),
            date_from=date_from or "",
            date_to=date_to or "",
        )
        self._tree.delete(*self._tree.get_children())
        self._count_var.set(f"{len(results)} case(s) found")

        for i, case in enumerate(results):
            docs = db.get_documents_for_case(case["id"])
            tag = "alt" if i % 2 == 0 else ""
            self._tree.insert(
                "",
                tk.END,
                iid=str(case["id"]),
                values=(
                    case["last_name"],
                    case["courtroom"],
                    case["docket_number"],
                    format_us_date(case["case_date"]),
                    len(docs),
                ),
                tags=(tag,),
            )
        self._tree.tag_configure("alt", background=C_ROW_ALT)

    def _parsed_date_bounds(self) -> tuple[str | None, str | None]:
        """Parse the date_from / date_to entries into ISO. Returns (from, to).

        Either side may be empty (None). If either side is non-empty but
        unparseable, sets the count label to an error message and returns
        (None, None) so the caller can abort the search.
        """
        raw_from = self._fields["date_from"].get().strip()
        raw_to = self._fields["date_to"].get().strip()
        try:
            iso_from = parse_us_date(raw_from) if raw_from else None
            iso_to = parse_us_date(raw_to) if raw_to else None
        except DateParseError as exc:
            self._count_var.set(f"Date error: {exc}")
            return None, None
        return iso_from, iso_to

    def _clear_search(self):
        for w in self._fields.values():
            w.delete(0, tk.END)
        self._run_search()

    def _view_case(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a case row first.")
            return
        case_id = int(sel[0])
        case = db.get_case_by_id(case_id)
        docs = db.get_documents_for_case(case_id)
        self._show_case_popup(case, docs)

    def _show_case_popup(self, case: dict, docs: list[dict]):
        popup = tk.Toplevel(self)
        popup.title(f"Case: {case['last_name']} — {case['docket_number']}")
        popup.geometry("640x480")
        popup.resizable(True, True)
        popup.configure(bg=C_BG)
        popup.grab_set()

        make_header(
            popup, f"{case['last_name']}", f"{case['docket_number']}  |  {case['courtroom']}"
        )

        info = tk.Frame(popup, bg=C_WHITE, padx=16, pady=10)
        info.pack(fill=tk.X, padx=16, pady=12)

        for label, val in [
            ("Courtroom", case["courtroom"]),
            ("Docket #", case["docket_number"]),
            ("Case Date", format_us_date(case["case_date"])),
            ("Created", case["created_at"]),
            ("Notes", case.get("notes", "")),
        ]:
            row = tk.Frame(info, bg=C_WHITE)
            row.pack(fill=tk.X, pady=2)
            tk.Label(
                row, text=f"{label}:", bg=C_WHITE, fg=C_MUTED, font=FONT_LABEL, width=14, anchor="e"
            ).pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(row, text=val, bg=C_WHITE, fg=C_TEXT, font=FONT_BODY, anchor="w").pack(
                side=tk.LEFT
            )

        tk.Label(popup, text=f"Documents ({len(docs)})", bg=C_BG, fg=C_PRIMARY, font=FONT_H2).pack(
            anchor="w", padx=16
        )

        doc_frame = tk.Frame(popup, bg=C_BG)
        doc_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 8))

        doc_cols = ("type", "filename", "imported")
        doc_tree = ttk.Treeview(doc_frame, columns=doc_cols, show="headings", height=6)
        doc_tree.heading("type", text="Petition Type")
        doc_tree.heading("filename", text="Filename")
        doc_tree.heading("imported", text="Imported")
        doc_tree.column("type", width=200)
        doc_tree.column("filename", width=200)
        doc_tree.column("imported", width=160)

        for doc in docs:
            doc_tree.insert(
                "",
                tk.END,
                iid=str(doc["id"]),
                values=(
                    doc.get("petition_type", ""),
                    doc["original_filename"],
                    doc["imported_at"],
                ),
            )

        doc_tree.pack(fill=tk.BOTH, expand=True)

        def open_pdf():
            sel = doc_tree.selection()
            if not sel:
                return
            doc_id = int(sel[0])
            matched = [d for d in docs if d["id"] == doc_id]
            if not matched:
                return
            doc = matched[0]
            path = Path(doc["stored_path"])
            if not path.exists():
                messagebox.showwarning("File Not Found", f"Cannot find file:\n{path}")
                return
            if path.suffix.lower() != ".pdf":
                messagebox.showwarning("Refusing to Open", f"Stored path is not a PDF:\n{path}")
                return
            verified = utils.verify_pdf_integrity(doc)
            if not verified:
                proceed = messagebox.askyesno(
                    "Integrity Warning",
                    "This PDF's contents differ from what was recorded at import time. "
                    "The discrepancy has been logged. Open it anyway?",
                )
                if not proceed:
                    return
            with contextlib.suppress(Exception):
                # Don't block the open on audit failure; the file logger
                # still has the event via get_logger.
                audit.append_standalone(
                    "doc.open",
                    target_table="documents",
                    target_id=doc_id,
                    details={"verified": verified, "via": "search"},
                )
            os.startfile(str(path))

        btn_row = tk.Frame(popup, bg=C_BG)
        btn_row.pack(pady=8)
        btn(btn_row, "📄  Open PDF", open_pdf, primary=False, width=14).pack(side=tk.LEFT, padx=8)
        btn(btn_row, "Close", popup.destroy, primary=True, width=10).pack(side=tk.LEFT, padx=8)
