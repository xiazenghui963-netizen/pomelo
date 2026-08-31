"""api_key 等敏感字段的加密/解密工具。

使用 Fernet 对称加密，密钥由项目 SECRET_KEY 派生（PBKDF2）。改 SECRET_KEY 后已存密文无法解密，属预期。
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = base64.urlsafe_b64encode(
            hashlib.pbkdf2_hmac("sha256", settings.secret_key.encode("utf-8"), b"pomelo-ai-llm-config", 100_000, dklen=32)
        )
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):  # noqa: BLE001
        return ""


def mask_secret(value: str) -> str:
    """脱敏展示：只保留前4后4，中间用 * 代替。"""
    if not value:
        return ""
    if len(value) <= 8:
        return value[:2] + "****" + value[-2:]
    return value[:4] + "****" + value[-4:]