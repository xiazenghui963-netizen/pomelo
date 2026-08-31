from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import MemberActivateIn
from app.services.points import get_or_create_points

router = APIRouter(tags=["admin"])


@router.post("/admin/member")
def set_member(body: MemberActivateIn, admin: User = Depends(require_admin), db=Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None:
        from app.core.errors import BizError
        raise BizError("用户不存在", code=40400, status_code=404)
    points = get_or_create_points(db, user.id)
    points.is_member = body.is_member
    db.commit()
    return {"ok": True, "username": user.username, "is_member": body.is_member}