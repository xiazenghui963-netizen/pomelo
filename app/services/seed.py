from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import User, UserPoints
from app.services.points import get_or_create_points


def seed_admin() -> None:
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == settings.admin_username).first()
        if exists is None:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                nickname="管理员",
                role="admin",
            )
            db.add(admin)
            db.flush()
            get_or_create_points(db, admin.id)
            db.commit()
    finally:
        db.close()