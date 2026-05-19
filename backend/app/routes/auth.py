import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response

from app.core.crypto import TokenCipher
from app.core.exceptions import OAuthError
from app.core.rate_limit import limiter
from app.core.security import (
    clear_session_cookie,
    compute_code_challenge,
    generate_code_verifier,
    generate_session_id,
    generate_state,
    set_session_cookie,
)
from app.models.session import SessionRecord, StateRecord
from app.providers import get_provider
from app.providers.base import OAuthProvider
from app.services.session_store import SessionStore
from config import Settings
from deps import (
    get_cipher,
    get_oauth_provider,
    get_provider_http,
    get_session_store,
    get_settings_dep,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_redirect(origin: str, error: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{origin}/login?{urlencode({'error': error})}",
        status_code=302,
    )


@router.get("/{provider}")
@limiter.limit("10/minute")
async def start_oauth(
    request: Request,
    provider: str,
    store: SessionStore = Depends(get_session_store),
    oauth_provider: OAuthProvider = Depends(get_oauth_provider),
    settings: Settings = Depends(get_settings_dep),
) -> RedirectResponse:
    state = generate_state()
    verifier = generate_code_verifier()
    challenge = compute_code_challenge(verifier)

    try:
        await store.put_state(
            state,
            StateRecord(
                provider=provider,
                code_verifier=verifier,
                created_at=datetime.now(UTC),
            ),
        )
    except Exception as exc:  # Added after subbmission
        logger.exception(
            "failed to store OAuth state provider=%s reason=%s", provider, exc
        )
        return _login_redirect(settings.FRONTEND_ORIGIN, "session_error")

    return RedirectResponse(
        url=oauth_provider.authorization_url(state, challenge),
        status_code=307,
    )


@router.get("/{provider}/callback")
@limiter.limit("20/minute")
async def oauth_callback(
    request: Request,
    provider: str,
    store: SessionStore = Depends(get_session_store),
    oauth_provider: OAuthProvider = Depends(get_oauth_provider),
    cipher: TokenCipher = Depends(get_cipher),
    settings: Settings = Depends(get_settings_dep),
    code: str = Query(default=None),
    state: str = Query(default=None),
    error: str = Query(default=None),
) -> RedirectResponse:
    if error:
        return _login_redirect(settings.FRONTEND_ORIGIN, error)
    if not code or not state:
        return _login_redirect(settings.FRONTEND_ORIGIN, "missing_code_or_state")

    state_record = await store.pop_state(state)
    if state_record is None:
        return _login_redirect(settings.FRONTEND_ORIGIN, "invalid_or_expired_state")
    if state_record.provider != provider:
        return _login_redirect(settings.FRONTEND_ORIGIN, "provider_mismatch")

    try:
        token = await oauth_provider.exchange_code(code, state_record.code_verifier)
    except (OAuthError, httpx.HTTPError) as exc:  # Added after subbmission
        logger.warning("token exchange failed provider=%s reason=%s", provider, exc)
        return _login_redirect(settings.FRONTEND_ORIGIN, "token_exchange_failed")

    granted = set(token.scope.split())
    if not set(oauth_provider.required_scopes).issubset(granted):
        return _login_redirect(settings.FRONTEND_ORIGIN, "insufficient_scope")

    try:
        user_id = await oauth_provider.fetch_user_id(token.value)
    except (OAuthError, httpx.HTTPError) as exc:  # Added after subbmission
        logger.warning("fetch_user_id failed provider=%s reason=%s", provider, exc)
        return _login_redirect(settings.FRONTEND_ORIGIN, "provider_unreachable")

    session_id = generate_session_id()
    session = SessionRecord(
        session_id=session_id,
        provider=provider,
        provider_user_id=user_id,
        encrypted_access_token=cipher.encrypt(token.value),
        encrypted_refresh_token=(
            cipher.encrypt(token.refresh_token) if token.refresh_token else None
        ),
        token_expires_at=token.expires_at,
        scope=token.scope,
        created_at=datetime.now(UTC),
        last_refreshed_at=None,
    )
    try:
        await store.create_session(session)
    except Exception as exc:
        logger.exception("session creation failed provider=%s reason=%s", provider, exc)
        return _login_redirect(settings.FRONTEND_ORIGIN, "session_error")

    response = RedirectResponse(url=settings.POST_LOGIN_REDIRECT, status_code=307)
    set_session_cookie(response, session_id, settings)
    return response


async def _terminate_session(
    session_id: str, store: SessionStore, settings: Settings
) -> Response:
    await store.delete_session(session_id)
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response


@router.post("/logout", status_code=204)
@limiter.limit("30/minute")
async def logout(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    session_id = request.cookies.get("session_id")
    if not session_id:
        return Response(status_code=204)
    return await _terminate_session(session_id, store, settings)


@router.delete("/account", status_code=204)
@limiter.limit("10/minute")
async def delete_account(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    cipher: TokenCipher = Depends(get_cipher),
    provider_http: httpx.AsyncClient = Depends(get_provider_http),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    session_id = request.cookies.get("session_id")
    if not session_id:
        return Response(status_code=204)

    session = await store.get_session(session_id)
    if session:
        try:
            plaintext = cipher.decrypt(session.encrypted_access_token)
            provider = get_provider(session.provider, provider_http, settings)
            await provider.revoke_token(plaintext)
        except (httpx.HTTPError, OAuthError) as exc:
            logger.warning(
                "token revocation failed session_id=%s reason=%s",
                session_id,
                exc,
            )
    return await _terminate_session(session_id, store, settings)
