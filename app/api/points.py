from fastapi import APIRouter, Depends

from app.deps import get_current_user, require_admin
from app.database import get_db
from app.models import User
from app.schemas import GrantPointsIn
from app.services.points import apply_daily_grant, get_or_create_points

router = APIRouter(prefix="/points", tags=["points"])


@router.get("")
def get_points(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = get_or_create_points(db, current_user.id)
    granted = apply_daily_grant(db, current_user.id)
    db.commit()
    return {
        "points": row.points_balance,
        "is_member": row.is_member,
        "daily_grant_today": granted,
    }


@router.post("/grant")
def grant_points(body: GrantPointsIn, admin: User = Depends(require_admin), db=Depends(get_db)):
    """管理员手动增加点数（累加 balance，仅限管理员后台调试使用）。"""
    row = get_or_create_points(db, admin.id)
    row.points_balance += body.amount
    db.commit()
    return {
        "ok": True,
        "granted": body.amount,
        "points": row.points_balance,
        "message": f"已增加 {body.amount} 点",
    }