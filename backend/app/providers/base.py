from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class AccessToken(BaseModel):

    value: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str


class OAuthProvider(ABC, Generic[T]):
    """Strategy interface for OAuth providers.

    To add a provider: subclass this, set ``name`` and ``required_scopes``,
    implement every abstract method, then register the class in the provider
    registry. Route handlers and session logic require no changes.
    """

    name: ClassVar[str]
    """Lowercase URL-safe slug matching the ``:provider`` route parameter."""

    required_scopes: ClassVar[list[str]]
    """Minimum scopes to request — list only what the implementation strictly needs."""

    @abstractmethod
    def authorization_url(self, state: str, code_challenge: str) -> str:
        """Return the provider's authorization URL (no I/O — must be synchronous).

        Include ``state`` verbatim for CSRF validation and ``code_challenge``
        with ``code_challenge_method=S256`` for PKCE. The ``redirect_uri``
        must exactly match what is registered in the provider's developer console.
        """
        ...

    @abstractmethod
    async def exchange_code(self, code: str, code_verifier: str) -> AccessToken:
        """Exchange a single-use authorization code for tokens.

        Pass ``code_verifier`` so the provider can validate the PKCE pair.
        Set ``expires_at`` to an absolute UTC datetime from ``expires_in``,
        or ``None`` if the provider does not expire tokens.
        """
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> AccessToken:
        """Return a fresh AccessToken using a refresh token.

        Raise ``NotImplementedError`` if the provider does not support refresh
        (the session layer will prompt re-authentication). If the provider
        rotates the refresh token, return the new one in the result.
        """
        ...

    @abstractmethod
    async def fetch_user_id(self, token: str) -> str:
        """Return the provider's stable, unique user identifier as a string.

        This value is used as the session key and the internal-service user ID.
        It must be stable across re-logins and must never be sent to the browser.
        """
        ...

    @abstractmethod
    async def revoke_token(self, token: str) -> None:
        """Revoke the access token at the provider on logout.

        If the provider has no revocation endpoint, log a warning and return
        normally — never raise, because the session must be cleared regardless.
        Treat 400/404 responses as success (token already invalid).
        """
        ...

    @abstractmethod
    async def fetch_profile_sections(self, token: str) -> T:
        """Return provider-specific profile data merged into GET /profile.

        ``T`` is bound by the concrete subclass (e.g. ``GithubProvider[GithubSections]``).
        The returned value must be JSON-serializable and include all keys the
        /profile aggregation layer expects for this provider.
        """
        ...
