class OAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ProviderError(OAuthError):
    pass


class InternalServiceError(OAuthError):
    def __init__(self, status: int) -> None:
        super().__init__(f"internal_service_error:{status}", status_code=502)
        self.upstream_status = status


class TokenRefreshError(OAuthError):
    def __init__(self, reason: str = "refresh_failed") -> None:
        super().__init__(reason, status_code=401)
