from skills._helpers import safe_json, wrap_prompt


def _mock(source: str) -> dict:
    source = (source or "").strip()
    if not source:
        return {"text": "", "similarity_score": 0.0, "reminder": ""}
    text = source.replace("吧", "呀").replace("吗", "啦")
    return {"text": text, "similarity_score": 1.0, "reminder": ""}


ANTI_CLEANUP_SYSTEM = (
    "你是内容改写助手，任务是对原文进行「避免洗稿」的深度改写。"
    "你必须做到以下强制要求：\n"
    "1. 完全改变句式结构，打散原文句子的组合顺序。\n"
    "2. 更换表达词汇，禁止连续照抄原文中的长句。\n"
    "3. 用自己的语气与视角重新组织内容，让观点表达方式完全不同。\n"
    "4. 保留原文的核心信息和要点，但表达形式不得与原文大比例重合。\n"
    "5. 输出应为全新的、面向小红书风格的正文，直接给结果不要解释。\n"
    "6. 改写结果的文本相似度必须显著降低，这是不可妥协的硬性标准。\n"
)


skill_meta = {
    "name": "skill_rewrite_note",
    "description": "改写生成完整笔记，内置强制防洗稿 System 提示词；支持传入私有资料文本；改写后自动执行相似度校验",
    "access_level": 1,
    "cost_point": 8,
    "parameters": [
        {"name": "source_text", "type": "string", "required": True, "label": "原文/笔记文本"},
        {"name": "materials_text", "type": "string", "required": False, "label": "私有资料"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    source = params.get("source_text", "").strip()
    materials = params.get("materials_text", "")
    if not source:
        return {"text": "", "similarity_score": 0.0, "reminder": "无原文可改写"}

    user_prompt = (
        "请将下面的原文进行深度改写，避免洗稿，输出全新的小红书笔记正文。\n\n"
        f"原文：\n{source}\n{wrap_prompt(materials)}"
    )
    text = llm_client.chat(ANTI_CLEANUP_SYSTEM, user_prompt)
    if not text:
        return _mock(source)

    similarity_score = llm_client.similarity(source, text)
    threshold = getattr(llm_client, "similarity_threshold", 0.35)
    reminder = ""
    if similarity_score > threshold:
        reminder = f"警告：改写文本与原文相似度 {similarity_score:.2f}（超过阈值 {threshold}），请人工再调整或重新改写。"
    return {"text": text.strip(), "similarity_score": similarity_score, "reminder": reminder}