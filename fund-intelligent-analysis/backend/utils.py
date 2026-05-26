"""
共享工具函数，由各 service 和 api 模块复用。
"""
import os
from datetime import date, datetime


def clear_proxy_env() -> None:
    for key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def money_to_yuan(value) -> float:
    """分转元"""
    return to_float(value) / 10000.0 if to_float(value) > 0 else 0.0


def today_str() -> str:
    return date.today().isoformat()


def now_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sanitize_text(text: str) -> str:
    """修复编码损坏的文本：移除 surrogate 字符，替换无法解码的字节"""
    if not text:
        return ""
    return text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
