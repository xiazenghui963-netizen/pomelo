import base64
import json
import time

from app.core.errors import BizError
from app.database import SessionLocal
from app.models import SkillCallLog, Task, now
from app.services import skills
from app.services.knowledge_base import assemble_vector_block, retrieve
from app.services.session_images import session_images
from app.services.llm import LLMClient
from app.services.points import refund


def _log_row(task_id: int, user_id: int, name: str, params: dict, result: dict, llm: LLMClient, duration_ms: int, error: str | None = None, status: str = "success"):
    return SkillCallLog(
        user_id=user_id,
        task_id=task_id,
        skill_name=name,
        status=status,
        cost_point=skills.get_meta(name).get("cost_point", 0),
        input_params=json.dumps(params, ensure_ascii=False, default=str),
        prompt=json.dumps(llm.last_prompt, ensure_ascii=False, default=str) if llm.last_prompt else None,
        model_output=json.dumps(result, ensure_ascii=False, default=str) if result else (llm.last_output or None),
        ocr_text=llm.last_ocr_text,
        similarity_score=llm.last_similarity,
        used_material_ids=json.dumps(params.get("material_ids", []), ensure_ascii=False) if params.get("material_ids") else None,
        error=error,
        duration_ms=duration_ms,
    )


def _call(db, task: Task, name: str, params: dict, llm: LLMClient) -> dict:
    started = time.perf_counter()
    llm.last_prompt = None
    llm.last_output = None
    llm.last_ocr_text = None
    llm.last_similarity = None
    error = None
    status = "success"
    try:
        result = skills.execute_skill(name, params, llm)
    except Exception as exc:  # noqa: BLE001
        result = {}
        error = str(exc)[:2000]
        status = "failed"
    duration_ms = int((time.perf_counter() - started) * 1000)
    db.add(_log_row(task.id, task.user_id, name, params, result, llm, duration_ms, error, status))
    db.flush()
    if error:
        raise BizError(error, code=50000, status_code=500)
    return result


def _load_session_image(task, inputs: dict) -> tuple[str, str] | None:
    """从内存暂存区取图并转为 base64；处理完成后立即丢弃，不落磁盘、不存云。"""
    token = inputs.get("session_image")
    if not token:
        return None
    rec = session_images.get(token)
    if rec is None or rec.get("user_id") != task.user_id:
        return None
    session_images.discard(token)
    b64 = base64.b64encode(rec["data"]).decode("ascii")
    return b64, rec.get("content_type") or "image/png"


def _build_vector_block(db, task: Task, inputs: dict) -> str:
    """私有向量知识库组装：只检索用户勾选启用的文档，按 meta 分类组装向量块。

    未启用私有资料 / 无启用文档 → 返回空串，完全跳过向量模块。
    组装顺序固定：总规则 → hard 区 → reference 区 → 【本次业务任务】。
    """
    if not inputs.get("use_vector"):
        return ""
    doc_ids = inputs.get("enabled_doc_ids", []) or []
    if not doc_ids:
        return ""
    query = inputs.get("text") or ""
    retrieved = retrieve(db, task.user_id, doc_ids, query)
    if not retrieved:
        return ""
    return assemble_vector_block(retrieved, query)


def _run_create_content(task: Task, inputs: dict, llm: LLMClient, db) -> dict:
    result: dict[str, str | dict | list] = {}
    material_ids = inputs.get("enabled_doc_ids", [])

    image_payload = _load_session_image(task, inputs)
    if image_payload:
        image_b64, content_type = image_payload
        params = {
            "image_data": image_b64,
            "content_type": content_type,
            "prompt": inputs.get("image_prompt"),
            "material_ids": material_ids,
        }
        parsed = _call(db, task, "skill_vlm_parse_image", params, llm)
        result["image_text"] = parsed.get("text", "")
        result["ocr_engine"] = parsed.get("engine", "")
    else:
        result["image_text"] = ""

    content = result["image_text"] or inputs.get("text", "")
    base_params = {
        "material_ids": material_ids,
        "vector_context": _build_vector_block(db, task, inputs),
    }

    decomp = _call(
        db, task, "skill_decompose_post",
        {"content_text": content or inputs.get("text", ""), **base_params}, llm,
    )
    result["decompose"] = decomp

    title_in = {"topic_text": inputs.get("text", "") or content[:2000], **base_params}
    titles = _call(db, task, "skill_generate_title", title_in, llm)
    result["titles"] = titles.get("titles", [])

    note = _call(
        db, task, "skill_generate_note",
        {
            "source_text": content or inputs.get("text", ""),
            "decompose": decomp,
            "titles": titles.get("titles", []),
            "vector_context": _build_vector_block(db, task, inputs),
            "material_ids": material_ids,
        }, llm,
    )
    result["note"] = note.get("note", "")
    result["note_char_count"] = note.get("char_count", 0)

    tags = _call(db, task, "skill_gen_tags", {"content_text": content or result["note"], **base_params}, llm)
    result["tags"] = tags.get("tags", [])

    if inputs.get("draw_image"):
        draw = _call(
            db, task, "skill_ai_draw",
            {"prompt": result["note"][:500] or inputs.get("text", ""), "material_ids": material_ids}, llm,
        )
        result["draw_image"] = draw

    return result


def _run_rewrite(task: Task, inputs: dict, llm: LLMClient, db) -> dict:
    material_ids = inputs.get("enabled_doc_ids", [])
    params = {
        "source_text": inputs.get("text", ""),
        "vector_context": _build_vector_block(db, task, inputs),
        "material_ids": material_ids,
    }
    rewritten = _call(db, task, "skill_human_rewrite", params, llm)
    return {
        "rewrite": rewritten,
        "similarity_score": rewritten.get("similarity_score"),
        "reminder": rewritten.get("reminder", ""),
    }


def run_job(task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if task is None:
            return
        task.status = "running"
        db.commit()

        inputs = json.loads(task.input_params or "{}")
        llm = LLMClient(user_id=task.user_id)
        llm.similarity_threshold = 0.35

        if inputs.get("skill_id"):
            from app.services.skill_engine import run_skill_task

            result = run_skill_task(task, inputs, llm, db)
        elif task.task_type == "create_content":
            result = _run_create_content(task, inputs, llm, db)
        elif task.task_type == "rewrite":
            result = _run_rewrite(task, inputs, llm, db)
        else:
            raise BizError(f"未知任务类型: {task.task_type}", code=40000, status_code=400)

        task.result = json.dumps(result, ensure_ascii=False)
        task.status = "success"
        task.finished_at = now()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None:
            task.status = "failed"
            task.error = str(exc)[:3000]
            task.finished_at = now()
            if task.points_cost > 0:
                refund(db, task.user_id, task.points_cost)
            db.commit()
    finally:
        db.close()