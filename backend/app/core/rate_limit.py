from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_session_key(request) -> str:
    session_id = request.cookies.get("session_id")
    return session_id if session_id else get_remote_address(request)


# storage_uri is set by main.py lifespan before any request is handled.
# No storage_uri defaults to in-memory (fine for tests/cold-start).
limiter = Limiter(key_func=get_remote_address)
