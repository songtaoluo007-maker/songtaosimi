import os
from pathlib import Path
from pydantic_settings import BaseSettings

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'fund_quant.db'}"

    # AI配置
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 服务端口
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000

    # 行情采集
    MARKET_COLLECT_INTERVAL_MINUTES: int = 5
    FUND_ESTIMATE_INTERVAL_MINUTES: int = 30
    AI_ADVICE_HOUR: int = 14
    AI_ADVICE_MINUTE: int = 30
    AI_ADVICE_PRE_REFRESH: bool = True
    AI_NEWS_LOOKBACK_DAYS: int = 3

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(BASE_DIR / "data" / "logs")

    # OCR临时目录
    OCR_TEMP_DIR: str = str(BASE_DIR / "data" / "ocr_temp")

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
