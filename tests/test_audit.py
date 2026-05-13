"""Audit chain mechanics: append, verify, tamper detection."""

import pytest

from court_cataloguer import audit, database


def _all_rows():
    with database._connect() as conn:
        return conn.execute(
            """SELECT id, action, this_hmac, prev_hmac, details_json
               FROM audit_log ORDER BY id"""
        ).fetchall()


def test_append_writes_row_with_hmac(fresh_db):
    audit.append_standalone("test.action", details={"k": "v"})
    rows = _all_rows()
    # fresh_db.init_db ran migrations + may have produced 0 rows of its own.
    test_rows = [r for r in rows if r["action"] == "test.action"]
    assert len(test_rows) == 1
    r = test_rows[0]
    assert r["this_hmac"]  # non-empty
    assert len(r["this_hmac"]) == 64  # SHA-256 hex


def test_verify_clean_chain(fresh_db):
    audit.append_standalone("test.one")
    audit.append_standalone("test.two")
    audit.append_standalone("test.three")
    result = audit.verify_chain()
    assert result.ok
    assert result.row_count >= 3
    assert result.first_broken_id is None


def test_verify_empty_chain(fresh_db):
    # No appends, but fresh_db already calls init_db; migrations don't audit
    # so the table may be empty. Verify must still succeed.
    result = audit.verify_chain()
    assert result.ok


def test_tamper_detected(fresh_db):
    audit.append_standalone("test.before")
    audit.append_standalone("test.tamper_target", details={"original": "good"})
    audit.append_standalone("test.after")

    # Hand-edit details_json on the middle row.
    with database._connect() as conn:
        target_id = conn.execute(
            "SELECT id FROM audit_log WHERE action = 'test.tamper_target'"
        ).fetchone()[0]
        conn.execute(
            "UPDATE audit_log SET details_json = ? WHERE id = ?",
            ('{"original":"tampered"}', target_id),
        )
        conn.commit()

    result = audit.verify_chain()
    assert not result.ok
    assert result.first_broken_id == target_id


def test_chain_prev_hmac_links_consecutive_rows(fresh_db):
    audit.append_standalone("test.a")
    audit.append_standalone("test.b")
    rows = [r for r in _all_rows() if r["action"].startswith("test.")]
    assert len(rows) == 2
    assert rows[1]["prev_hmac"] == rows[0]["this_hmac"]


def test_signing_requires_master_key(fresh_db):
    database.clear_master_key()
    with pytest.raises(RuntimeError):
        audit.append_standalone("test.no_key")


def test_actor_and_machine_populated(fresh_db, monkeypatch):
    monkeypatch.setenv("USERNAME", "test-user")
    audit.append_standalone("test.identity")
    with database._connect() as conn:
        row = conn.execute(
            "SELECT actor, machine FROM audit_log WHERE action = 'test.identity'"
        ).fetchone()
    assert row["actor"] == "test-user"
    assert row["machine"]  # platform.node() returns something on every test host
