"""
爆款内容拆解（痛点/选题角度/写作框架）。
mock 时结合原文与向量上下文，差异化输出，不重复固定文案。
"""

import re


def _extract_sentences(content: str) -> list[str]:
    if not content:
        return []
    parts = re.split(r"[。！？\n；;]", content)
    return [p.strip() for p in parts if len(p.strip()) >= 6]


def _extract_topic(text: str) -> str:
    s = _extract_sentences(text)
    return s[0][:30] if s else (text or "通用话题").strip()[:30]


def _reference_hints(text: str) -> list[str]:
    if not text:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("【") or line.startswith("[") or line.startswith("#"):
            continue
        if len(line) >= 10:
            out.append(line)
        if len(out) >= 2:
            break
    return out


def _mock(content_text: str, vector_context: str) -> dict:
    source = content_text or vector_context
    topic = _extract_topic(source)
    sentences = _extract_sentences(content_text) or _extract_sentences(vector_context)

    pains = []
    for s in sentences[:3]:
        pains.append(f"{s[:20]}…这一点其实很多人没抓住")
    if not pains:
        pains = ["信息过载，不知道从哪下手", "尝试过但没效果，容易放弃", "缺少可复制的具体方法"]

    ref = _reference_hints(vector_context)
    angles = [
        f"从自身经历讲「{topic}」的踩坑与反转",
        f"用对比案例说明「{topic}」的关键差异",
        f"把「{topic}」拆成保姆级步骤清单",
    ]
    if ref:
        angles.insert(0, f"结合{ref[0][:16]}…切入「{topic}」的真实场景")

    framework = {
        "opening": "直接抛出多数人都会踩的坑",
        "body": ["痛点场景共情", "方法论分步拆解", "真实效果对比"],
        "ending": "总结金句 + 引导收藏/关注",
    }
    return {"pain_points": pains[:3], "topic_angles": angles[:4], "framework": framework}


skill_meta = {
    "name": "skill_decompose_post",
    "description": "帖子爆款拆解：痛点/选题角度/写作框架（mock 时结合原文与向量上下文）",
    "access_level": 0,
    "cost_point": 0,
    "parameters": [
        {"name": "content_text", "type": "string", "required": True, "label": "原帖文本"},
        {"name": "vector_context", "type": "string", "required": False, "label": "向量上下文"},
    ],
}


_SYSTEM = (
    "你是资深新媒体拆解专家。请分析给定文本，输出 JSON："
    '{"pain_points":["痛点1",...], "topic_angles":["角度1",...], '
    '"framework":{"opening":..., "body":[...], "ending":...}}'
)


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    content = params.get("content_text", "")
    vector_context = params.get("vector_context", "")

    user_prompt = (
        f"原帖文本：\n{content}\n\n"
        f"可参考的私有向量资料上下文（仅作创作背景，不要照抄）：\n{vector_context or '（无）'}\n\n"
        "请输出热点拆解 JSON。"
    )
    raw = llm_client.chat(_SYSTEM, user_prompt)
    parsed = _safe_json(raw)
    if parsed:
        return {
            "pain_points": parsed.get("pain_points") or [],
            "topic_angles": parsed.get("topic_angles") or [],
            "framework": parsed.get("framework") or {},
        }
    return _mock(content, vector_context)


def _safe_json(text: str) -> dict | None:
    import json

    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, dict) else None
            except Exception:  # noqa: BLE001
                return None
        return None