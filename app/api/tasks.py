import json

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.errors import BizError
from app.core.tasks import enqueue
from app.database import get_db
from app.deps import get_current_user
from app.models import SkillCallLog, Task, User, UserMaterial
from app.schemas import TaskCreateIn
from app.services.knowledge_base import validate_hard_instruction
from app.services.session_images import session_images
from app.services.skill_configs import DEFAULT_SKILL_ID, load_config, task_cost
from app.services.points import apply_daily_grant, calc_pipeline_cost, deduct, get_or_create_points, validate_member_access

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _resolve_enabled_docs(db, user_id: int, material_ids: list[int]) -> tuple[list[int], str]:
    """解析用户勾选启用的私有文档（不再把资料原文直接拼进 prompt）。

    - 未勾选 → 返回空列表（调用方完全跳过向量模块）
    - 前置校验：启用文档中 hard_instruction 数量 > 1 → 拦截，不调用大模型
    - 只保存启用文档 id，业务 prompt 组装在 jobs 阶段用向量召回完成
    """
    if not material_ids:
        return [], ""
    ids = list(dict.fromkeys(material_ids))
    if len(ids) > settings.material_max_select:
        raise BizError(f"最多选择 {settings.material_max_select} 条私有资料", code=40020, status_code=400)
    rows = (
        db.query(UserMaterial)
        .filter(
            UserMaterial.user_id == user_id,
            UserMaterial.is_deleted == False,  # noqa: E712
            UserMaterial.id.in_(ids),
        )
        .all()
    )
    found = {r.id for r in rows}
    if len(found) != len(ids):
        raise BizError("部分私有资料不存在或无权访问", code=40021, status_code=400)
    # 接口层前置校验：hard_instruction > 1 直接拦截（不调用大模型）
    validate_hard_instruction(db, user_id, ids)
    return ids, ""


def _session_image_ok(current_user_id: int, token: str | None) -> bool:
    if not token:
        return False
    rec = session_images.get(token)
    if rec is None or rec.get("user_id") != current_user_id:
        return False
    return True


