"""utils.import_pdfs must roll back the file copy if the DB insert fails."""

import pytest

from court_cataloguer import database as db
from court_cataloguer import utils


def test_orphan_pdf_removed_when_db_insert_fails(fresh_db, monkeypatch, tmp_path):
    # Redirect the archive into the test's tmp dir so we don't write to
    # the real C:\CourtDocCataloguer\ tree.
    archive = tmp_path / "archive"
    monkeypatch.setattr(utils, "ARCHIVE_DIR", archive)

    src = tmp_path / "case-12345.pdf"
    src.write_bytes(b"%PDF-1.4 fake")

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(db, "add_document", boom)

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        utils.import_pdfs([src])

    # The destination file in the archive must NOT exist after rollback.
    leftover = list(archive.rglob("*.pdf"))
    assert leftover == [], f"expected zero PDFs in archive, found: {leftover}"


def test_successful_import_returns_doc_ids(fresh_db, monkeypatch, tmp_path):
    archive = tmp_path / "archive"
    monkeypatch.setattr(utils, "ARCHIVE_DIR", archive)

    src = tmp_path / "case-99.pdf"
    src.write_bytes(b"%PDF-1.4 fake")

    ids = utils.import_pdfs([src])
    assert len(ids) == 1
    assert isinstance(ids[0], int)

    # And the file is present in the archive.
    leftover = list(archive.rglob("*.pdf"))
    assert len(leftover) == 1
