import difflib
import json
import logging

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models import UserLlmModel

logger = logging.getLogger(__name__)


class LLMTimeoutError(Exception):
    """大模型接口请求超时（read/connect timed out）。"""

    def __init__(self, message: str = "大模型接口请求超时，请重试，或更换模型API"):
        super().__init__(message)


class LLMError(Exception):
    """大模型接口调用失败（网络/HTTP等）。"""

    def __init__(self, message: str = "大模型接口调用失败，请重试，或更换模型API"):
        super().__init__(message)


def _prompt_summary(system: str, user: str) -> str:
    s = (system or "").replace("\n", " ").strip()
    u = (user or "").replace("\n", " ").strip()
    return f"sys[{s[:120]}] user[{u[:120]}]"


class LLMClient:
    similarity_threshold = 0.35

    def __init__(self, user_id: int | None = None):
        self.user_id = user_id
        self.last_prompt = None
        self.last_output = None
        self.last_similarity = None
        self.last_ocr_text = None
        self._model_cache: dict[str, dict | None] = {}

    # ---------- 用户默认模型解析：模拟模式 > 用户默认(对应类型) > 全局默认 ----------

    def _load_user_default(self, mtype: str) -> dict | None:
        if not self.user_id:
            return None
        key = f"u:{self.user_id}:{mtype}"
        if key in self._model_cache:
            return self._model_cache[key]
        db = SessionLocal()
        try:
            row = (
                db.query(UserLlmModel)
                .filter(UserLlmModel.user_id == self.user_id, UserLlmModel.type == mtype, UserLlmModel.is_default == True)  # noqa: E712
                .first()
            )
            if row is None:
                self._model_cache[key] = None
                return None
            from app.core.crypto import decrypt

            self._model_cache[key] = {
                "base_url": (row.base_url or "").strip(),
                "api_key": decrypt(row.api_key or "").strip(),
                "model_name": (row.model_name or "").strip(),
            }
            return self._model_cache[key]
        finally:
            db.close()

    def _resolve_text(self) -> dict:
        if settings.enable_ai_simulate:
            return {"mode": "simulate"}
        cfg = self._load_user_default("text") or {}
        if cfg.get("base_url") and cfg.get("api_key") and cfg.get("model_name"):
            return {
                "mode": "user",
                "base_url": cfg["base_url"],
                "api_key": cfg["api_key"],
                "model": cfg["model_name"],
            }
        return {
            "mode": "global",
            "base_url": settings.llm_base_url,
            "api_key": settings.llm_api_key,
            "model": settings.llm_model,
        }

    def _resolve_image(self) -> dict:
        if settings.enable_ai_simulate:
            return {"mode": "simulate"}
        cfg = self._load_user_default("image") or {}
        if cfg.get("base_url") and cfg.get("api_key") and cfg.get("model_name"):
            return {
                "mode": "user",
                "base_url": cfg["base_url"],
                "api_key": cfg["api_key"],
                "model": cfg["model_name"],
            }
        return {
            "mode": "global",
            "base_url": settings.vlm_base_url,
            "api_key": settings.vlm_api_key,
            "model": settings.vlm_model,
        }

    # ---------- 文本对话 ----------

    def _chat(self, base_url: str, api_key: str, model: str, system: str, user: str, timeout: int, model_params: dict | None = None) -> str | None:
        self.last_timeout = False
        self.last_error = None
        if not (base_url and api_key and model):
            return None
        messages = [{"role": "system", "content": system}]
        if user:
            messages.append({"role": "user", "content": user})
        self.last_prompt = messages
        body = {"model": model, "messages": messages, "temperature": 0.7, "stream": False}
        if model_params:
            for k, v in model_params.items():
                if k == "messages" or v is None:
                    continue
                body[k] = v
        try:
            resp = httpx.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
                timeout=timeout,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            self.last_output = text
            logger.info("llm chat ok, chars=%d", len(text or ""))
            return text
        except httpx.TimeoutException as exc:
            # 超时必须与正常失败区分，禁止静默走 mock 模板
            self.last_timeout = True
            logger.error("llm chat 请求超时: %s | prompt=%s", exc, _prompt_summary(system, user), exc_info=True)
            return None
        except Exception as exc:  # noqa: BLE001
            self.last_error = exc
            logger.error("llm chat 调用失败: %s | prompt=%s", exc, _prompt_summary(system, user), exc_info=True)
            return None

    def chat(self, system: str, user: str, model_params: dict | None = None) -> str | None:
        resolved = self._resolve_text()
        if resolved.get("mode") == "simulate":
            return None
        text = self._chat(resolved["base_url"], resolved["api_key"], resolved["model"], system, user, settings.llm_timeout, model_params)
        # 区分超时与普通失败：直接抛异常，禁止上层静默走 mock 模板
        if text is None:
            if self.last_timeout:
                raise LLMTimeoutError()
            if self.last_error is not None:
                raise LLMError()
        return text

    def test_chat(self, base_url: str, api_key: str, model: str) -> str | None:
        return self._chat(base_url, api_key, model, "你是连接测试助手，请只回复：连接成功。", "测试连接", settings.llm_timeout)

    # ---------- VLM 多模态（图片类型默认配置） ----------

    def vlm(self, image_b64: str, prompt: str, content_type: str = "image/png") -> str | None:
        resolved = self._resolve_image()
        if resolved.get("mode") == "simulate":
            return None
        base_url = resolved["base_url"]
        api_key = resolved["api_key"]
        model = resolved["model"]
        if not (base_url and api_key):
            return None
        if not model:
            return None
        data_url = f"data:{content_type};base64,{image_b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        self.last_prompt = messages
        try:
            resp = httpx.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.2, "stream": False},
                timeout=settings.llm_timeout,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            self.last_output = text
            return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("vlm failed: %s", exc)
            return None

    # ---------- OCR（全局配置，与用户 LLM 配置无关） ----------

    def ocr(self, image_b64: str) -> str:
        if settings.enable_ai_simulate:
            return ""
        if not (settings.ocr_secret_id and settings.ocr_secret_key):
            return ""
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.ocr.v20181119 import models, ocr_client

            cred = credential.Credential(settings.ocr_secret_id, settings.ocr_secret_key)
            hp = HttpProfile()
            hp.endpoint = "ocr.tencentcloudapi.com"
            cp = ClientProfile()
            cp.httpProfile = hp
            client = ocr_client.OcrClient(cred, settings.ocr_region, cp)
            req = models.GeneralBasicOCRRequest()
            req.ImageBase64 = image_b64
            resp = client.GeneralBasicOCR(req)
            text = "\n".join([t.DetectedText for t in resp.TextDetections])
            logger.info("ocr ok, chars=%d", len(text or ""))
            return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("ocr failed: %s", exc)
            return ""

    # ---------- AI 绘图（图片类型默认配置） ----------

    def generate_image(self, prompt: str) -> str | None:
        if settings.enable_ai_simulate:
            return None
        resolved = self._resolve_image()
        base_url = resolved["base_url"]
        api_key = resolved["api_key"]
        model = resolved["model"]
        if not (base_url and api_key and model):
            return None
        try:
            resp = httpx.post(
                f"{base_url.rstrip('/')}/images/generations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"},
                timeout=settings.image_timeout,
            )
            resp.raise_for_status()
            data = resp.json()["data"][0]
            raw = data.get("url") or data.get("b64_json")
            if not raw:
                return None
            if data.get("b64_json"):
                return f"data:image/png;base64,{data['b64_json']}"
            return raw
        except Exception as exc:  # noqa: BLE001
            logger.warning("image generate failed: %s", exc)
            return None

    def similarity(self, text_a: str, text_b: str) -> float:
        score = similarity(text_a, text_b)
        self.last_similarity = score
        return score


def _char_bigrams(text: str) -> set[str]:
    cleaned = "".join([c for c in text if not c.isspace()])
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def similarity(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    if text_a == text_b:
        return 1.0
    bigrams_a = _char_bigrams(text_a)
    bigrams_b = _char_bigrams(text_b)
    if not bigrams_a or not bigrams_b:
        return 0.0
    jaccard = len(bigrams_a & bigrams_b) / len(bigrams_a | bigrams_b)
    ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()
    return round(max(0.0, min(1.0, 0.75 * ratio + 0.25 * jaccard)), 4)


def safe_json(text: str | None) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:  # noqa: BLE001
                return None
        return None