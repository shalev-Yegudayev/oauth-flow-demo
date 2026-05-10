from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class StateRecord(BaseModel):
    provider: str
    code_verifier: str
    created_at: datetime


class SessionRecord(BaseModel):
    session_id: str
    provider: str
    provider_user_id: str
    encrypted_access_token: str
    encrypted_refresh_token: str | None
    token_expires_at: datetime | None
    scope: str
    created_at: datetime
    last_refreshed_at: datetime | None


class UserProfileRecord(BaseModel):
    provider: str
    provider_user_id: str
    user_name: str
    license: Literal["Pro", "Basic"]
    role: str
