# Shared widget factories used by every screen.
# Keep visual conventions here — colours, fonts, button shapes — so the rest
# of the screen code stays focused on layout and behaviour.

import tkinter as tk
from tkinter import ttk

from ..config import (
    C_ACCENT,
    C_PRIMARY,
    C_TEXT,
    C_WHITE,
    FONT_BODY,
    FONT_LABEL,
    FONT_TITLE,
)


def make_header(parent, title: str, subtitle: str = "") -> tk.Frame:
    """Navy header bar with a title and optional subtitle."""
    bar = tk.Frame(parent, bg=C_PRIMARY)
    bar.pack(fill=tk.X)
    tk.Label(bar, text=title, bg=C_PRIMARY, fg="white", font=FONT_TITLE, pady=10, padx=20).pack(
        side=tk.LEFT
    )
    if subtitle:
        tk.Label(bar, text=subtitle, bg=C_PRIMARY, fg="#aac4e0", font=FONT_BODY, padx=10).pack(
            side=tk.LEFT
        )
    return bar


def btn(parent, text: str, cmd, primary: bool = True, width: int = 18) -> tk.Button:
    """Styled button — primary (navy) or secondary (gold)."""
    bg = C_PRIMARY if primary else C_ACCENT
    fg = "white" if primary else "black"
    return tk.Button(
        parent,
        text=text,
        command=cmd,
        bg=bg,
        fg=fg,
        activebackground=C_ACCENT,
        activeforeground="black",
        font=FONT_BODY,
        relief=tk.FLAT,
        cursor="hand2",
        padx=12,
        pady=8,
        width=width,
    )


def field_row(parent, label: str, widget_factory) -> tuple[tk.Frame, tk.Widget]:
    """Label + widget on a single row, returned as (row_frame, widget)."""
    row = tk.Frame(parent, bg=C_WHITE)
    row.pack(fill=tk.X, pady=3)
    tk.Label(row, text=label, bg=C_WHITE, fg=C_TEXT, font=FONT_LABEL, width=16, anchor="e").pack(
        side=tk.LEFT, padx=(0, 6)
    )
    widget = widget_factory(row)
    widget.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    return row, widget


def entry(parent, **kwargs) -> tk.Entry:
    return tk.Entry(parent, font=FONT_BODY, relief=tk.SOLID, bd=1, bg=C_WHITE, **kwargs)


def combo(parent, values: list[str], **kwargs) -> ttk.Combobox:
    cb = ttk.Combobox(parent, values=values, state="readonly", font=FONT_BODY, **kwargs)
    if values:
        cb.current(0)
    return cb
