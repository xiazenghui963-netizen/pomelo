from fastapi import APIRouter, Depends

from app.config import settings
from app.core.errors import BizError
from app.database import get_db
from app.deps import get_current_user
from app.models import UserMaterial, User
from app.schemas import MaterialIn
from app.services.knowledge_base import (
    DEFAULT_DOC_TYPE,
    DOC_TYPE_HARD,
    DOC_TYPE_REFERENCE,
    VALID_DOC_TYPES,
    reindex_document,
    validate_hard_instruction,
)

router = APIRouter(prefix="/materials", tags=["materials"])


def _assert_content_len(content: str):
    if len(content) > settings.material_max_chars:
        raise BizError(
            f"单条资料最大 {settings.material_max_chars} 字符，请删减内容",
            code=40041,
            status_code=400,
        )


def _item(doc: UserMaterial) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "doc_type": doc.doc_type,
        "source_name": doc.source_name,
        "is_enabled": doc.is_enabled,
        "is_deleted": doc.is_deleted,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("")
def list_materials(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    rows = (
        db.query(UserMaterial)
        .filter(UserMaterial.user_id == current_user.id, UserMaterial.is_deleted == False)  # noqa: E712
        .order_by(UserMaterial.created_at.desc())
        .all()
    )
    return [_item(r) for r in rows]


@router.post("")
def create_material(body: MaterialIn, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    _assert_content_len(body.content.strip())
    doc_type = body.doc_type if body.doc_type in VALID_DOC_TYPES else DEFAULT_DOC_TYPE
    doc = UserMaterial(
        user_id=current_user.id,
        title=body.title.strip(),
        content=body.content,
        doc_type=doc_type,
        source_name=body.source_name.strip() or body.title.strip(),
        is_enabled=body.is_enabled,
    )
    db.add(doc)
    db.flush()
    reindex_document(db, doc)
    db.commit()
    db.refresh(doc)
    return _item(doc)


@router.put("/{material_id}")
def update_material(material_id: int, body: MaterialIn, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    doc = db.get(UserMaterial, material_id)
    if doc is None or doc.user_id != current_user.id or doc.is_deleted:
        raise BizError("资料不存在", code=40400, status_code=404)
    _assert_content_len(body.content.strip())
    doc_type = body.doc_type if body.doc_type in VALID_DOC_TYPES else (doc.doc_type or DEFAULT_DOC_TYPE)
    doc.title = body.title.strip()
    doc.content = body.content
    doc.doc_type = doc_type
    if body.source_name.strip():
        doc.source_name = body.source_name.strip()
    doc.is_enabled = body.is_enabled
    reindex_document(db, doc)
    db.commit()
    db.refresh(doc)
    return _item(doc)


@router.post("/{material_id}/toggle-enabled")
def toggle_enabled(material_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    doc = db.get(UserMaterial, material_id)
    if doc is None or doc.user_id != current_user.id or doc.is_deleted:
        raise BizError("资料不存在", code=40400, status_code=404)
    doc.is_enabled = not doc.is_enabled
    db.commit()
    return {"ok": True, "material": _item(doc)}


@router.post("/validate-enabled")
def validate_enabled(body, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """接口层前置校验：启用文档中 hard_instruction > 1 直接拦截（不调用大模型）。"""
    ids = (getattr(body, "material_ids", None) or getattr(body, "document_ids", None) or [])
    validate_hard_instruction(db, current_user.id, ids)
    return {"ok": True}


@router.delete("/{material_id}")
def delete_material(material_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserMaterial, material_id)
    if row is None or row.user_id != current_user.id:
        raise BizError("资料不存在", code=40400, status_code=404)
    from app.models import DocumentChunk

    db.query(DocumentChunk).filter(DocumentChunk.doc_id == material_id).delete()
    row.is_deleted = True
    db.commit()
    return {"id": material_id, "deleted": True}