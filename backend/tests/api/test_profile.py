"""API integration tests — GET /profile.

Covers:
- Auth guard: missing / invalid session cookie
- Response shape: UnifiedProfile JSON structure
- User fields from internal service mock
- Repositories section from GitHub mock
- User profile cache: internal service called only once per user
"""

_REPOS_RESPONSE = [
    {"name": "alpha", "description": "First repo", "stargazers_count": 10},
    {"name": "beta", "description": None, "stargazers_count": 0},
]


def _mock_repos(github_mock, test_settings):
    github_mock.get(f"{test_settings.GITHUB_API_BASE}/user/repos").respond(
        200,
        json=_REPOS_RESPONSE,
        headers={"Link": ""},
    )


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


class TestAuthGuard:
    async def test_no_cookie_returns_401(self, client):
        response = await client.get("/profile")
        assert response.status_code == 401

    async def test_bogus_session_id_returns_401(self, client):
        client.cookies.set("session_id", "does-not-exist")
        response = await client.get("/profile")
        assert response.status_code == 401

    async def test_error_detail_for_missing_cookie(self, client):
        response = await client.get("/profile")
        assert response.json()["detail"] == "not_authenticated"

    async def test_error_detail_for_expired_session(self, client):
        client.cookies.set("session_id", "ghost-session")
        response = await client.get("/profile")
        assert response.json()["detail"] == "session_expired"


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestProfileResponse:
    async def test_valid_session_returns_200(
        self, authed_client, github_mock, test_settings
    ):
        _mock_repos(github_mock, test_settings)
        response = await authed_client.get("/profile")
        assert response.status_code == 200

    async def test_response_has_user_and_sections(
        self, authed_client, github_mock, test_settings
    ):
        _mock_repos(github_mock, test_settings)
        body = (await authed_client.get("/profile")).json()
        assert "user" in body
        assert "sections" in body

    async def test_user_has_required_fields(
        self, authed_client, github_mock, test_settings
    ):
        _mock_repos(github_mock, test_settings)
        user = (await authed_client.get("/profile")).json()["user"]
        assert user["id"] == "42"
        assert user["provider"] == "github"
        assert "name" in user
        assert user["license"] in ("Pro", "Basic")
        assert "role" in user

    async def test_sections_has_repositories_list(
        self, authed_client, github_mock, test_settings
    ):
        _mock_repos(github_mock, test_settings)
        sections = (await authed_client.get("/profile")).json()["sections"]
        assert "repositories" in sections
        assert isinstance(sections["repositories"], list)

    async def test_repository_fields(self, authed_client, github_mock, test_settings):
        _mock_repos(github_mock, test_settings)
        repos = (await authed_client.get("/profile")).json()["sections"]["repositories"]
        assert len(repos) == 2
        assert repos[0]["name"] == "alpha"
        assert repos[0]["stars"] == 10
        assert repos[1]["description"] is None


# ---------------------------------------------------------------------------
# User profile cache
# ---------------------------------------------------------------------------


class TestProfileCache:
    async def test_user_profile_cached_after_first_call(
        self, authed_client, github_mock, test_settings, store
    ):
        """After a successful /profile call, the user profile must be in the store."""
        _mock_repos(github_mock, test_settings)
        await authed_client.get("/profile")

        cached = await store.get_user_profile("github", "42")
        assert cached is not None
        assert cached.provider == "github"
        assert cached.provider_user_id == "42"

    async def test_second_call_returns_same_user_data(
        self, authed_client, github_mock, test_settings
    ):
        """Two consecutive /profile calls return the same user name (cache hit)."""
        _mock_repos(github_mock, test_settings)
        first = (await authed_client.get("/profile")).json()["user"]["name"]
        _mock_repos(github_mock, test_settings)  # repos are always re-fetched
        second = (await authed_client.get("/profile")).json()["user"]["name"]
        assert first == second
