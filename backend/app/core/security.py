import base64
import hashlib
import os
import re

from fastapi import Response

from config import Settings

_REDACT_RE = re.compile(
    r"(?i)(token|secret|authorization|api[-_]?key|code_verifier|refresh)"
)


def _redact(value: str) -> str:
    return "[REDACTED]" if _REDACT_RE.search(value) else value


def generate_state() -> str:
    return (
        base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
    )


def generate_code_verifier() -> str:
    return (
        base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode("ascii")
    )


def compute_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return (
        base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    )


def set_session_cookie(
    response: Response, session_id: str, settings: Settings
) -> None:
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
