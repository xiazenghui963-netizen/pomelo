from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .core.errors import BizError
from .core.security import decode_token
from .database import get_db
from .models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db=Depends(get_db),
) -> User:
    if credentials is None:
        raise BizError("未登录", code=40100, status_code=401)
    user_id = decode_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise BizError("用户不存在", code=40100, status_code=401)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise BizError("无权限", code=40300, status_code=403)
    return user