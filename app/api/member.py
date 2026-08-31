from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.points import get_or_create_points

router = APIRouter(tags=["member"])


@router.post("/member/activate")
def activate_member(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    points = get_or_create_points(db, current_user.id)
    points.is_member = True
    db.commit()
    return {"ok": True, "is_member": True, "message": "会员已开通（模拟支付，未接入真实支付）"}