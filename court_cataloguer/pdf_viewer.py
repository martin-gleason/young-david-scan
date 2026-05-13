# Reusable Tkinter widget that renders a PDF file using PyMuPDF.

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .config import C_ACCENT, C_PRIMARY, FONT_SMALL
from .logging_setup import get_logger

log = get_logger(__name__)


class PDFViewer(tk.Frame):
    """
    A self-contained PDF viewer widget.

    Usage:
        viewer = PDFViewer(parent)
        viewer.pack(fill=tk.BOTH, expand=True)
        viewer.load(Path("some_file.pdf"))
        viewer.close()   # call before loading a new file
    """

    ZOOM_MIN = 0.5
    ZOOM_MAX = 3.0
    ZOOM_STEP = 0.25

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=C_PRIMARY, **kwargs)
        self._doc = None
        self._page_idx = 0
        self._zoom = 1.5
        self._photo_ref = None  # Must keep a reference or image is GC'd

        self._build_toolbar()
        self._build_canvas()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=C_PRIMARY, pady=4)
        bar.pack(fill=tk.X)

        self._lbl = tk.Label(
            bar,
            text="No document loaded",
            bg=C_PRIMARY,
            fg="white",
            font=FONT_SMALL,
            anchor="w",
        )
        self._lbl.pack(side=tk.LEFT, padx=10)

        btn_cfg = dict(
            bg="#2c4f7a",
            fg="white",
            font=FONT_SMALL,
            relief=tk.FLAT,
            activebackground=C_ACCENT,
            activeforeground="black",
            cursor="hand2",
            padx=6,
            pady=2,
        )

        for text, cmd in [
            ("◀ Prev", self._prev_page),
            ("Next ▶", self._next_page),
            ("  −  ", self._zoom_out),
            ("  +  ", self._zoom_in),
        ]:
            tk.Button(bar, text=text, command=cmd, **btn_cfg).pack(side=tk.RIGHT, padx=3)

    def _build_canvas(self):
        frame = tk.Frame(self, bg="#666")
        frame.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(frame, bg="#888", highlightthickness=0)
        sb_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._canvas.yview)
        sb_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self._canvas.xview)
        self._canvas.configure(
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
        )

        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

    # ── Public API ────────────────────────────────────────────────────────

    def load(self, path: Path) -> None:
        """Open a PDF file and display the first page."""
        self.close()
        try:
            import fitz  # PyMuPDF

            self._doc = fitz.open(str(path))
            self._page_idx = 0
            self._render()
        except ImportError:
            log.exception("PyMuPDF not installed")
            self._lbl.config(text="PyMuPDF not installed.")
        except Exception as exc:
            log.exception("Failed to open PDF")
            self._lbl.config(text=f"Cannot open PDF: {exc}")

    def close(self) -> None:
        """Release the open document."""
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                log.exception("Error closing PDF doc")
            self._doc = None
        self._photo_ref = None
        self._canvas.delete("all")
        self._lbl.config(text="No document loaded")

    # ── Internal rendering ────────────────────────────────────────────────

    def _render(self) -> None:
        if not self._doc:
            return
        try:
            import fitz
            from PIL import Image, ImageTk

            page = self._doc[self._page_idx]
            mat = fitz.Matrix(self._zoom, self._zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            self._photo_ref = ImageTk.PhotoImage(img)
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor=tk.NW, image=self._photo_ref)
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))

            total = len(self._doc)
            self._lbl.config(text=f"Page {self._page_idx + 1} of {total}")
        except Exception as exc:
            log.exception("PDF render error")
            self._lbl.config(text=f"Render error: {exc}")

    def _next_page(self) -> None:
        if self._doc and self._page_idx < len(self._doc) - 1:
            self._page_idx += 1
            self._render()

    def _prev_page(self) -> None:
        if self._doc and self._page_idx > 0:
            self._page_idx -= 1
            self._render()

    def _zoom_in(self) -> None:
        if self._zoom < self.ZOOM_MAX:
            self._zoom = round(self._zoom + self.ZOOM_STEP, 2)
            self._render()

    def _zoom_out(self) -> None:
        if self._zoom > self.ZOOM_MIN:
            self._zoom = round(self._zoom - self.ZOOM_STEP, 2)
            self._render()
