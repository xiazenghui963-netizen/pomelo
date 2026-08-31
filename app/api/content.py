from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.skills import skill_names

router = APIRouter(tags=["content"])


@router.get("/skills")
def list_skills(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    from app.services.skills import get_meta

    data = []
    for name in skill_names():
        meta = get_meta(name)
        data.append({
            "name": name,
            "description": meta.get("description"),
            "access_level": meta.get("access_level"),
            "member_only": bool(meta.get("access_level") == 1),
            "cost_point": meta.get("cost_point"),
            "parameters": meta.get("parameters"),
        })
    return sorted(data, key=lambda x: x["name"])