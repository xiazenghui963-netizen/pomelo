import threading
import time
from collections import defaultdict

from fastapi import Request

from .errors import BizError

_STORE: dict[str, list[float]] = defaultdict(list)
_LOCK = threading.Lock()


def _check(key: str, limit: int, window: int) -> bool:
    now = time.monotonic()
    with _LOCK:
        hits = [t for t in _STORE[key] if now - t < window]
        if len(hits) >= limit:
            _STORE[key] = hits
            return False
        hits.append(now)
        _STORE[key] = hits
        return True


def make_limiter(limit_key: str, limit: int, window: int):
    def dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        if not _check(f"{limit_key}:{client_ip}", limit, window):
            raise BizError("操作太频繁，请稍后再试", code=42900, status_code=429)

    return dependency