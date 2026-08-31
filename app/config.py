from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "青柚AI"
    debug: bool = True
    secret_key: str = "dev-secret-change-me-please-set-a-long-random-key-0123456789"
    token_expire_days: int = 7
    database_url: str = "sqlite:///./pomelo.db"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: int = 90

    # 模拟模式：最高优先级。开启后忽略用户配置与全局默认，所有大模型调用返回模拟数据（skill 走 mock 分支）
    enable_ai_simulate: bool = False

    vlm_base_url: str = ""
    vlm_api_key: str = ""
    vlm_model: str = ""

    ocr_secret_id: str = ""
    ocr_secret_key: str = ""
    ocr_region: str = "ap-beijing"

    # AI 绘图（OpenAI 兼容 images API）：直接使用第三方返回的图片 url，本服务不下载、不存储图片
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""
    image_timeout: int = 120

    # 上传截图仅在内存中暂存用于 OCR/VLM 识别，处理完成立即丢弃；该值是最长保留秒数的兜底
    session_image_ttl: int = 900

    initial_points: int = 100
    free_daily_points: int = 20
    member_daily_points: int = 50
    similarity_threshold: float = 0.35
    material_max_select: int = 3
    material_max_chars: int = 2000
    upload_max_mb: int = 15

    task_workers: int = 2
    rate_limit_requests: int = 20
    rate_limit_window: int = 60

    admin_username: str = "admin"
    admin_password: str = "admin123456"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()