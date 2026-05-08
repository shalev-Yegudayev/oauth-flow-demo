from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: SecretStr
    GITHUB_REDIRECT_URI: str
    GITHUB_AUTHORIZE_URL: str = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL: str = "https://github.com/login/oauth/access_token"
    GITHUB_API_BASE: str = "https://api.github.com"
    INTERNAL_SERVICE_URL: str
    INTERNAL_API_KEY: SecretStr
    INTERNAL_SERVICE_MOCK: bool = True
    REDIS_URL: str
    SESSION_SECRET: SecretStr
    FRONTEND_ORIGIN: str
    POST_LOGIN_REDIRECT: str
    ENV: Literal["dev", "prod"] = "dev"
    SESSION_TTL_SECONDS: int = 3600
    STATE_TTL_SECONDS: int = 300
    USER_PROFILE_TTL_SECONDS: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")


@lru_cache
def get_settings() -> Settings:
    return Settings()
