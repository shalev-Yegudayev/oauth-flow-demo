import httpx

from app.core.exceptions import OAuthError
from app.providers.base import OAuthProvider
from app.providers.github import GithubProvider
from config import Settings

# Registry maps provider slug → class.
_REGISTRY: dict[str, type] = {
    GithubProvider.name: GithubProvider,
}


def get_provider(
    name: str, http: httpx.AsyncClient, settings: Settings
) -> OAuthProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise OAuthError(f"unknown_provider:{name}", status_code=404)
    return cls(http, settings)
