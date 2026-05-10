import base64
import hashlib
import logging
import os
import re

from fastapi import Response

from config import Settings

REDACT_RE = re.compile(
    r"(?i)(token|secret|authorization|api[-_]?key|code_verifier|refresh)"
)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = REDACT_RE.sub("[REDACTED]", str(record.msg))
        return True


def generate_session_id() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")


def generate_code_verifier() -> str:
    return base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode("ascii")


def compute_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def set_session_cookie(response: Response, session_id: str, settings: Settings) -> None:
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=(settings.ENV == "production"),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        key="session_id",
        value="",
        max_age=0,
        httponly=True,
        secure=(settings.ENV == "production"),
        samesite="lax",
        path="/",
    )
