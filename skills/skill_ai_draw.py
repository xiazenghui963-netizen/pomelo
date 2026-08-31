skill_meta = {
    "name": "skill_ai_draw",
    "description": "AI 绘图生成笔记配图；直接使用大模型返回的第三方图片链接，本服务不下载、不存储图片",
    "access_level": 1,
    "cost_point": 10,
    "parameters": [
        {"name": "prompt", "type": "string", "required": True, "label": "绘图提示词"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    prompt = params.get("prompt", "")
    image_url = llm_client.generate_image(prompt)
    return {
        "image_url": image_url,
        "prompt": prompt,
        "success": bool(image_url),
        "note": "" if image_url else "未配置 AI 绘图服务或生成失败，未保存图片",
    }