@router.post("")
def create_task(
    body: TaskCreateIn,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    has_image = _session_image_ok(current_user.id, body.session_image)
    if body.task_type == "skill_task":
        skill_id = (body.skill_id or DEFAULT_SKILL_ID).strip() or DEFAULT_SKILL_ID
        skill_cfg = load_config(skill_id)  # 不存在则 404
        if not body.text and not has_image:
            raise BizError("请至少填写选题文本或上传截图", code=40030, status_code=400)
    else:
        skill_id = None
        if body.task_type == "create_content" and not body.text and not has_image:
            raise BizError("请至少填写选题文本或上传截图", code=40030, status_code=400)
        if body.task_type == "rewrite" and not body.text:
            raise BizError("请填写需要改写的原文", code=40031, status_code=400)

    points_row = get_or_create_points(db, current_user.id)
    apply_daily_grant(db, current_user.id)
    if body.task_type == "skill_task":
        if int(skill_cfg.get("access_level") or 0) == 1 and not points_row.is_member:
            raise BizError("该 Skill 为会员专属，请先开通会员", code=40301, status_code=403)
        if body.draw_image and not points_row.is_member:
            raise BizError("AI 配图为会员专属，请先开通会员", code=40301, status_code=403)
        cost = task_cost(skill_id, body.draw_image)
    else:
        validate_member_access(body.task_type, has_image, body.draw_image, points_row.is_member)
        cost = calc_pipeline_cost(body.task_type, has_image, body.draw_image)
    deduct(db, current_user.id, cost)

    # 私有向量知识库：只保存启用文档 id 与检索 query，资料原文交由向量检索/分类组装，不直接进 prompt
    enabled_doc_ids, _ = _resolve_enabled_docs(db, current_user.id, body.material_ids)
    use_vector = bool(enabled_doc_ids)
    inputs = {
        "task_type": body.task_type,
        "skill_id": skill_id,
        "text": body.text,
        "session_image": body.session_image if has_image else None,
        "draw_image": body.draw_image,
        "enabled_doc_ids": enabled_doc_ids,
        "use_vector": use_vector,
        "vector_query": body.text or "",
    }
    task = Task(
        user_id=current_user.id,
        task_type=body.task_type,
        skill_id=skill_id,
        status="pending",
        input_params=json.dumps(inputs, ensure_ascii=False),
        points_cost=cost,
        used_material_ids=json.dumps(enabled_doc_ids, ensure_ascii=False) if enabled_doc_ids else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    enqueue(task.id)
    return {"task_id": task.id, "points_cost": cost, "status": task.status}


@router.get("")
def list_tasks(current_user: User = Depends(get_current_user), db=Depends(get_db), page: int = 1, size: int = 20):
    q = db.query(Task).filter(Task.user_id == current_user.id).order_by(Task.created_at.desc(), Task.id.desc())
    total = q.count()
    rows = q.offset((page - 1) * size).limit(size).all()
    items = []
    for r in rows:
        try:
            result = json.loads(r.result or "{}")
        except Exception:  # noqa: BLE001
            result = {}
        items.append({
            "id": r.id,
            "task_type": r.task_type,
            "skill_id": r.skill_id,
            "status": r.status,
            "points_cost": r.points_cost,
            "created_at": r.created_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "error": r.error,
            "summary": _task_summary(r.task_type, result),
        })
    return {"items": items, "total": total, "page": page, "size": size}


def _task_summary(task_type: str, result: dict) -> dict:
    summary = {}
    if task_type == "create_content":
        summary = {
            "decompose": result.get("decompose"),
            "titles": result.get("titles", [])[:3],
            "note": (result.get("note") or "")[:60],
            "tags": result.get("tags", [])[:5],
            "draw_image": (result.get("draw_image") or {}).get("image_url"),
        }
    elif task_type == "rewrite":
        summary = {
            "note": (result.get("rewrite") or {}).get("text", "")[:60],
            "similarity_score": (result.get("rewrite") or {}).get("similarity_score"),
        }
    elif task_type == "skill_task":
        summary = {
            "note": (result.get("note") or "")[:60],
            "titles": (result.get("titles") or [])[:3],
        }
    return summary


@router.get("/{task_id}")
def get_task(task_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise BizError("任务不存在", code=40400, status_code=404)
    try:
        result = json.loads(task.result or "{}")
    except Exception:  # noqa: BLE001
        result = {}
    return {
        "id": task.id,
        "task_type": task.task_type,
        "skill_id": task.skill_id,
        "status": task.status,
        "points_cost": task.points_cost,
        "used_material_ids": json.loads(task.used_material_ids or "[]"),
        "created_at": task.created_at.isoformat(),
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "result": result,
    }


@router.post("/{task_id}/retry")
def retry_task(task_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise BizError("任务不存在", code=40400, status_code=404)
    inputs = json.loads(task.input_params or "{}")

    token = inputs.get("session_image")
    has_image = _session_image_ok(current_user.id, token)

    points_row = get_or_create_points(db, current_user.id)
    apply_daily_grant(db, current_user.id)
    skill_id = inputs.get("skill_id")
    if skill_id:
        skill_cfg = load_config(skill_id)
        if int(skill_cfg.get("access_level") or 0) == 1 and not points_row.is_member:
            raise BizError("该 Skill 为会员专属，请先开通会员", code=40301, status_code=403)
        if bool(inputs.get("draw_image")) and not points_row.is_member:
            raise BizError("AI 配图为会员专属，请先开通会员", code=40301, status_code=403)
        cost = task_cost(skill_id, bool(inputs.get("draw_image")))
    else:
        validate_member_access(task.task_type, has_image, bool(inputs.get("draw_image")), points_row.is_member)
        cost = calc_pipeline_cost(task.task_type, has_image, bool(inputs.get("draw_image")))
    deduct(db, current_user.id, cost)

    new_inputs = {**inputs, "session_image": token if has_image else None}
    new_task = Task(
        user_id=current_user.id,
        task_type=task.task_type,
        skill_id=skill_id,
        status="pending",
        input_params=json.dumps(new_inputs, ensure_ascii=False),
        points_cost=cost,
        used_material_ids=json.dumps(new_inputs.get("enabled_doc_ids", []), ensure_ascii=False) if new_inputs.get("enabled_doc_ids") else None,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    enqueue(new_task.id)
    return {"task_id": new_task.id, "points_cost": cost, "status": new_task.status}


@router.delete("/{task_id}")
def delete_task(task_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise BizError("任务不存在", code=40400, status_code=404)
    if task.status == "running":
        raise BizError("任务正在执行中，请稍后再删除", code=40002, status_code=400)
    try:
        # 先清理与任务存在外键关联的日志记录（task_id → tasks.id），再删除任务本身
        db.query(SkillCallLog).filter(SkillCallLog.task_id == task_id).delete()
        db.delete(task)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise BizError(f"任务删除失败：{exc}", code=40003, status_code=400)
    return {"id": task_id, "deleted": True}