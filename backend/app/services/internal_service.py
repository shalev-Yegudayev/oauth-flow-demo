import random
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.core.exceptions import InternalServiceError
from app.models.session import UserProfileRecord
from config import Settings

_FIRST_NAMES = ["Alex", "Jordan", "Riley", "Sam", "Taylor", "Morgan", "Casey", "Jamie"]
_LAST_NAMES = ["Chen", "Patel", "Garcia", "Smith", "Cohen", "Nguyen", "Khan", "Silva"]
_ROLES = ["developer", "admin", "analyst", "viewer"]


class _InternalUser(BaseModel):
    user_id: str
    name: str
    license: Literal["Pro", "Basic"]
    role: str


def mock_transport_handler(request: httpx.Request) -> httpx.Response:
    from config import get_settings

    settings = get_settings()
    if (
        request.headers.get("X-Internal-API-Key")
        != settings.INTERNAL_API_KEY.get_secret_value()
    ):
        return httpx.Response(401, json={"error": "missing_or_invalid_api_key"})
    user_id = request.url.path.rsplit("/", 1)[-1]
    rng = random.Random(user_id)
    return httpx.Response(
        200,
        json={
            "user_id": user_id,
            "name": f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
            "license": rng.choice(["Pro", "Basic"]),
            "role": rng.choice(_ROLES),
        },
    )


class InternalServiceClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    async def get_user(self, provider: str, provider_user_id: str) -> UserProfileRecord:
        safe_id = quote(provider_user_id, safe="")
        url = f"{self._settings.INTERNAL_SERVICE_URL}/api/users/{safe_id}"
        api_key = self._settings.INTERNAL_API_KEY.get_secret_value()
        headers = {"X-Internal-API-Key": api_key}
        try:
            resp = await self._http.get(url, headers=headers, timeout=5.0)
        except httpx.RequestError as exc:
            raise InternalServiceError(503) from exc

        if resp.status_code != 200:
            raise InternalServiceError(resp.status_code)

        try:
            internal = _InternalUser.model_validate(resp.json())
        except Exception as exc:
            raise InternalServiceError(502) from exc

        return UserProfileRecord(
            provider=provider,
            provider_user_id=provider_user_id,
            user_name=internal.name,
            license=internal.license,
            role=internal.role,
        )
