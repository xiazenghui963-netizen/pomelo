from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.skill_configs import get_detail, list_skills

router = APIRouter(prefix="/skill", tags=["skill"])


@router.get("/list")
def skill_list(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    return list_skills()


@router.get("/{skill_id}")
def skill_detail(skill_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    return get_detail(skill_id)