import logging
import re

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Matches parameter/header names that carry credentials so their values are never logged.
_REDACT_RE = re.compile(r"(?i)(token|secret|authorization|api[-_]?key|code_verifier|refresh)")


def _redact(value: str) -> str:
    return "[REDACTED]" if _REDACT_RE.search(value) else value


class OAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ProviderError(OAuthError):
    pass


class InternalServiceError(OAuthError):
    def __init__(self, status: int) -> None:
        super().__init__(f"internal_service_error:{status}", status_code=502)
        self.upstream_status = status


class TokenRefreshError(OAuthError):
    def __init__(self, reason: str = "refresh_failed") -> None:
        super().__init__(reason, status_code=401)


async def oauth_error_handler(request: Request, exc: OAuthError) -> JSONResponse:
    logger.warning("OAuthError: %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "internal_error"})
