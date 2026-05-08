from typing import Any, Literal

from pydantic import BaseModel


class UserSummary(BaseModel):
    id: str
    name: str
    provider: str
    tier: Literal["Pro", "Basic"]
    role: str


class UnifiedProfile(BaseModel):
    user: UserSummary
    sections: dict[str, Any]
