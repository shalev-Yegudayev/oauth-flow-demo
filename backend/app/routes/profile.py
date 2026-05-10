import httpx
from fastapi import APIRouter, Depends, Request

from app.core.crypto import TokenCipher
from app.core.rate_limit import get_session_key, limiter
from app.models.profile import UnifiedProfile, UserSummary
from app.models.session import SessionRecord, UserProfileRecord
from app.providers import get_provider
from app.services.internal_service import InternalServiceClient
from app.services.session_store import SessionStore
from config import Settings
from deps import (
    get_authenticated_session,
    get_cipher,
    get_internal_client,
    get_provider_http,
    get_session_store,
    get_settings_dep,
)

router = APIRouter(tags=["profile"])


async def get_or_fetch_user_profile(
    store: SessionStore,
    internal: InternalServiceClient,
    provider_user_id: str,
) -> UserProfileRecord:
    profile_record = await store.get_user_profile(provider_user_id)
    if profile_record is None:
        profile_record = await internal.get_user(provider_user_id)
        await store.set_user_profile(profile_record)
    return profile_record


@router.get("/profile", response_model=UnifiedProfile)
@limiter.limit("60/minute", key_func=get_session_key)
async def get_profile(
    request: Request,
    session: SessionRecord = Depends(get_authenticated_session),
    store: SessionStore = Depends(get_session_store),
    internal: InternalServiceClient = Depends(get_internal_client),
    cipher: TokenCipher = Depends(get_cipher),
    provider_http: httpx.AsyncClient = Depends(get_provider_http),
    settings: Settings = Depends(get_settings_dep),
) -> UnifiedProfile:
    profile_record = await get_or_fetch_user_profile(
        store=store,
        internal=internal,
        provider_user_id=session.provider_user_id,
    )

    provider = get_provider(session.provider, provider_http, settings)

    plaintext_token = cipher.decrypt(session.encrypted_access_token)
    sections = await provider.fetch_profile_sections(plaintext_token)

    return UnifiedProfile(
        user=UserSummary(
            id=session.provider_user_id,
            name=profile_record.user_name,
            provider=session.provider,
            tier=profile_record.tier,
            role=profile_record.role,
        ),
        sections=sections,
    )
