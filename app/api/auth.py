from app.core.errors import BizError
from app.core.security import create_token, hash_password, verify_password
from app.database import get_db
from app.core.limiter import make_limiter
from app.models import User
from app.schemas import ChangePasswordIn, LoginIn, RegisterIn
from app.services.points import apply_daily_grant, get_or_create_points

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_public(user: User, points_row) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "role": user.role,
        "points": points_row.points_balance,
        "is_member": points_row.is_member,
    }


@router.post("/register", dependencies=[Depends(make_limiter("register", 5, 60))])
def register(body: RegisterIn, db=Depends(get_db)):
    exists = db.query(User).filter(User.username == body.username).first()
    if exists:
        raise BizError("用户名已存在", code=40001, status_code=409)
    from app.core.security import hash_password

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname or body.username,
    )
    db.add(user)
    db.flush()
    points = get_or_create_points(db, user.id)
    db.commit()
    token = create_token(user.id)
    return {"token": token, "user": _user_public(user, points)}


@router.post("/login", dependencies=[Depends(make_limiter("login", 5, 60))])
def login(body: LoginIn, db=Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise BizError("用户名或密码错误", code=40002, status_code=401)
    points = get_or_create_points(db, user.id)
    apply_daily_grant(db, user.id)
    db.commit()
    token = create_token(user.id)
    return {"token": token, "user": _user_public(user, points)}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, current_user=Depends(get_current_user), db=Depends(get_db)):
    """仅当前登录用户修改自己的密码：校验旧密码、新密码不能与旧密码相同、confirm 一致，更新 bcrypt 哈希。"""
    if body.confirm_password != body.new_password:
        raise BizError("两次输入的新密码不一致", code=40006, status_code=400)
    if not verify_password(body.old_password, current_user.password_hash):
        raise BizError("旧密码错误", code=40007, status_code=400)
    if verify_password(body.new_password, current_user.password_hash):
        raise BizError("新密码不能与旧密码相同", code=40008, status_code=400)
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True, "message": "密码修改成功，请重新登录"}


@router.get("/me")
def me(current_user=Depends(get_current_user), db=Depends(get_db)):
    points = get_or_create_points(db, current_user.id)
    granted = apply_daily_grant(db, current_user.id)
    db.commit()
    return {**_user_public(current_user, points), "daily_grant": granted}