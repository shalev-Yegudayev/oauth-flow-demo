from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class UserSummary(BaseModel):
    id: str
    name: str
    provider: str
    license: Literal["Pro", "Basic"]
    role: str


class UnifiedProfile(BaseModel, Generic[T]):
    user: UserSummary
    sections: dict[str, T]
