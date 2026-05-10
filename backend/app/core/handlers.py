import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import OAuthError

logger = logging.getLogger(__name__)


async def oauth_error_handler(request: Request, exc: OAuthError) -> JSONResponse:
    logger.warning("OAuthError: %s", exc.message)
    return JSONResponse(
        status_code=exc.status_code, content={"error": exc.message}
    )


async def unhandled_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "internal_error"})
