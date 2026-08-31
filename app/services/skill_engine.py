"""Skill 模板调度引擎。

统一基座 System Prompt + skill_config 注入业务逻辑；强制输出 JSON，
按 skill 内部 output_json_schema 校验，校验失败抛出业务错误。
"""

import json
import re

from app.core.errors import BizError
from app.services.llm import LLMError, LLMTimeoutError, safe_json
from app.services.skill_configs import DEFAULT_SKILL_ID, load_config

BASE_SYSTEM_PROMPT = """# 角色：通用AI内容执行器
你是一个严格按照Skill配置执行任务的AI工具，不自行创造任务逻辑，一切行为完全服从传入的skill_config。

## 输入信息
1. 用户原始输入：{{user_input}}，可以是经过VLM/OCR提取的图片文本，或者用户手动输入的选题文本。
2. 参考资料：{{vector_context}}，私有向量检索出来的参考素材，可选；没有参考资料则忽略。
3. Skill配置：
```json
{{skill_config}}
```

## 输出要求
1. 严格依据 skill_config.output_json_schema 输出 JSON 对象，只输出 JSON 本身，不要任何多余文字。
2. 禁止输出解释、前言、尾语、代码块标记（不要出现 ```json 与 ```）。
3. 字段与结构必须与 output_json_schema 完全一致，不得缺失 required 字段，类型必须匹配。
4. 禁止占位造假：不得输出 xxxx、XX年XX月XX日、YYYY-MM-DD、2024-XX-XX、{{date}} 之类的虚假占位内容；无法给出的信息基于输入合理生成或省略。
5. 参考资料 vector_context 为空时忽略它，只依据用户输入与 skill_config 执行任务。
"""

_PLACEHOLDER_PATTERNS = [
    re.compile(r"Y{2,4}\s*[-–—/\\]\s*M{1,2}\s*[-–—/\\]\s*D{1,2}", re.IGNORECASE),
    re.compile(r"\d{4}\s*[-年/]\s*X{1,4}([月-]\d{1,4})?(日)?"),
    re.compile(r"[Xx]{2,}\s*[年月]"),
    re.compile(r"[Xx]{4,}"),
    re.compile(r"\{\{\s*(date|日期|time|时间)\s*\}\}", re.IGNORECASE),
    re.compile(r"(?:^|[\[【])\s*(日期|时间|date|time)\s*(?:[\]】]|[:：])", re.IGNORECASE),
    re.compile(r"\d{4}-[Xx]{1,2}-[Xx]{1,2}"),
]


def _has_placeholder(text: str) -> bool:
    return any(p.search(text) for p in _PLACEHOLDER_PATTERNS)


def build_prompt(user_input: str, vector_context: str, config: dict) -> str:
    # 只注入模型真正需要的部分，不灌整份配置（节省输入 token，加快生成）
    skill_body = {
        "name": config.get("name", ""),
        "system_prompt": config.get("system_prompt", ""),
        "output_json_schema": config.get("output_json_schema", {}),
    }
    return BASE_SYSTEM_PROMPT.replace(
        "{{user_input}}", (user_input or "（无）").strip()
    ).replace(
        "{{vector_context}}", (vector_context or "（无参考资料）").strip()
    ).replace(
        "{{skill_config}}", json.dumps(skill_body, ensure_ascii=False, indent=2)
    )


def _schema_error(value, schema: dict, path: str = "root") -> str | None:
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return f"{path} 类型应为 object"
        for name in schema.get("required") or []:
            if name not in value or value[name] is None:
                return f"{path} 缺少必需字段: {name}"
        for name, sub in (schema.get("properties") or {}).items():
            if name in value and value[name] is not None:
                err = _schema_error(value[name], sub, f"{path}.{name}")
                if err:
                    return err
        return None
    if t == "array":
        if not isinstance(value, list):
            return f"{path} 类型应为 array"
        items = schema.get("items")
        if items:
            for i, item in enumerate(value):
                err = _schema_error(item, items, f"{path}[{i}]")
                if err:
                    return err
        return None
    if t == "string":
        return None if isinstance(value, str) else f"{path} 类型应为 string"
    if t == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{path} 类型应为 integer"
        return None
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{path} 类型应为 number"
        return None
    if t == "boolean":
        return None if isinstance(value, bool) else f"{path} 类型应为 boolean"
    return None


def _scan_placeholders(value) -> bool:
    if isinstance(value, str):
        return _has_placeholder(value)
    if isinstance(value, list):
        return any(_scan_placeholders(v) for v in value)
    if isinstance(value, dict):
        return any(_scan_placeholders(v) for v in value.values())
    return False


def validate_output(output, schema: dict) -> str | None:
    err = _schema_error(output, schema)
    if err:
        return f"输出结构校验失败: {err}"
    if _scan_placeholders(output):
        return "输出包含脏占位/日期占位内容"
    return None


