"""Date parsing and formatting at the UI ↔ storage boundary.

Storage format: ISO 8601 `YYYY-MM-DD` (sortable, comparable in SQL).
Display format: `MM/DD/YYYY` (what the navigator expects).

All functions here are pure — no I/O, no logging — so they're cheap to test
and safe to call from anywhere in the UI.
"""

from __future__ import annotations

import re
from datetime import date

ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
US_PATTERN = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*$")


class DateParseError(ValueError):
    """Raised when an input string can't be interpreted as a valid date."""


def parse_us_date(text: str) -> str:
    """Parse a user-entered date string and return ISO `YYYY-MM-DD`.

    Accepted formats (with whitespace tolerated on the ends):
      - `MM/DD/YYYY`, `M/D/YYYY`, `MM/D/YYYY`, `M/DD/YYYY`
      - `MM/DD/YY`  → century inferred: 00–69 → 2000s, 70–99 → 1900s
      - `YYYY-MM-DD` (already-ISO is a no-op pass-through, for paste-friendliness)

    Raises DateParseError if the string can't be parsed or names an invalid
    calendar date (e.g. `02/30/2024`).
    """
    if text is None:
        raise DateParseError("Date is required.")
    s = text.strip()
    if not s:
        raise DateParseError("Date is required.")

    # Already ISO — validate calendar but accept.
    if ISO_PATTERN.match(s):
        try:
            date.fromisoformat(s)
        except ValueError as exc:
            raise DateParseError(f"Invalid date: {s}") from exc
        return s

    m = US_PATTERN.match(s)
    if not m:
        raise DateParseError(f"Date must be MM/DD/YYYY (got: {text!r}).")

    month_s, day_s, year_s = m.groups()
    month = int(month_s)
    day = int(day_s)
    year = int(year_s)
    if len(year_s) == 2:
        year += 2000 if year < 70 else 1900

    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise DateParseError(f"Invalid date: {text!r} ({exc})") from exc


def format_us_date(iso: str) -> str:
    """Format an ISO date string for display as `MM/DD/YYYY`.

    Falls back to returning the input unchanged if it's not parseable —
    we'd rather show the raw value than mask data we haven't migrated yet.
    """
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.month:02d}/{d.day:02d}/{d.year}"


def is_iso_date(value: str) -> bool:
    """True iff `value` is a syntactically valid `YYYY-MM-DD` calendar date."""
    if not value or not ISO_PATTERN.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True
