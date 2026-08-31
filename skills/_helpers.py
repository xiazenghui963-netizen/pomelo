import json
import re


def safe_json(text: str | None) -> dict | list | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None


def split_list(text: str | None) -> list[str]:
    if not text:
        return []
    lines = [re.sub(r"^\d+[\.、\)\s]*|^[-*•\s]+", "", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


def wrap_prompt(materials_text: str | None) -> str:
    if not materials_text:
        return ""
    return f"\n\n以下为可参考的私有资料原文：\n{materials_text}\n请在不偏离主题的前提下自然融入参考信息。"