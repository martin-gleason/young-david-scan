# Entry screen — split-pane PDF viewer + case-info form.
# This is the main work surface for the navigator.

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import database as db
from ..config import (
    C_BG,
    C_DANGER,
    C_MUTED,
    C_PRIMARY,
    C_SUCCESS,
    C_WHITE,
    COURTROOMS,
    FONT_BODY,
    FONT_H2,
    FONT_SMALL,
    PETITION_TYPES,
)
from ..dates import DateParseError, format_us_date, parse_us_date
from ..logging_setup import get_logger
from ._shared import btn, combo, entry, field_row, make_header

log = get_logger(__name__)


class EntryScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C_BG)
        self.app = app
        self._current_doc: dict | None = None
        self._linked_case_id: int | None = None
        self._found_case: dict | None = None
        self._pending_docs: list[dict] = []
        self._current_index: int = 0
        self._build()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        from ..pdf_viewer import PDFViewer

        header = make_header(self, "Document Entry")
        btn(
            header,
            "← Back to Queue",
            lambda: self.app.show_screen("QueueScreen"),
            primary=False,
            width=14,
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        self._queue_label = tk.Label(header, text="", bg=C_PRIMARY, fg="#aac4e0", font=FONT_BODY)
        self._queue_label.pack(side=tk.RIGHT, padx=10)

        pane = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bg="#cccccc"
        )
        pane.pack(fill=tk.BOTH, expand=True)

        self._viewer = PDFViewer(pane)
        pane.add(self._viewer, minsize=400, width=620)

        form_outer = tk.Frame(pane, bg=C_BG)
        pane.add(form_outer, minsize=340)
        self._build_form(form_outer)

    def _build_form(self, parent):
        canvas = tk.Canvas(parent, bg=C_WHITE, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)

        self._form_frame = tk.Frame(canvas, bg=C_WHITE, padx=16, pady=12)
        canvas.create_window((0, 0), window=self._form_frame, anchor="nw")
        self._form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        f = self._form_frame

        self._doc_name_var = tk.StringVar()
        tk.Label(
            f,
            textvariable=self._doc_name_var,
            bg=C_WHITE,
            fg=C_MUTED,
            font=FONT_SMALL,
            wraplength=300,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(f, text="Case Information", bg=C_WHITE, fg=C_PRIMARY, font=FONT_H2).pack(
            anchor="w", pady=(0, 8)
        )

        _, self._last_name_entry = field_row(f, "Last Name *", lambda p: entry(p, width=22))
        _, self._courtroom_combo = field_row(
            f, "Courtroom *", lambda p: combo(p, COURTROOMS, width=20)
        )
        _, self._docket_entry = field_row(f, "Docket # *", lambda p: entry(p, width=22))
        _, self._date_entry = field_row(
            f, "Case Date *\n(MM/DD/YYYY)", lambda p: entry(p, width=14)
        )
        _, self._petition_combo = field_row(
            f, "Petition Type", lambda p: combo(p, PETITION_TYPES, width=20)
        )
        _, self._notes_entry = field_row(f, "Notes", lambda p: entry(p, width=22))

        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 8))
        tk.Label(f, text="Link to Existing Case", bg=C_WHITE, fg=C_PRIMARY, font=FONT_H2).pack(
            anchor="w", pady=(0, 4)
        )
        tk.Label(
            f,
            text="If this document belongs to an existing case,\n" "search by docket # to link it.",
            bg=C_WHITE,
            fg=C_MUTED,
            font=FONT_SMALL,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        link_row = tk.Frame(f, bg=C_WHITE)
        link_row.pack(fill=tk.X, pady=2)
        self._link_entry = entry(link_row, width=16)
        self._link_entry.pack(side=tk.LEFT, padx=(0, 6))
        btn(link_row, "Find", self._find_case, primary=False, width=6).pack(side=tk.LEFT)

        self._link_result_var = tk.StringVar()
        self._link_result_label = tk.Label(
            f,
            textvariable=self._link_result_var,
            bg=C_WHITE,
            fg=C_SUCCESS,
            font=FONT_SMALL,
            wraplength=280,
            justify="left",
        )
        self._link_result_label.pack(anchor="w", pady=4)

        self._link_btn = btn(f, "✓  Link to This Case", self._apply_link, primary=True, width=22)
        self._link_btn.pack(pady=4)
        self._link_btn.pack_forget()

        self._unlink_btn = btn(f, "✕  Unlink", self._clear_link, primary=False, width=12)
        self._unlink_btn.pack(pady=2)
        self._unlink_btn.pack_forget()

        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 8))
        btn(f, "💾  Save & Next", self._save_and_next, primary=True, width=22).pack(pady=4)
        btn(f, "Skip (come back later)", self._skip, primary=False, width=22).pack(pady=2)

        self._error_var = tk.StringVar()
        tk.Label(
            f,
            textvariable=self._error_var,
            bg=C_WHITE,
            fg=C_DANGER,
            font=FONT_SMALL,
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=4)

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self, doc_id: int | None = None, **_):
        """Load the queue and jump to the given doc_id (or first pending)."""
        self._pending_docs = db.get_pending_documents()
        if doc_id is not None:
            self._current_index = next(
                (i for i, d in enumerate(self._pending_docs) if d["id"] == doc_id),
                0,
            )
        else:
            self._current_index = 0
        self._load_current()

    # ── Internal navigation ───────────────────────────────────────────────

    def _load_current(self):
        if not self._pending_docs:
            self._viewer.close()
            messagebox.showinfo("Queue Empty", "All documents have been processed!")
            self.app.show_screen("HomeScreen")
            return

        doc = self._pending_docs[self._current_index]
        self._current_doc = doc
        self._linked_case_id = None

        total = len(self._pending_docs)
        pos = self._current_index + 1
        self._queue_label.config(text=f"Document {pos} of {total} pending")

        self._doc_name_var.set(doc["original_filename"])

        pdf_path = Path(doc["stored_path"])
        if pdf_path.exists():
            self._viewer.load(pdf_path)
        else:
            self._viewer.close()
            messagebox.showwarning(
                "File Not Found",
                f"The PDF file could not be found:\n{pdf_path}\n\n"
                "You can still enter the case data manually.",
            )

        self._clear_form()

    def _clear_form(self):
        for widget in (
            self._last_name_entry,
            self._docket_entry,
            self._date_entry,
            self._notes_entry,
            self._link_entry,
        ):
            widget.delete(0, tk.END)
        self._courtroom_combo.current(0)
        self._petition_combo.current(0)
        self._link_result_var.set("")
        self._link_btn.pack_forget()
        self._unlink_btn.pack_forget()
        self._error_var.set("")
        self._linked_case_id = None
        self._set_fields_editable(True)

    def _set_fields_editable(self, editable: bool):
        state = tk.NORMAL if editable else "readonly"
        combo_state = "readonly" if editable else "disabled"
        for w in (self._last_name_entry, self._docket_entry, self._date_entry, self._notes_entry):
            w.config(state=state)
        for cb in (self._courtroom_combo, self._petition_combo):
            cb.config(state=combo_state)

    # ── Case linking ──────────────────────────────────────────────────────

    def _find_case(self):
        docket = self._link_entry.get().strip()
        if not docket:
            self._link_result_var.set("Enter a docket number to search.")
            self._link_result_label.config(fg=C_DANGER)
            return

        case = db.get_case_by_docket(docket)
        if case:
            self._found_case = case
            self._link_result_var.set(
                f"Found:  {case['last_name']}  |  {case['docket_number']}"
                f"\n{case['courtroom']}  |  {format_us_date(case['case_date'])}"
            )
            self._link_result_label.config(fg=C_SUCCESS)
            self._link_btn.pack(pady=4)
            self._unlink_btn.pack_forget()
        else:
            self._found_case = None
            self._link_result_var.set(
                "No case found with that docket number.\n"
                "Fill the form above to create a new case."
            )
            self._link_result_label.config(fg=C_DANGER)
            self._link_btn.pack_forget()

    def _apply_link(self):
        if not self._found_case:
            return
        case = self._found_case
        self._linked_case_id = case["id"]

        self._set_fields_editable(False)
        for w in (self._last_name_entry, self._docket_entry, self._date_entry):
            w.config(state=tk.NORMAL)
            w.delete(0, tk.END)
        self._last_name_entry.insert(0, case["last_name"])
        self._docket_entry.insert(0, case["docket_number"])
        self._date_entry.insert(0, format_us_date(case["case_date"]))

        if case["courtroom"] in COURTROOMS:
            self._courtroom_combo.set(case["courtroom"])
        self._set_fields_editable(False)

        self._link_result_var.set(
            f"✓  Linked to case: {case['last_name']} / {case['docket_number']}"
        )
        self._link_result_label.config(fg=C_SUCCESS)
        self._link_btn.pack_forget()
        self._unlink_btn.pack(pady=2)

    def _clear_link(self):
        self._linked_case_id = None
        self._found_case = None
        self._set_fields_editable(True)
        self._link_result_var.set("")
        self._link_btn.pack_forget()
        self._unlink_btn.pack_forget()
        self._clear_form()

    # ── Save & Skip ───────────────────────────────────────────────────────

    def _validate(self) -> bool:
        """Run field-level checks. Returns True iff inputs are usable."""
        errors = []
        if not self._last_name_entry.get().strip():
            errors.append("Last Name is required.")
        if not self._docket_entry.get().strip():
            errors.append("Docket # is required.")
        date_raw = self._date_entry.get().strip()
        if not date_raw:
            errors.append("Case Date is required.")
        else:
            try:
                parse_us_date(date_raw)
            except DateParseError as exc:
                errors.append(str(exc))
        if errors:
            self._error_var.set("\n".join(errors))
            return False
        self._error_var.set("")
        return True

    def _save_and_next(self):
        if not self._current_doc:
            return
        if not self._validate():
            return

        last_name = self._last_name_entry.get().strip()
        courtroom = self._courtroom_combo.get()
        docket = self._docket_entry.get().strip()
        case_date = parse_us_date(self._date_entry.get().strip())
        petition = self._petition_combo.get()
        notes = self._notes_entry.get().strip()

        try:
            if self._linked_case_id:
                case_id = self._linked_case_id
            else:
                existing = db.get_case_by_docket(docket)
                if existing:
                    case_id = existing["id"]
                else:
                    case_id = db.create_case(last_name, courtroom, docket, case_date, notes)
            db.complete_document(self._current_doc["id"], case_id, petition)
        except Exception as exc:
            log.exception("Save failed")
            messagebox.showerror("Save Error", f"Could not save:\n{exc}")
            return

        self._pending_docs = db.get_pending_documents()
        if self._current_index >= len(self._pending_docs):
            self._current_index = 0

        if not self._pending_docs:
            messagebox.showinfo("Queue Complete", "All documents processed! Great work.")
            self.app.show_screen("HomeScreen")
        else:
            self._load_current()

    def _skip(self):
        if not self._current_doc:
            return
        db.skip_document(self._current_doc["id"])
        self._pending_docs = db.get_pending_documents()
        if self._current_index >= len(self._pending_docs):
            self._current_index = 0
        if not self._pending_docs:
            messagebox.showinfo("Queue Complete", "All remaining documents have been skipped.")
            self.app.show_screen("HomeScreen")
        else:
            self._load_current()
