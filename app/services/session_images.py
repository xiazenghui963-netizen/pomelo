import threading
import time
import uuid

from app.config import settings


class SessionImageStore:
    """上传截图的内存暂存区：只在进程内存中保存，供 OCR/VLM 识别，不写磁盘、不传云存储。

    识别完成后调用 discard 立即丢弃；另有 TTL 兜底清理，防止长期占用内存。
    """

    def __init__(self, ttl: int):
        self._ttl = ttl
        self._records: dict[str, dict] = {}
        self._lock = threading.Lock()

    def put(self, user_id: int, data: bytes, content_type: str, filename: str) -> str:
        token = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._gc(now)
            self._records[token] = {
                "user_id": user_id,
                "data": data,
                "content_type": content_type,
                "filename": filename,
                "created_at": now,
            }
        return token

    def get(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._lock:
            rec = self._records.get(token)
            if rec is None:
                return None
            if time.time() - rec["created_at"] > self._ttl:
                self._records.pop(token, None)
                return None
            return rec

    def discard(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._records.pop(token, None)

    def _gc(self, now: float) -> None:
        expired = [k for k, v in self._records.items() if now - v["created_at"] > self._ttl]
        for k in expired:
            self._records.pop(k, None)


session_images = SessionImageStore(settings.session_image_ttl)