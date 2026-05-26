import sys
import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings

# 项目根目录 — 打包后使用 exe 所在目录的上级（与 dist/../ 即项目根一致）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
_PLACEHOLDER_API_KEY = "your_deepseek_api_key_here"


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'fund_quant.db'}"

    # AI配置
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"

    # 服务端口
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    # 本地账号与会话
    APP_SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # 行情采集
    MARKET_COLLECT_INTERVAL_MINUTES: int = 5
    FUND_ESTIMATE_INTERVAL_MINUTES: int = 30
    AI_ADVICE_HOUR: int = 14
    AI_ADVICE_MINUTE: int = 30
    AI_ADVICE_PRE_REFRESH: bool = True
    AI_NEWS_LOOKBACK_DAYS: int = 3
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 8192

    # 飞书通知
    FEISHU_WEBHOOK_URL: str = ""

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(BASE_DIR / "data" / "logs")

    # OCR临时目录
    OCR_TEMP_DIR: str = str(BASE_DIR / "data" / "ocr_temp")

    @field_validator("LOG_LEVEL")
    @classmethod
    def _check_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in _VALID_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL 必须为 {'/'.join(sorted(_VALID_LOG_LEVELS))}，当前值: {v}")
        return v

    @field_validator("DEEPSEEK_API_KEY")
    @classmethod
    def _check_api_key(cls, v: str) -> str:
        if v.startswith("ENCRYPTED:"):
            return v
        if v == _PLACEHOLDER_API_KEY:
            raise ValueError(
                f"DEEPSEEK_API_KEY 仍是占位值 '{_PLACEHOLDER_API_KEY}'，请在 .env 中配置真实 Key"
            )
        return v

    @field_validator("APP_SECRET_KEY")
    @classmethod
    def _check_app_secret(cls, v: str) -> str:
        if v and len(v) < 16:
            raise ValueError("APP_SECRET_KEY 长度至少 16 位")
        return v

    @property
    def decrypted_api_key(self) -> str:
        from backend.crypto import decrypt_value
        return decrypt_value(self.DEEPSEEK_API_KEY)

    @property
    def has_api_key(self) -> bool:
        key = self.decrypted_api_key if self.DEEPSEEK_API_KEY.startswith("ENCRYPTED:") else self.DEEPSEEK_API_KEY
        return bool(key and key != _PLACEHOLDER_API_KEY)

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# 确保必要目录存在
os.makedirs(settings.LOG_DIR, exist_ok=True)
os.makedirs(settings.OCR_TEMP_DIR, exist_ok=True)
os.makedirs(str(BASE_DIR / "data"), exist_ok=True)
