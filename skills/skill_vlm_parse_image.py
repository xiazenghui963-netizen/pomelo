def _mock() -> dict:
    return {
        "text": "[模拟VLM] 图片解析结果占位（未配置VLM服务）",
        "engine": "mock",
        "degraded": True,
    }


skill_meta = {
    "name": "skill_vlm_parse_image",
    "description": "VLM 多模态解析图片；图片以 base64 传入，VLM 不可用或文本过少时自动降级到 OCR，消耗更高点数",
    "access_level": 0,
    "cost_point": 8,
    "parameters": [
        {"name": "image_data", "type": "string", "required": True, "label": "图片 base64"},
        {"name": "content_type", "type": "string", "required": False, "label": "图片类型"},
        {"name": "prompt", "type": "string", "required": False, "label": "解析提示词"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    image_data = params.get("image_data", "")
    content_type = params.get("content_type") or "image/png"
    prompt = params.get("prompt") or "请提取图片中的全部文字内容，并简要描述图片主体与结构，输出为纯文本。"
    if not image_data:
        return _mock()

    text = llm_client.vlm(image_data, prompt, content_type)
    engine = "vlm"
    degraded = False

    if not text or len(text.strip()) < 10:
        ocr_text = llm_client.ocr(image_data)
        if ocr_text and len(ocr_text.strip()) > len((text or "").strip()):
            text = ocr_text
            engine = "ocr_fallback"
            degraded = True

    if not text:
        return _mock()

    llm_client.last_ocr_text = text
    return {"text": text.strip(), "engine": engine, "degraded": degraded}