"""Tests for the auth orchestrator: startup mode + first_run + unlock."""

import pytest

from court_cataloguer import auth, crypto, database


@pytest.fixture
def empty_dir(tmp_path, monkeypatch):
    """A fresh data dir with no keyfile and no DB yet."""
    from court_cataloguer import config

    monkeypatch.setattr(config, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(config, "KEYFILE_PATH", tmp_path / "keyfile.json")
    monkeypatch.setattr(database, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(auth, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(auth, "KEYFILE_PATH", tmp_path / "keyfile.json")
    yield tmp_path
    database.clear_master_key()


class TestStartupMode:
    def test_no_keyfile_no_db_is_first_run(self, empty_dir):
        assert auth.determine_startup_mode() == auth.StartupMode.FIRST_RUN

    def test_keyfile_alone_is_unlock(self, empty_dir):
        crypto.save_keyfile(empty_dir / "keyfile.json", crypto.generate_salt())
        assert auth.determine_startup_mode() == auth.StartupMode.UNLOCK

    def test_keyfile_and_db_is_unlock(self, empty_dir):
        crypto.save_keyfile(empty_dir / "keyfile.json", crypto.generate_salt())
        (empty_dir / "cataloguer.db").write_bytes(b"\x00" * 100)
        assert auth.determine_startup_mode() == auth.StartupMode.UNLOCK


class TestFirstRunAndUnlock:
    def test_first_run_then_unlock_round_trip(self, empty_dir):
        passphrase = "this-is-a-real-test-passphrase"

        # First run creates keyfile and installs key.
        auth.first_run_setup(passphrase)
        database.init_db()
        assert (empty_dir / "keyfile.json").exists()
        case_id = database.create_case("Doe", "Courtroom 1", "FR-1", "2024-05-12")
        assert case_id is not None

        # Simulate quit: drop the key.
        database.clear_master_key()

        # Subsequent run via unlock should succeed.
        auth.unlock(passphrase)
        fetched = database.get_case_by_docket("FR-1")
        assert fetched is not None
        assert fetched["last_name"] == "Doe"

    def test_unlock_with_wrong_passphrase_raises(self, empty_dir):
        auth.first_run_setup("correct-horse-battery-staple")
        database.init_db()
        database.clear_master_key()

        with pytest.raises(database.WrongPassphraseError):
            auth.unlock("absolutely-not-the-passphrase")
        # And master key was cleared on failure.
        assert not database.has_master_key()
