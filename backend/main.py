import logging
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.crypto import TokenCipher
from app.core.exceptions import OAuthError
from app.core.handlers import oauth_error_handler, unhandled_error_handler
from app.core.rate_limit import get_session_key
from app.core.security import RedactingFilter
from app.routes.auth import router as auth_router
from app.routes.profile import router as profile_router
from app.services.internal_service import (
    InternalServiceClient,
    mock_transport_handler,
)
from app.services.session_store import SessionStore
from config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    app.state.redis = aioredis.from_url(
        settings.REDIS_URL, decode_responses=False
    )
    app.state.provider_http = httpx.AsyncClient(timeout=10.0)

    if settings.INTERNAL_SERVICE_MOCK:
        app.state.internal_http = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_transport_handler)
        )
    else:
        app.state.internal_http = httpx.AsyncClient(timeout=10.0)

    secrets = [
        s.strip()
        for s in settings.SESSION_SECRET.get_secret_value().split(",")
    ]
    app.state.cipher = TokenCipher(secrets)

    app.state.store = SessionStore(
        app.state.redis,
        settings.SESSION_TTL_SECONDS,
        settings.STATE_TTL_SECONDS,
        settings.USER_PROFILE_TTL_SECONDS,
    )
    app.state.internal_client = InternalServiceClient(
        app.state.internal_http, settings
    )

    app.state.limiter = Limiter(
        key_func=get_session_key, storage_uri=settings.REDIS_URL
    )

    yield

    await app.state.redis.aclose()
    await app.state.provider_http.aclose()
    await app.state.internal_http.aclose()


def create_app() -> FastAPI:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[handler],
    )
    settings = get_settings()

    app = FastAPI(title="OAuth Microservice", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(OAuthError, oauth_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(auth_router)
    app.include_router(profile_router)

    return app


app = create_app()
