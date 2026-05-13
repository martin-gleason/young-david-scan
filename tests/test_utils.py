"""Tests for the parts of utils.py that don't need Windows APIs."""

import sys

from court_cataloguer.utils import _safe_copy, get_removable_drives


def test_safe_copy_renames_on_collision(tmp_path):
    src_a = tmp_path / "a.pdf"
    src_a.write_bytes(b"first")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    first = _safe_copy(src_a, dest_dir)
    assert first.name == "a.pdf"

    # Second copy of a file with the same name must not overwrite the first.
    src_b = tmp_path / "a.pdf"  # same path → same name on dest
    second = _safe_copy(src_b, dest_dir)
    assert second.name == "a_v2.pdf"
    assert second != first
    assert first.read_bytes() == b"first"

    # Third copy bumps to _v3.
    third = _safe_copy(src_b, dest_dir)
    assert third.name == "a_v3.pdf"


def test_get_removable_drives_safe_on_non_windows():
    if sys.platform != "win32":
        assert get_removable_drives() == []
    else:
        # On Windows we can't assert a specific result, but we can assert
        # the call returns a list and doesn't crash.
        result = get_removable_drives()
        assert isinstance(result, list)
