"""Tests for crypto.py — KDF determinism, salt generation, keyfile I/O."""

import json

import pytest

from court_cataloguer import crypto


class TestKDF:
    def test_same_inputs_produce_same_key(self):
        salt = b"\x01" * crypto.SALT_BYTES
        a = crypto.derive_key("hunter2-but-long", salt)
        b = crypto.derive_key("hunter2-but-long", salt)
        assert a == b
        assert len(a) == crypto.KEY_BYTES

    def test_different_salt_yields_different_key(self):
        a = crypto.derive_key("same-passphrase", b"\x01" * crypto.SALT_BYTES)
        b = crypto.derive_key("same-passphrase", b"\x02" * crypto.SALT_BYTES)
        assert a != b

    def test_different_passphrase_yields_different_key(self):
        salt = b"\x05" * crypto.SALT_BYTES
        a = crypto.derive_key("alpha-bravo-charlie", salt)
        b = crypto.derive_key("alpha-bravo-delta", salt)
        assert a != b

    def test_empty_passphrase_rejected(self):
        with pytest.raises(ValueError):
            crypto.derive_key("", b"\x00" * crypto.SALT_BYTES)

    def test_wrong_salt_length_rejected(self):
        with pytest.raises(ValueError):
            crypto.derive_key("ok-passphrase", b"\x00" * 8)


class TestSalt:
    def test_generate_salt_correct_length(self):
        assert len(crypto.generate_salt()) == crypto.SALT_BYTES

    def test_salts_are_random(self):
        salts = {crypto.generate_salt() for _ in range(20)}
        assert len(salts) == 20


class TestPragmaHex:
    def test_round_trip(self):
        key = b"\x00\x11\x22\x33" * 8
        hex_str = crypto.key_to_pragma_hex(key)
        assert hex_str == "00112233" * 8
        assert bytes.fromhex(hex_str) == key

    def test_wrong_length_rejected(self):
        with pytest.raises(ValueError):
            crypto.key_to_pragma_hex(b"\x00" * 16)


class TestKeyfile:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "keyfile.json"
        salt = crypto.generate_salt()
        crypto.save_keyfile(path, salt)
        loaded = crypto.load_keyfile(path)
        assert loaded.version == crypto.KEYFILE_VERSION
        assert loaded.kdf == crypto.KDF_NAME
        assert loaded.iterations == crypto.PBKDF2_ITERS
        assert loaded.salt == salt

    def test_load_missing_raises_filenotfound(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            crypto.load_keyfile(tmp_path / "nope.json")

    def test_load_malformed_raises_keyfileerror(self, tmp_path):
        path = tmp_path / "keyfile.json"
        path.write_text("not json {{{")
        with pytest.raises(crypto.KeyfileError):
            crypto.load_keyfile(path)

    def test_load_unknown_version_raises(self, tmp_path):
        path = tmp_path / "keyfile.json"
        path.write_text(
            json.dumps(
                {
                    "version": 999,
                    "kdf": crypto.KDF_NAME,
                    "iterations": crypto.PBKDF2_ITERS,
                    "salt_b64": "AAAAAAAAAAAAAAAAAAAAAA==",
                }
            )
        )
        with pytest.raises(crypto.KeyfileError):
            crypto.load_keyfile(path)

    def test_load_unknown_kdf_raises(self, tmp_path):
        path = tmp_path / "keyfile.json"
        path.write_text(
            json.dumps(
                {
                    "version": crypto.KEYFILE_VERSION,
                    "kdf": "bcrypt-but-not-really",
                    "iterations": 1,
                    "salt_b64": "AAAAAAAAAAAAAAAAAAAAAA==",
                }
            )
        )
        with pytest.raises(crypto.KeyfileError):
            crypto.load_keyfile(path)

    def test_save_refuses_to_clobber_unknown_format(self, tmp_path):
        path = tmp_path / "keyfile.json"
        path.write_text(json.dumps({"version": 999}))
        with pytest.raises(crypto.KeyfileError):
            crypto.save_keyfile(path, crypto.generate_salt())

    def test_save_overwrites_known_format(self, tmp_path):
        path = tmp_path / "keyfile.json"
        salt1 = crypto.generate_salt()
        crypto.save_keyfile(path, salt1)
        salt2 = crypto.generate_salt()
        crypto.save_keyfile(path, salt2)
        assert crypto.load_keyfile(path).salt == salt2
