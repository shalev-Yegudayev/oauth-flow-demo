from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: SecretStr
    GITHUB_REDIRECT_URI: str
    GITHUB_AUTHORIZE_URL: str = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL: str = "https://github.com/login/oauth/access_token"
    GITHUB_API_BASE: str = "https://api.github.com"
    GITHUB_REPOS_PER_PAGE: int = 100
    INTERNAL_SERVICE_URL: str
    INTERNAL_API_KEY: SecretStr
    INTERNAL_SERVICE_MOCK: bool = True
    REDIS_URL: str
    SESSION_SECRET: SecretStr
    FRONTEND_ORIGIN: str
    POST_LOGIN_REDIRECT: str
    ENV: Literal["dev", "production"] = "dev"
    SESSION_TTL_SECONDS: int = 3600
    STATE_TTL_SECONDS: int = 300
    USER_PROFILE_TTL_SECONDS: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    @model_validator(mode="after")
    def _validate_post_login_redirect(self) -> "Settings":
        # Pin POST_LOGIN_REDIRECT to the configured frontend origin so a
        # misconfigured env var cannot turn the OAuth callback into an open
        # redirect. The path can vary; the origin must match exactly.
        origin = self.FRONTEND_ORIGIN.rstrip("/")
        if not (
            self.POST_LOGIN_REDIRECT == origin
            or self.POST_LOGIN_REDIRECT.startswith(origin + "/")
        ):
            raise ValueError(
                "POST_LOGIN_REDIRECT must be on the FRONTEND_ORIGIN "
                f"({origin}); got {self.POST_LOGIN_REDIRECT}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
