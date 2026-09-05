"""Encryption service for CTL metadata."""

from __future__ import annotations

import os
from pathlib import Path

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoError(Exception):
    """Raised on cryptographic failures."""


class CryptoService:
    """AES-256-GCM encryption with Argon2id key derivation."""

    def __init__(self, key_path: str | Path) -> None:
        self.key_path = Path(key_path).expanduser()
        self._aesgcm: AESGCM | None = None

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        return hash_secret_raw(
            password.encode("utf-8"),
            salt,
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            type=Type.ID,
        )

    def initialize(self, password: str) -> None:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        key = self._derive_key(password, salt)
        self.key_path.write_bytes(salt + key)
        os.chmod(self.key_path, 0o600)
        self._aesgcm = AESGCM(key)

    def load(self, password: str) -> None:
        if not self.key_path.exists():
            self.initialize(password)
            return
        data = self.key_path.read_bytes()
        salt, key = data[:16], data[16:]
        derived = self._derive_key(password, salt)
        if derived != key:
            raise CryptoError("Invalid password")
        self._aesgcm = AESGCM(derived)

    def encrypt(self, plaintext: bytes) -> bytes:
        if self._aesgcm is None:
            raise CryptoError("CryptoService not initialized")
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        if self._aesgcm is None:
            raise CryptoError("CryptoService not initialized")
        nonce, ciphertext = data[:12], data[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    @property
    def ready(self) -> bool:
        return self._aesgcm is not None
