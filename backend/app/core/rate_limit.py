from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_session_key(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    return session_id if session_id else get_remote_address(request)


limiter = Limiter(key_func=get_session_key)
