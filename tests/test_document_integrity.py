"""SHA-256 storage on import + verification on open + mismatch audit."""

import pytest

from court_cataloguer import database, utils


def test_import_pdfs_stores_sha256(fresh_db, tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    monkeypatch.setattr(utils, "ARCHIVE_DIR", archive)

    src = tmp_path / "case.pdf"
    src.write_bytes(b"%PDF-1.4 hello world")

    [doc_id] = utils.import_pdfs([src])
    with database._connect() as conn:
        row = conn.execute(
            "SELECT sha256, imported_by, import_machine FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
    assert row["sha256"] and len(row["sha256"]) == 64
    assert row["imported_by"]
    assert row["import_machine"]


def test_verify_matches_returns_true(fresh_db, tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    monkeypatch.setattr(utils, "ARCHIVE_DIR", archive)
    src = tmp_path / "ok.pdf"
    src.write_bytes(b"%PDF-1.4 content")

    [doc_id] = utils.import_pdfs([src])
    doc = database.get_documents_for_case(0)  # unlinked yet
    # Fetch by id instead.
    with database._connect() as conn:
        doc = dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())

    assert utils.verify_pdf_integrity(doc) is True


def test_verify_mismatch_returns_false_and_audits(fresh_db, tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    monkeypatch.setattr(utils, "ARCHIVE_DIR", archive)
    src = tmp_path / "ok.pdf"
    src.write_bytes(b"%PDF-1.4 original")

    [doc_id] = utils.import_pdfs([src])
    with database._connect() as conn:
        doc = dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())

    # Tamper with the file on disk after import.
    from pathlib import Path

    Path(doc["stored_path"]).write_bytes(b"%PDF-1.4 TAMPERED")

    assert utils.verify_pdf_integrity(doc) is False

    # An audit row should have been recorded.
    with database._connect() as conn:
        rows = conn.execute(
            "SELECT target_id FROM audit_log WHERE action = 'integrity.mismatch'"
        ).fetchall()
    assert any(r["target_id"] == doc_id for r in rows)


def test_verify_backfills_null_sha256(fresh_db, tmp_path, monkeypatch):
    """A doc imported pre-Phase-4 has NULL sha256. First open backfills."""
    archive = tmp_path / "archive"
    monkeypatch.setattr(utils, "ARCHIVE_DIR", archive)
    archive.mkdir(parents=True)
    path = archive / "legacy.pdf"
    path.write_bytes(b"%PDF-1.4 legacy")

    # Insert document without sha256 (simulating pre-Phase-4 row).
    doc_id = database.add_document("legacy.pdf", str(path))
    # Wipe the audit-noise sha256_prefix; pre-Phase-4 would have stored NULL.
    with database._connect() as conn:
        conn.execute("UPDATE documents SET sha256 = NULL WHERE id = ?", (doc_id,))
        conn.commit()
        doc = dict(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())

    assert doc["sha256"] is None
    assert utils.verify_pdf_integrity(doc) is True

    # And the row now has a sha256.
    with database._connect() as conn:
        backfilled = conn.execute(
            "SELECT sha256 FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()["sha256"]
    assert backfilled and len(backfilled) == 64


def test_set_sha256_refuses_to_overwrite(fresh_db):
    doc_id = database.add_document("z.pdf", "/tmp/z.pdf", sha256="a" * 64)
    with pytest.raises(ValueError, match="already has"):
        database.set_document_sha256(doc_id, "b" * 64)
