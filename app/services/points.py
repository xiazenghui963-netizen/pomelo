from datetime import date, datetime, timezone

from app.config import settings
from app.core.errors import BizError
from app.models import UserPoints


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_or_create_points(db, user_id: int) -> UserPoints:
    row = db.query(UserPoints).filter(UserPoints.user_id == user_id).first()
    if row is None:
        row = UserPoints(user_id=user_id, points_balance=settings.initial_points)
        db.add(row)
        db.flush()
    return row


def balance(db, user_id: int) -> int:
    row = get_or_create_points(db, user_id)
    return row.points_balance


def apply_daily_grant(db, user_id: int) -> int:
    row = get_or_create_points(db, user_id)
    today = date.today()
    if row.last_daily_grant != today:
        amount = settings.member_daily_points if row.is_member else settings.free_daily_points
        row.points_balance += amount
        row.last_daily_grant = today
        db.flush()
        return amount
    return 0


def deduct(db, user_id: int, amount: int) -> None:
    if amount <= 0:
        return
    row = get_or_create_points(db, user_id)
    row.points_balance -= amount
    if row.points_balance < 0:
        row.points_balance += amount
        raise BizError("点数不足，请稍后再试或开通会员", code=40003, status_code=400)
    db.flush()


def refund(db, user_id: int, amount: int) -> None:
    if amount <= 0:
        return
    row = get_or_create_points(db, user_id)
    row.points_balance += amount
    db.flush()


def calc_pipeline_cost(task_type: str, has_image: bool, draw_image: bool) -> int:
    from app.services.skills import pipeline_cost

    return pipeline_cost(task_type, has_image, draw_image)


def validate_member_access(task_type: str, has_image: bool, draw_image: bool, is_member: bool) -> None:
    from app.services.skills import member_access_required

    locked = member_access_required(task_type, has_image, draw_image)
    if locked and not is_member:
        raise BizError("该功能为会员专属，请先开通会员", code=40301, status_code=403)