def _extract_image_text(llm, image_b64: str, content_type: str) -> tuple[str, str]:
    prompt = "请提取图片中的全部文字内容，并简要描述图片主体与结构，输出为纯文本。"
    text = llm.vlm(image_b64, prompt, content_type)
    engine = "vlm"
    if not text or len(text.strip()) < 10:
        ocr_text = llm.ocr(image_b64)
        if ocr_text and len(ocr_text.strip()) > len((text or "").strip()):
            text = ocr_text
            engine = "ocr_fallback"
    if not text or not text.strip():
        raise BizError("图片解析失败，请重新生成或改用文本输入", code=50002, status_code=400)
    llm.last_ocr_text = text.strip()
    return text.strip(), engine


def _check_hard_bans(note: str) -> str | None:
    """复用 skill_human_rewrite 的硬禁令检查（禁冒号/破折号/翻案腔/名词化/黑话等）。"""
    from skills.skill_human_rewrite import _check_summary

    return _check_summary(note or "")


def _repair_note(llm, note: str) -> str:
    issue = _check_hard_bans(note)
    if not issue or note is None:
        return note
    from skills.skill_human_rewrite import SYSTEM_REPAIR

    repaired = llm.chat(SYSTEM_REPAIR, f"{issue}\n\n待修复文本：\n{note}", {"temperature": 0.4, "max_tokens": 3000})
    return (repaired or note).strip()


def _mock_output(config, input_text, vector_context) -> dict:
    topic = (input_text or "").strip()[:24] or "新人入门"
    return {
        "hot_analysis": {
            "pain_points": [
                f"关于「{topic}」，信息很散，不知道从哪学起",
                "尝试过但没效果，容易中途放弃",
                "缺乏一套可以直接照做的具体方法",
            ],
            "topic_angles": [
                f"从亲身经历讲「{topic}」的踩坑与反转",
                f"把「{topic}」拆成保姆级步骤清单",
                "用前后对比案例讲清关键差异",
            ],
            "framework": {
                "opening": "直接抛出多数人都会踩的坑",
                "body": ["痛点场景共情", "方法分步拆解", "真实效果对比"],
                "ending": "总结金句，引导收藏与关注",
            },
        },
        "titles": [
            f"{topic}：新手最容易忽略的 3 个细节",
            f"从零做到「{topic}」，我踩过的坑都在这里",
            f"别再瞎折腾「{topic}」了，方法其实很简单",
        ],
        "note": f"整理了关于「{topic}」的真实经历和踩过的坑。\n\n刚开始我也是一头雾水，资料看了一堆，真正动手才发现完全不是那么回事。\n\n1. 先明确目标，别贪多。\n2. 找一份能对照的案例，照着拆解起步。\n3. 每做一次都记录调整和效果。\n\n坚持这三步，进度立刻不一样。希望我的经历能帮到同样迷茫的你。",
        "tags": ["成长干货", "经验分享", "避坑指南"],
    }


def run_skill_task(task, inputs: dict, llm, db) -> dict:
    import app.services.jobs as jobs

    skill_id = inputs.get("skill_id") or DEFAULT_SKILL_ID
    config = load_config(skill_id)
    material_ids = inputs.get("enabled_doc_ids") or []

    result: dict = {}
    input_text = ""
    image_payload = jobs._load_session_image(task, inputs)
    if image_payload:
        image_b64, content_type = image_payload
        text, engine = _extract_image_text(llm, image_b64, content_type)
        result["ocr_text"] = text
        result["ocr_engine"] = engine
        input_text = text
    raw = (inputs.get("text") or "").strip()
    if raw:
        input_text = input_text.strip() + ("\n\n" + raw if input_text.strip() else raw)

    vector_context = jobs._build_vector_block(db, task, inputs)
    system_prompt = build_prompt(input_text, vector_context, config)
    try:
        raw_out = llm.chat(system_prompt, "请严格执行输出要求，直接返回 JSON 结果。", config.get("model_params"))
    except LLMTimeoutError:
        raise BizError("大模型接口请求超时，请重试，或更换模型API", code=50003, status_code=500)
    except LLMError:
        raise BizError("大模型接口调用失败，请重试，或更换模型API", code=50004, status_code=500)

    if raw_out is None:
        # 未配置大模型 / 模拟模式：走 mock 分支（与既有 skill 降级策略一致）
        output = _mock_output(config, input_text, vector_context)
    else:
        output = safe_json(raw_out)
        if output is None:
            raise BizError("AI生成异常，请重新生成", code=50001, status_code=500)
        err = validate_output(output, config.get("output_json_schema"))
        if err:
            raise BizError("AI生成异常，请重新生成", code=50001, status_code=500)
    result.update(output)

    # 采用 skill_human_rewrite 的硬禁令检查：命中则自动修复一轮，保证任意模型输出质量
    if isinstance(result.get("note"), str) and result["note"] and raw_out is not None:
        result["note"] = _repair_note(llm, result["note"])

    if inputs.get("draw_image"):
        from app.services.skills import execute_skill

        draw = execute_skill(
            "skill_ai_draw",
            {"prompt": (result.get("note") or input_text or "")[:500], "material_ids": material_ids},
            llm,
        )
        result["draw_image"] = draw

    return result