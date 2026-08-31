from skills._helpers import safe_json, wrap_prompt


def _mock(content: str) -> dict:
    topic = (content or "").strip()[:8]
    tags = [
        f"#{topic}" if topic else "#干货分享",
        "#新手必看",
        "#避坑指南",
        "#经验分享",
        "#生活小技巧",
        "#实用干货",
        "#建议收藏",
        "#涨知识",
    ]
    return {"tags": tags}


skill_meta = {
    "name": "skill_gen_tags",
    "description": "生成小红书话题标签",
    "access_level": 0,
    "cost_point": 1,
    "parameters": [
        {"name": "content_text", "type": "string", "required": True, "label": "内容文本"},
        {"name": "materials_text", "type": "string", "required": False, "label": "私有资料"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    content = params.get("content_text", "")
    materials = params.get("materials_text", "")
    user_prompt = (
        "基于内容生成 10 个小红书话题标签，每行一个，格式以 # 开头。\n\n"
        f"内容：\n{content}\n{wrap_prompt(materials)}"
    )
    system = "你是小红书话题标签策划专家，熟悉平台流量与垂类标签组合。"
    raw = llm_client.chat(system, user_prompt)
    parsed = safe_json(raw)
    if parsed and "tags" in parsed:
        return {"tags": parsed["tags"]}
    if raw:
        tags = [ln.strip() for ln in raw.splitlines() if ln.strip().startswith("#")]
        if tags:
            return {"tags": tags[:12]}
    return _mock(content)