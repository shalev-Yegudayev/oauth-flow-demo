from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class TokenCipher:
    def __init__(self, secrets: list[str]) -> None:
        if not secrets:
            raise ValueError("SESSION_SECRET required")

        self._cipher = MultiFernet([Fernet(k.encode()) for k in secrets])

    def encrypt(self, plaintext: str) -> str:
        return self._cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self._cipher.decrypt(ciphertext.encode("ascii")).decode("utf-8")


__all__ = ["TokenCipher", "InvalidToken"]
