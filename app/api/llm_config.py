import logging

from fastapi import APIRouter, Depends

from app.core.crypto import decrypt, encrypt, mask_secret
from app.core.errors import BizError
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserLlmModel
from app.schemas import LlmModelIn

router = APIRouter(prefix="/llm-models", tags=["llm-models"])

logger = logging.getLogger(__name__)


def _encrypt_or_keep(body: LlmModelIn, current_masked: str, existing_cipher: str) -> str:
    """api_key 加密保存：\n    1) 前端回传脱敏串与当前脱敏串一致 → 未修改密钥，保留原密文；\n    2) 提供了新密钥文本 → 加密新值；\n    3) 编辑时两者都为空 → 保留原密文。\n    """
    if body.api_key_masked_confirm and body.api_key_masked_confirm == current_masked:
        return existing_cipher
    if body.api_key:
        return encrypt((body.api_key or "").strip())
    return existing_cipher if existing_cipher else encrypt("")


def _item(row: UserLlmModel) -> dict:
    plain = decrypt(row.api_key or "")
    return {
        "id": row.id,
        "type": row.type,
        "config_name": row.config_name,
        "model_name": row.model_name,
        "base_url": row.base_url,
        "api_key_masked": mask_secret(plain) if plain else "",
        "has_key": bool(plain),
        "is_default": row.is_default,
        "update_time": row.update_time.isoformat() if row.update_time else "",
    }


def _reset_default(db, user_id: int, mtype: str, except_id: int | None = None) -> None:
    q = db.query(UserLlmModel).filter(UserLlmModel.user_id == user_id, UserLlmModel.type == mtype)
    if except_id is not None:
        q = q.filter(UserLlmModel.id != except_id)
    for r in q.all():
        if r.is_default:
            r.is_default = False


@router.get("")
def list_models(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    rows = (
        db.query(UserLlmModel)
        .filter(UserLlmModel.user_id == current_user.id)
        .order_by(UserLlmModel.type, UserLlmModel.is_default.desc(), UserLlmModel.update_time.desc())
        .all()
    )
    from app.config import settings

    return {
        "enable_ai_simulate": settings.enable_ai_simulate,
        "models": [_item(r) for r in rows],
    }


@router.post("")
def create_model(body: LlmModelIn, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    if body.type not in ("text", "image"):
        raise BizError("模型类型仅支持 text / image", code=40001, status_code=400)
    same_name = (
        db.query(UserLlmModel)
        .filter(
            UserLlmModel.user_id == current_user.id,
            UserLlmModel.type == body.type,
            UserLlmModel.config_name == body.config_name.strip(),
        )
        .first()
    )
    if same_name is not None:
        raise BizError("该类型下已存在同名配置", code=40002, status_code=400)

    duplicate = (
        db.query(UserLlmModel)
        .filter(
            UserLlmModel.user_id == current_user.id,
            UserLlmModel.type == body.type,
            UserLlmModel.model_name == body.model_name.strip(),
            UserLlmModel.base_url == body.base_url.strip(),
        )
        .first()
    )
    if duplicate is not None:
        raise BizError("该模型配置已存在", code=40003, status_code=400)

    row = UserLlmModel(
        user_id=current_user.id,
        type=body.type,
        config_name=body.config_name.strip(),
        model_name=body.model_name.strip(),
        base_url=body.base_url.strip(),
        api_key=encrypt((body.api_key or "").strip()),
        is_default=body.is_default,
    )
    if body.is_default:
        _reset_default(db, current_user.id, body.type)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "model": _item(row)}


@router.put("/{model_id}")
def update_model(model_id: int, body: LlmModelIn, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserLlmModel, model_id)
    if row is None or row.user_id != current_user.id:
        raise BizError("模型配置不存在", code=40400, status_code=404)
    if body.type not in ("text", "image"):
        raise BizError("模型类型仅支持 text / image", code=40001, status_code=400)

    same_name = (
        db.query(UserLlmModel)
        .filter(
            UserLlmModel.user_id == current_user.id,
            UserLlmModel.type == body.type,
            UserLlmModel.config_name == body.config_name.strip(),
            UserLlmModel.id != model_id,
        )
        .first()
    )
    if same_name is not None:
        raise BizError("该类型下已存在同名配置", code=40002, status_code=400)

    current_masked = mask_secret(decrypt(row.api_key or ""))
    row.type = body.type
    row.config_name = body.config_name.strip()
    row.model_name = body.model_name.strip()
    row.base_url = body.base_url.strip()
    row.api_key = _encrypt_or_keep(body, current_masked or "", row.api_key or "")

    if body.is_default:
        _reset_default(db, current_user.id, body.type, except_id=model_id)
    row.is_default = bool(body.is_default)
    db.commit()
    db.refresh(row)
    return {"ok": True, "model": _item(row)}


@router.delete("/{model_id}")
def delete_model(model_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserLlmModel, model_id)
    if row is None or row.user_id != current_user.id:
        raise BizError("模型配置不存在", code=40400, status_code=404)
    db.delete(row)
    db.commit()
    return {"ok": True, "id": model_id}


@router.post("/{model_id}/set-default")
def set_default(model_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserLlmModel, model_id)
    if row is None or row.user_id != current_user.id:
        raise BizError("模型配置不存在", code=40400, status_code=404)
    _reset_default(db, current_user.id, row.type, except_id=model_id)
    row.is_default = True
    db.commit()
    return {"ok": True, "id": model_id, "type": row.type}


@router.post("/{model_id}/check")
def check_model(model_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserLlmModel, model_id)
    if row is None or row.user_id != current_user.id:
        raise BizError("模型配置不存在", code=40400, status_code=404)
    base_url = row.base_url
    api_key = decrypt(row.api_key or "")
    model_name = row.model_name
    if not (base_url and api_key and model_name):
        logger.warning("模型检查失败 user=%s id=%s: 配置不完整", current_user.id, model_id)
        return {"ok": False}

    from app.config import settings

    if settings.enable_ai_simulate:
        logger.info("模型检查 user=%s id=%s: 模拟模式跳过真实连接", current_user.id, model_id)
        return {"ok": True}

    from app.services.llm import LLMClient

    llm = LLMClient()
    resp = llm.test_chat(base_url, api_key, model_name)
    if resp:
        logger.info("模型检查 user=%s id=%s: 连接成功", current_user.id, model_id)
        return {"ok": True}
    logger.warning("模型检查 user=%s id=%s: 连接失败", current_user.id, model_id)
    return {"ok": False}