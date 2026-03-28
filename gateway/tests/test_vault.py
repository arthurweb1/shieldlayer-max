# gateway/tests/test_vault.py
import pytest
from gateway.anonymizer.crypto import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    key = b"\x00" * 32
    plaintext = "PERSON_001=John Doe"
    ciphertext = encrypt(key, plaintext)
    assert ciphertext != plaintext.encode()
    assert decrypt(key, ciphertext) == plaintext


def test_different_ciphertexts_same_plaintext():
    key = b"\x01" * 32
    ct1 = encrypt(key, "hello")
    ct2 = encrypt(key, "hello")
    assert ct1 != ct2  # random nonce per call
