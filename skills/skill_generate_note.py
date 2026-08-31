"""生成小红书笔记正文（基于原文改写 + 拆解结构 + 向量上下文，mock 差异化取材）。"""

import re


def _extract_first(content: str) -> str:
    if not content:
        return ""
    parts = re.split(r"[。！？\n]", content)
    for p in parts:
        p = p.strip()
        if len(p) >= 6:
            return p
    return content.strip()[:30]


def _reference_hints(vector_context: str) -> list[str]:
    if not vector_context:
        return []
    out = []
    for line in vector_context.splitlines():
        line = line.strip()
        if not line or line.startswith("【") or line.startswith("["):
            continue
        if len(line) >= 12:
            out.append(line)
        if len(out) >= 3:
            break
    return out


def _decompose_text(decompose) -> str:
    if isinstance(decompose, str):
        try:
            import json

            decompose = json.loads(decompose)
        except Exception:  # noqa: BLE001
            decompose = None
    if not isinstance(decompose, dict):
        return "（无拆解结果）"
    parts = []
    if decompose.get("pain_points"):
        parts.append("痛点：" + "；".join(str(p) for p in decompose["pain_points"]))
    if decompose.get("topic_angles"):
        parts.append("选题角度：" + "；".join(str(a) for a in decompose["topic_angles"]))
    if decompose.get("framework"):
        parts.append("写作框架：" + str(decompose["framework"]))
    return "\n".join(parts) if parts else "（无拆解结果）"


def _mock(source_text: str, decompose: dict | None, vector_context: str) -> dict:
    first = _extract_first(source_text) or _extract_first(vector_context)
    hints = _reference_hints(vector_context)
    pains = []
    if isinstance(decompose, dict):
        pains = (decompose.get("pain_points") or [])[:1]
    pain = pains[0] if pains else ""
    hint = hints[0] if hints else ""

    note = ""
    if first:
        note += f"先看结论：{first}\n\n"
    note += "这篇是把亲身经历和踩坑整理出来的经验，不是套模板。\n\n"
    if pain:
        note += f"最先绕不开的是：{pain}\n\n"
    if hint:
        note += f"结合资料里的一点参考：{hint[:60]}\n\n"
    note += (
        "如果你也在纠结同一件事，建议先把最耗时间的那一步单独做完一遍，"
        "再回来看整体效果，比一次全扑上去更靠谱。\n\n"
    )
    note += "具体的差别和细节，欢迎在评论里慢慢聊。"
    return {"note": note, "char_count": len(note)}


skill_meta = {
    "name": "skill_generate_note",
    "description": "生成小红书笔记正文：基于原文改写润色，参考爆款拆解结构与私有向量资料（mock 时差异化取材）",
    "access_level": 0,
    "cost_point": 5,
    "parameters": [
        {"name": "source_text", "type": "string", "required": True, "label": "原文全文（OCR/用户输入）"},
        {"name": "decompose", "type": "object", "required": False, "label": "爆款拆解结果"},
        {"name": "titles", "type": "list", "required": False, "label": "标题候选"},
        {"name": "vector_context", "type": "string", "required": False, "label": "私有向量资料上下文"},
    ],
}

_SYSTEM = (
    "你是小红书笔记正文作者。基于原文全文与私有向量资料上下文改写成一篇小红书笔记："
    "保留原文核心观点与关键信息、延续原文风格，不要强行改成干货教程，"
    "不要硬套1.2.3.分点模板，口语化、分段短、适度emoji、结尾引导互动。"
)


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    source = params.get("source_text", "").strip()
    decompose = params.get("decompose")
    titles = params.get("titles") or []
    vector_context = params.get("vector_context", "")

    title = titles[0] if titles else ""
    user_prompt = (
        f"【原文全文】\n{source}\n\n"
        f"【爆款拆解（参考结构，不照搬）】\n{_decompose_text(decompose)}\n\n"
        f"【私有向量资料上下文（仅作背景，不要照抄）】\n{vector_context or '（无）'}\n\n"
        f"【标题候选】\n{title or '（无标题候选）'}\n\n"
        "请直接输出改写后的小红书笔记正文。"
    )
    raw = llm_client.chat(_SYSTEM, user_prompt)
    if raw and len(raw.strip()) >= 50:
        return {"note": raw.strip(), "char_count": len(raw.strip())}
    return _mock(source, decompose, vector_context)