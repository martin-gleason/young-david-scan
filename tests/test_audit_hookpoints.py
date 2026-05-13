"""Each wrapped DB write produces exactly one audit row, no PII in details."""

from court_cataloguer import audit, database


def _rows_for(action: str):
    with database._connect() as conn:
        return conn.execute(
            "SELECT id, target_table, target_id, details_json "
            "FROM audit_log WHERE action = ? ORDER BY id",
            (action,),
        ).fetchall()


def test_create_case_appends_case_create(fresh_db):
    before = len(_rows_for("case.create"))
    case_id = database.create_case("Doe", "Courtroom 1", "AUDIT-1", "2024-05-12")
    after = _rows_for("case.create")
    assert len(after) == before + 1
    row = after[-1]
    assert row["target_table"] == "cases"
    assert row["target_id"] == case_id


def test_add_document_appends_doc_import(fresh_db):
    before = len(_rows_for("doc.import"))
    doc_id = database.add_document("x.pdf", "/tmp/x.pdf", sha256="a" * 64)
    after = _rows_for("doc.import")
    assert len(after) == before + 1
    assert after[-1]["target_id"] == doc_id


def test_complete_document_appends_doc_complete(fresh_db):
    case_id = database.create_case("Doe", "Courtroom 1", "HOOK-C", "2024-05-12")
    doc_id = database.add_document("x.pdf", "/tmp/x.pdf")
    before = len(_rows_for("doc.complete"))
    database.complete_document(doc_id, case_id, "Petition for Adjudication — Neglect")
    after = _rows_for("doc.complete")
    assert len(after) == before + 1
    assert after[-1]["target_id"] == doc_id
    assert f'"case_id":{case_id}' in after[-1]["details_json"]


def test_skip_document_appends_doc_skip(fresh_db):
    doc_id = database.add_document("y.pdf", "/tmp/y.pdf")
    before = len(_rows_for("doc.skip"))
    database.skip_document(doc_id)
    after = _rows_for("doc.skip")
    assert len(after) == before + 1
    assert after[-1]["target_id"] == doc_id


def test_no_pii_in_details_json(fresh_db):
    """Surnames + docket numbers should never appear in audit details."""
    database.create_case("Sensitive-Lastname", "Courtroom 1", "24-JA-9876", "2024-05-12")
    with database._connect() as conn:
        rows = conn.execute("SELECT details_json FROM audit_log").fetchall()
    blob = "".join(r["details_json"] for r in rows)
    assert "Sensitive-Lastname" not in blob
    assert "24-JA-9876" not in blob


def test_chain_stays_consistent_across_writes(fresh_db):
    """Multiple wrapped operations leave a verifying chain behind."""
    case_id = database.create_case("Doe", "Courtroom 1", "FLOW-1", "2024-05-12")
    doc_id = database.add_document("z.pdf", "/tmp/z.pdf", sha256="b" * 64)
    database.complete_document(doc_id, case_id, "Other")
    database.skip_document(database.add_document("w.pdf", "/tmp/w.pdf"))

    result = audit.verify_chain()
    assert result.ok
    assert result.row_count >= 5  # create_case + 2 imports + complete + skip
