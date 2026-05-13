"""Smoke tests for the DB layer. Real schema, tmp file, no mocks."""

from court_cataloguer import database as db


def test_init_db_creates_tables(fresh_db):
    # init_db ran in the fixture; a second call must be idempotent.
    db.init_db()

    # Inserting + reading round-trips.
    case_id = db.create_case(
        last_name="Doe",
        courtroom="Courtroom 1",
        docket_number="2024-JA-000001",
        case_date="2024-05-12",
        notes="initial intake",
    )
    assert isinstance(case_id, int)

    fetched = db.get_case_by_id(case_id)
    assert fetched is not None
    assert fetched["last_name"] == "Doe"
    assert fetched["docket_number"] == "2024-JA-000001"


def test_search_cases_filters_by_last_name(fresh_db):
    db.create_case("Smith", "Courtroom 1", "2024-JA-1001", "2024-01-15")
    db.create_case("Smithers", "Courtroom 2", "2024-JA-1002", "2024-02-20")
    db.create_case("Jones", "Courtroom 1", "2024-JA-1003", "2024-03-10")

    results = db.search_cases(last_name="Smith")
    names = {r["last_name"] for r in results}
    assert names == {"Smith", "Smithers"}


def test_queue_summary_counts_by_status(fresh_db):
    a = db.add_document("a.pdf", "/tmp/a.pdf")
    db.add_document("b.pdf", "/tmp/b.pdf")
    db.skip_document(a)

    summary = db.get_queue_summary()
    assert summary["pending"] == 1
    assert summary["skipped"] == 1
    assert summary["complete"] == 0
    assert summary["total"] == 2
