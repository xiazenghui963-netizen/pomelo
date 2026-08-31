from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.database import get_db
from app.models import User
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