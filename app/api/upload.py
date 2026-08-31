from fastapi import APIRouter, Depends, File, UploadFile

from app.core.errors import BizError
from app.core.limiter import make_limiter
from app.deps import get_current_user
from app.models import User
from app.services.session_images import session_images

router = APIRouter(prefix="/upload", tags=["upload"])

_ALLOWED = ("image/jpeg", "image/png", "image/webp", "image/gif")


@router.post("", dependencies=[Depends(make_limiter("upload", 10, 60))])
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in _ALLOWED:
        raise BizError("仅支持 JPG/PNG/WEBP/GIF 图片", code=40010, status_code=400)

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise BizError("图片不能超过 20MB", code=40011, status_code=400)
    if not data:
        raise BizError("图片内容为空", code=40012, status_code=400)

    token = session_images.put(current_user.id, data, file.content_type, file.filename or "")
    return {
        "session_image": token,
        "size": len(data),
        "content_type": file.content_type,
        "hint": "图片仅保存在当前进程内存中，将在本次识别完成后丢弃，不落盘、不存云存储",
    }