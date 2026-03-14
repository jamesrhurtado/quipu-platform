"""Fernet encryption helpers for storing sensitive credentials."""

from cryptography.fernet import Fernet

from config import settings


def _get_fernet() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError("ENCRYPTION_KEY not configured — cannot encrypt/decrypt credentials")
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet key (for initial setup)."""
    return Fernet.generate_key().decode()
