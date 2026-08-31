import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.core.errors import BizError
from app.core.tasks import shutdown_workers, start_workers
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_skill_registry()
    start_workers()
    yield
    shutdown_workers()


def load_skill_registry():
    from app.services.skills import ensure_loaded
    ensure_loaded()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


def _ok_response(status_code: int, body: bytes) -> Response:
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        data = None
    return Response(
        content=json.dumps({"code": 0, "message": "ok", "data": data}, ensure_ascii=False),
        media_type="application/json",
        status_code=status_code,
    )


async def _read_body(response) -> bytes:
    if hasattr(response, "body") and response.body is not None:
        return response.body
    chunks = [c async for c in response.body_iterator]
    return b"".join(chunks)


@app.middleware("http")
async def response_envelope(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        return response
    if not (response.headers.get("content-type") or "").startswith("application/json"):
        return response
    if response.status_code >= 400:
        return response
    return _ok_response(response.status_code, await _read_body(response))


app.include_router(api_router, prefix="/api")

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")