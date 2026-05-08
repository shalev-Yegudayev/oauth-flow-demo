import httpx
from fastapi import Depends, HTTPException, Request

from app.core.crypto import TokenCipher
from app.models.session import SessionRecord
from app.providers import get_provider
from app.providers.base import OAuthProvider
from app.services.internal_service import InternalServiceClient
from app.services.session_store import SessionStore
from app.services.token_refresher import TokenRefresher
from config import Settings, get_settings


def get_settings_dep() -> Settings:
    return get_settings()


def get_cipher(request: Request) -> TokenCipher:
    return request.app.state.cipher


async def get_session_store(request: Request) -> SessionStore:
    return request.app.state.store


def get_provider_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.provider_http


def get_oauth_provider(
    provider: str,
    http: httpx.AsyncClient = Depends(get_provider_http),
    settings: Settings = Depends(get_settings_dep),
) -> OAuthProvider:
    return get_provider(provider, http, settings)


def get_internal_client(request: Request) -> InternalServiceClient:
    return request.app.state.internal_client


async def get_authenticated_session(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    cipher: TokenCipher = Depends(get_cipher),
    http: httpx.AsyncClient = Depends(get_provider_http),
    settings: Settings = Depends(get_settings_dep),
) -> SessionRecord:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="not_authenticated")

    record = await store.get_session(session_id)
    if record is None:
        raise HTTPException(status_code=401, detail="session_expired")

    provider = get_provider(record.provider, http, settings)
    refresher = TokenRefresher(request.app.state.redis, store, cipher, provider)
    return await refresher.ensure_fresh(record)
