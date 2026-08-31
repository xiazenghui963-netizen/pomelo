from pydantic import BaseModel, Field

from .config import settings


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=32)


class LoginIn(BaseModel):
    username: str
    password: str


class MaterialIn(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1)
    doc_type: str = Field(default="reference_context", pattern="^(hard_instruction|reference_context)$")
    source_name: str = Field(default="", max_length=128)
    is_enabled: bool = Field(default=True)


class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1)
    source_name: str = Field(default="", max_length=128)
    doc_type: str = Field(default="reference_context", pattern="^(hard_instruction|reference_context)$")
    is_enabled: bool = True


class ValidateEnabledIn(BaseModel):
    document_ids: list[int] = Field(default=[])


class TaskCreateIn(BaseModel):
    task_type: str = Field(pattern="^(create_content|rewrite|skill_task)$")
    skill_id: str | None = Field(default=None, max_length=64)
    text: str = Field(default="", max_length=8000)
    session_image: str | None = None
    use_materials: bool = False
    material_ids: list[int] = Field(default=[], max_length=settings.material_max_select)
    draw_image: bool = False


class MemberActivateIn(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    is_member: bool = True


class LlmModelIn(BaseModel):
    type: str = Field(default="text", pattern="^(text|image)$")
    config_name: str = Field(min_length=1, max_length=64)
    model_name: str = Field(max_length=128)
    base_url: str = Field(default="", max_length=512)
    api_key: str = Field(default="", max_length=512)
    api_key_masked_confirm: str = Field(default="", max_length=512)
    is_default: bool = False