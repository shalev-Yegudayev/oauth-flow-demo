"""Tests for TokenCipher (app/core/crypto.py)."""

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import InvalidToken, TokenCipher


@pytest.fixture
def key_a() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def key_b() -> str:
    return Fernet.generate_key().decode()


class TestEncryptDecryptRoundTrip:
    def test_plaintext_survives_round_trip(self, key_a):
        cipher = TokenCipher([key_a])
        assert (
            cipher.decrypt(cipher.encrypt("gho_some_access_token"))
            == "gho_some_access_token"
        )

    def test_empty_string_round_trip(self, key_a):
        cipher = TokenCipher([key_a])
        assert cipher.decrypt(cipher.encrypt("")) == ""

    def test_unicode_payload_round_trip(self, key_a):
        cipher = TokenCipher([key_a])
        payload = "token-éàü-end"
        assert cipher.decrypt(cipher.encrypt(payload)) == payload

    def test_ciphertext_differs_from_plaintext(self, key_a):
        cipher = TokenCipher([key_a])
        plaintext = "gho_super_secret"
        assert cipher.encrypt(plaintext) != plaintext

    def test_two_encryptions_produce_different_ciphertext(self, key_a):
        # Fernet uses a random IV — same plaintext must produce distinct ciphertexts.
        cipher = TokenCipher([key_a])
        ct1 = cipher.encrypt("same-token")
        ct2 = cipher.encrypt("same-token")
        assert ct1 != ct2


class TestWrongKeyRaisesInvalidToken:
    def test_wrong_single_key_raises(self, key_a, key_b):
        encryptor = TokenCipher([key_a])
        decryptor = TokenCipher([key_b])
        ciphertext = encryptor.encrypt("secret")
        with pytest.raises(InvalidToken):
            decryptor.decrypt(ciphertext)

    def test_corrupted_ciphertext_raises(self, key_a):
        cipher = TokenCipher([key_a])
        ciphertext = cipher.encrypt("secret")
        corrupted = ciphertext[:-4] + "XXXX"
        with pytest.raises(InvalidToken):
            cipher.decrypt(corrupted)

    def test_random_bytes_raises(self, key_a):
        cipher = TokenCipher([key_a])
        with pytest.raises((InvalidToken, Exception)):
            cipher.decrypt("not-a-fernet-token-at-all")


class TestKeyRotation:
    def test_primary_key_decrypts_new_token(self, key_a, key_b):
        """After rotation the primary key encrypts; both keys should decrypt."""
        rotated = TokenCipher([key_a, key_b])
        ct = rotated.encrypt("new-token")
        assert rotated.decrypt(ct) == "new-token"

    def test_fallback_key_decrypts_old_token(self, key_a, key_b):
        """Token encrypted by the old key must still decrypt after rotation."""
        old_cipher = TokenCipher([key_b])
        old_ciphertext = old_cipher.encrypt("old-token")

        # key_a is now primary; key_b is retired fallback
        rotated = TokenCipher([key_a, key_b])
        assert rotated.decrypt(old_ciphertext) == "old-token"

    def test_primary_key_encrypts_after_rotation(self, key_a, key_b):
        """New tokens must be decryptable by primary key alone."""
        rotated = TokenCipher([key_a, key_b])
        ct = rotated.encrypt("fresh-token")
        primary_only = TokenCipher([key_a])
        assert primary_only.decrypt(ct) == "fresh-token"

    def test_retired_key_only_cannot_decrypt_new_token(self, key_a, key_b):
        """Old key alone must NOT decrypt tokens encrypted with the new primary."""
        rotated = TokenCipher([key_a, key_b])
        ct = rotated.encrypt("fresh-token")
        retired_only = TokenCipher([key_b])
        with pytest.raises(InvalidToken):
            retired_only.decrypt(ct)


class TestInitValidation:
    def test_empty_secrets_raises_value_error(self):
        with pytest.raises(ValueError, match="SESSION_SECRET required"):
            TokenCipher([])

    def test_single_valid_key_accepted(self, key_a):
        cipher = TokenCipher([key_a])
        assert cipher is not None

    def test_multiple_valid_keys_accepted(self, key_a, key_b):
        cipher = TokenCipher([key_a, key_b])
        assert cipher is not None
