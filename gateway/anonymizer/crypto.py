# gateway/anonymizer/crypto.py
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(key: bytes, plaintext: str) -> bytes:
    """AES-256-GCM encrypt. Returns nonce (12 B) + ciphertext + tag."""
    assert len(key) == 32, f"Key must be 32 bytes, got {len(key)}"
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt(key: bytes, data: bytes) -> str:
    """AES-256-GCM decrypt. Expects nonce (12 B) prepended to ciphertext+tag."""
    assert len(key) == 32, f"Key must be 32 bytes, got {len(key)}"
    nonce, ct = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
