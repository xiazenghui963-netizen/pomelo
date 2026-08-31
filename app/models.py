from datetime import datetime, date, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    nickname: Mapped[str] = mapped_column(String(32), default="")
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    points: Mapped["UserPoints"] = relationship(back_populates="user", uselist=False, cascade="all,delete-orphan")


class UserPoints(Base):
    __tablename__ = "user_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    points_balance: Mapped[int] = mapped_column(Integer, default=0)
    is_member: Mapped[bool] = mapped_column(Boolean, default=False)
    last_daily_grant: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    user: Mapped[User] = relationship(back_populates="points")


class UserMaterial(Base):
    """用户私有资料（兼容旧版直接文本资料，升级后作为源文档载体）。
    doc_type: hard_instruction=AI强制生成约束 / reference_context=事实参考素材（默认）。"""
    __tablename__ = "user_material"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(String(24), default="reference_context")
    source_name: Mapped[str] = mapped_column(String(128), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)   # 用户在页面勾选是否启用该文档参与任务
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class DocumentChunk(Base):
    """多租户私有向量知识库切片。
    meta_json 为元数据，doc_type 来源于源文档标记（默认 reference_context），不靠文本判定。"""
    __tablename__ = "document_chunk"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("user_material.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")  # 向量元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(32))  # create_content / rewrite / skill_task
    skill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    input_params: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[str] = mapped_column(Text, default="{}")
    points_cost: Mapped[int] = mapped_column(Integer, default=0)
    used_material_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserLlmModel(Base):
    __tablename__ = "user_llm_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(16), default="text")  # text / image
    config_name: Mapped[str] = mapped_column(String(64), default="")
    model_name: Mapped[str] = mapped_column(String(128), default="")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    api_key: Mapped[str] = mapped_column(Text, default="")  # 密文存储
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class SkillCallLog(Base):
    __tablename__ = "skill_call_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    skill_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    cost_point: Mapped[int] = mapped_column(Integer, default=0)
    input_params: Mapped[str] = mapped_column(Text, default="{}")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_material_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)