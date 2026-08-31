skill_meta = {
    "name": "skill_ocr_extract",
    "description": "图片 OCR 提取文本；图片以 base64 传入，仅在内存中识别，不落盘、不存云端",
    "access_level": 0,
    "cost_point": 0,
    "parameters": [
        {"name": "image_data", "type": "string", "required": True, "label": "图片 base64"},
        {"name": "content_type", "type": "string", "required": False, "label": "图片类型"},
    ],
}


def execute(params: dict, llm_client) -> dict:  # noqa: ANN001
    image_data = params.get("image_data", "")
    text = llm_client.ocr(image_data) if image_data else ""
    llm_client.last_ocr_text = text
    return {"text": text, "chars": len(text)}