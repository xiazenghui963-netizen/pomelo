"""生成小红书风格标题。"""

import re


def _extract_topic(content: str, vector_context: str) -> str:
    """从原文 / 向量召回上下文提取最可能的主题（避免 mock 跑题）。"""
    target = content or vector_context
    if not target:
        return "这个话题"
    body = re.sub(r"【.*?】|\[.*?\]|#.*?\n|\n+", " ", target).strip()
    # 优先取最长的一段中文（往往是主题句）
    parts = [p for p in re.split(r"[。！？\n;；，,]", body) if len(p.strip()) >= 4]
    if parts:
        return max(parts, key=len).strip()[:30]
    return body[:30] or "这个话题"


def _mock(topic_text: str, vector_context: str) -> dict:
    topic = _extract_topic(topic_text, vector_context)
    # 用向量上下文里非硬指令的参考片段作为话题脚注，产出差异化短语
    ref_hints = _reference_hints(vector_context)
    hint = ref_hints[0] if ref_hints else None

    titles = [
        f"别再踩坑！{topic}的正确打开方式",
        f"关于{topic}，这 3 点 90% 的人都理解偏了",
        f"{topic}实操记录：亲测有效的几个关键动作",
        f"被疯转的{topic}经验，今天一次讲透",
        f"建议先收藏再慢慢看：{topic}避坑清单",
        f"刷到就是缘分，{topic}的真实复盘来了",
        f"普通人也能做好的{topic}，别再焦虑了",
        f"亲测一个月的{topic}，结果超出预期",
    ]
    if hint:
        # 把参考句揉进标题，增加上下文相关性
        short = hint[:16]
        titles.insert(0, f"{short}…关于{topic}的一份实测复盘")

    return {"titles": titles[:8]}


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
        if len(out) >= 3:
            break
    return out


skill_meta = {
    "name": "skill_generate_title",
    "description": "生成多组小红书风格标题（mock 时结合原文与向量上下文）",
    "access_level": 0,
    "cost_point": 3,
    "parameters": [
        {"name": "topic_text", "type": "string", "required": True, "label": "选题描述"},
        {"name": "vector_context", "type": "string", "required": False, "label": "向量上下文"},
    ],
}


_SYSTEM = (
    "你是小红书爆款标题专家。请基于给定的选题描述与私有向量资料上下文，"
    "生成 8 个小红书风格标题：口语化、有情绪张力、善用数字/悬念/对比，每行一个，不要编号。"
)


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    topic = params.get("topic_text", "")
    vector_context = params.get("vector_context", "")

    user_prompt = (
        f"选题描述：\n{topic}\n\n"
        f"可参考的私有向量资料上下文（仅作背景，不要照抄原文）：\n{vector_context or '（无）'}\n\n"
        "请输出 8 个爆款标题。"
    )
    raw = llm_client.chat(_SYSTEM, user_prompt)
    parsed = _safe_json(raw)
    if parsed and "titles" in parsed:
        return {"titles": parsed["titles"][:8]}
    if raw:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if lines:
            return {"titles": lines[:8]}
    return _mock(topic, vector_context)


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