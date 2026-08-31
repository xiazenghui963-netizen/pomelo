skill_meta = {
    "name": "skill_similarity_check",
    "description": "文本相似度校验工具 skill，返回 0-1 相似度分数",
    "access_level": 0,
    "cost_point": 0,
    "parameters": [
        {"name": "text_a", "type": "string", "required": True, "label": "文本A"},
        {"name": "text_b", "type": "string", "required": True, "label": "文本B"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    text_a = params.get("text_a", "")
    text_b = params.get("text_b", "")
    score = llm_client.similarity(text_a, text_b)
    threshold = getattr(llm_client, "similarity_threshold", 0.35)
    return {"similarity_score": score, "exceed_threshold": score > threshold, "threshold": threshold}