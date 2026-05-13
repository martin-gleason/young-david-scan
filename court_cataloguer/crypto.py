"""Passphrase → key derivation, salt management, keyfile persistence.

All functions here are pure (no I/O except `load_keyfile` / `save_keyfile`)
so they're cheap to test deterministically.

THE DERIVED KEY MUST NOT BE LOGGED, PRINTED, OR `repr`'d. Treat the
`bytes` return value of `derive_key` like a password. Same for the
passphrase argument — callers should not retain it after derivation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

PBKDF2_ITERS = 600_000
SALT_BYTES = 16
KEY_BYTES = 32
KEYFILE_VERSION = 1
KDF_NAME = "pbkdf2-hmac-sha256"


class KeyfileError(ValueError):
    """Raised when the keyfile is missing, malformed, or uses an unknown KDF."""


@dataclass(frozen=True)
class KeyfileV1:
    version: int
    kdf: str
    iterations: int
    salt: bytes


def generate_salt() -> bytes:
    """Cryptographically random salt for a new keyfile."""
    return os.urandom(SALT_BYTES)


def derive_key(passphrase: str, salt: bytes, iterations: int = PBKDF2_ITERS) -> bytes:
    """PBKDF2-HMAC-SHA256 over the passphrase. Returns 32 raw bytes."""
    if not passphrase:
        raise ValueError("passphrase must be non-empty")
    if len(salt) != SALT_BYTES:
        raise ValueError(f"salt must be {SALT_BYTES} bytes, got {len(salt)}")
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, iterations, dklen=KEY_BYTES
    )


def key_to_pragma_hex(key: bytes) -> str:
    """Lowercase hex string for `PRAGMA key = "x'<hex>'"`."""
    if len(key) != KEY_BYTES:
        raise ValueError(f"key must be {KEY_BYTES} bytes, got {len(key)}")
    return key.hex()


def load_keyfile(path: Path) -> KeyfileV1:
    """Read the keyfile at `path`. Raises KeyfileError on malformed input.

    The keyfile holds only NON-SECRET parameters — salt, KDF name, iteration
    count, format version. Knowing all of these tells an attacker nothing
    without the passphrase.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KeyfileError(f"keyfile is not valid JSON: {path}") from exc

    try:
        version = int(raw["version"])
        kdf = str(raw["kdf"])
        iterations = int(raw["iterations"])
        salt_b64 = str(raw["salt_b64"])
    except (KeyError, TypeError, ValueError) as exc:
        raise KeyfileError(f"keyfile is missing required fields: {path}") from exc

    if version != KEYFILE_VERSION:
        raise KeyfileError(
            f"keyfile version {version} is not supported by this app "
            f"(expected {KEYFILE_VERSION}); refusing to overwrite"
        )
    if kdf != KDF_NAME:
        raise KeyfileError(f"keyfile uses unknown KDF {kdf!r}; expected {KDF_NAME!r}")

    try:
        salt = base64.b64decode(salt_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise KeyfileError("keyfile salt is not valid base64") from exc

    if len(salt) != SALT_BYTES:
        raise KeyfileError(f"keyfile salt length is {len(salt)}, expected {SALT_BYTES}")

    return KeyfileV1(version=version, kdf=kdf, iterations=iterations, salt=salt)


def save_keyfile(path: Path, salt: bytes, iterations: int = PBKDF2_ITERS) -> None:
    """Write a fresh keyfile. Refuses to clobber a keyfile with an unknown version."""
    if len(salt) != SALT_BYTES:
        raise ValueError(f"salt must be {SALT_BYTES} bytes, got {len(salt)}")

    if path.exists():
        # If the existing file is a known format we'll overwrite it (e.g.
        # rekey path); if it's something we don't recognise, bail out
        # rather than destroy future-Claude's data.
        try:
            load_keyfile(path)
        except KeyfileError as exc:
            raise KeyfileError(
                f"refusing to overwrite an unknown keyfile at {path}: {exc}"
            ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": KEYFILE_VERSION,
        "kdf": KDF_NAME,
        "iterations": iterations,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
