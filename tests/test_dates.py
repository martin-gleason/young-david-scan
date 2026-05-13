"""Tests for the dates parse/format helpers."""

import pytest

from court_cataloguer.dates import (
    DateParseError,
    format_us_date,
    is_iso_date,
    parse_us_date,
)


class TestParseUsDate:
    def test_canonical_form(self):
        assert parse_us_date("05/12/2024") == "2024-05-12"

    def test_single_digit_components(self):
        assert parse_us_date("5/2/2024") == "2024-05-02"

    def test_whitespace_tolerated(self):
        assert parse_us_date("  05/12/2024  ") == "2024-05-12"

    def test_two_digit_year_2000s(self):
        assert parse_us_date("05/12/24") == "2024-05-12"
        assert parse_us_date("05/12/00") == "2000-05-12"
        assert parse_us_date("05/12/69") == "2069-05-12"

    def test_two_digit_year_1900s(self):
        assert parse_us_date("05/12/70") == "1970-05-12"
        assert parse_us_date("05/12/99") == "1999-05-12"

    def test_iso_passthrough(self):
        # Already-ISO input is accepted and returned as-is.
        assert parse_us_date("2024-05-12") == "2024-05-12"

    def test_iso_invalid_calendar_rejected(self):
        with pytest.raises(DateParseError):
            parse_us_date("2024-02-30")

    @pytest.mark.parametrize(
        "bad",
        ["", "   ", "garbage", "05-12-2024", "2024/05/12", "13/45/2024", "02/30/2024"],
    )
    def test_invalid(self, bad):
        with pytest.raises(DateParseError):
            parse_us_date(bad)

    def test_none_rejected(self):
        with pytest.raises(DateParseError):
            parse_us_date(None)


class TestFormatUsDate:
    def test_canonical(self):
        assert format_us_date("2024-05-12") == "05/12/2024"

    def test_pads_components(self):
        assert format_us_date("2024-01-05") == "01/05/2024"

    def test_empty(self):
        assert format_us_date("") == ""

    def test_unparseable_passes_through(self):
        # We prefer to show the raw value rather than silently lose data.
        assert format_us_date("not-a-date") == "not-a-date"


class TestIsIsoDate:
    def test_valid(self):
        assert is_iso_date("2024-05-12")

    def test_invalid(self):
        assert not is_iso_date("05/12/2024")
        assert not is_iso_date("2024-02-30")
        assert not is_iso_date("")
        assert not is_iso_date("2024-5-12")  # not zero-padded
