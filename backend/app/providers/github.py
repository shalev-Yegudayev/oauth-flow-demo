import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from pydantic import BaseModel

from app.core.exceptions import ProviderError, TokenRefreshError
from app.providers.base import AccessToken, OAuthProvider

logger = logging.getLogger(__name__)

_MAX_REPO_PAGES = 5


class Repo(BaseModel):
    name: str
    description: str | None
    stars: int


class GithubProvider(OAuthProvider):
    name = "github"
    required_scopes = ["public_repo", "read:user"]

    def authorization_url(self, state: str, code_challenge: str) -> str:
        params = urlencode(
            {
                "client_id": self._settings.GITHUB_CLIENT_ID,
                "redirect_uri": self._settings.GITHUB_REDIRECT_URI,
                "scope": " ".join(self.required_scopes),
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._settings.GITHUB_AUTHORIZE_URL}?{params}"

    async def exchange_code(self, code: str, code_verifier: str) -> AccessToken:
        resp = await self._http.post(
            self._settings.GITHUB_TOKEN_URL,
            data={
                "client_id": self._settings.GITHUB_CLIENT_ID,
                "client_secret": self._settings.GITHUB_CLIENT_SECRET.get_secret_value(),
                "code": code,
                "redirect_uri": self._settings.GITHUB_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise ProviderError(f"token_exchange_failed:{resp.status_code}")

        payload = resp.json()
        if "error" in payload:
            raise ProviderError(payload.get("error_description", payload["error"]))

        return self._parse_token_response(payload)

    async def refresh_token(self, refresh_token: str) -> AccessToken:
        resp = await self._http.post(
            self._settings.GITHUB_TOKEN_URL,
            data={
                "client_id": self._settings.GITHUB_CLIENT_ID,
                "client_secret": self._settings.GITHUB_CLIENT_SECRET.get_secret_value(),
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
            timeout=8.0,
        )
        if resp.status_code != 200:
            raise TokenRefreshError("refresh_request_failed")

        payload = resp.json()
        if "error" in payload:
            raise TokenRefreshError(payload.get("error_description", payload["error"]))

        return self._parse_token_response(payload)

    async def fetch_user_id(self, token: str) -> str:
        resp = await self._http.get(
            f"{self._settings.GITHUB_API_BASE}/user",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise ProviderError(f"fetch_user_failed:{resp.status_code}")
        return str(resp.json()["id"])

    async def revoke_token(self, token: str) -> None:
        resp = await self._http.delete(
            f"{self._settings.GITHUB_API_BASE}/applications/{self._settings.GITHUB_CLIENT_ID}/token",
            auth=(
                self._settings.GITHUB_CLIENT_ID,
                self._settings.GITHUB_CLIENT_SECRET.get_secret_value(),
            ),
            json={"access_token": token},
            timeout=10.0,
        )
        if resp.status_code not in (204, 404):
            logger.warning(
                "token revocation returned unexpected status=%d", resp.status_code
            )

    async def fetch_profile_sections(self, token: str) -> dict:
        repos = await self._fetch_repositories(token)
        return {"repositories": [r.model_dump() for r in repos]}

    async def _fetch_repositories(self, token: str) -> list[Repo]:
        repos: list[Repo] = []
        url: str | None = (
            f"{self._settings.GITHUB_API_BASE}/user/repos?visibility=public&per_page=100&sort=updated"
        )
        pages = 0
        while url and pages < _MAX_REPO_PAGES:
            resp = await self._http.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise ProviderError(f"fetch_repos_failed:{resp.status_code}")
            repos.extend(
                Repo(
                    name=item["name"],
                    description=item.get("description"),
                    stars=item["stargazers_count"],
                )
                for item in resp.json()
            )
            pages += 1
            url = _next_link(resp.headers.get("Link", ""))
        return repos

    @staticmethod
    def _parse_token_response(payload: dict) -> AccessToken:
        expires_at: datetime | None = None
        if "expires_in" in payload:
            expires_at = datetime.now(UTC) + timedelta(
                seconds=int(payload["expires_in"])
            )
        raw_scope = payload.get("scope", "")
        # GitHub returns scopes comma-separated; normalize to space-separated.
        normalized_scope = raw_scope.replace(",", " ")
        return AccessToken(
            value=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scope=normalized_scope,
        )


def _next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        segments = [s.strip() for s in part.split(";")]
        if len(segments) == 2 and segments[1] == 'rel="next"':
            return segments[0].strip("<>")
    return None
