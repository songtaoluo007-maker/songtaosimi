"""
TTL 内存缓存层。减少重复的外部 API 调用和数据库查询。
支持持久化到磁盘，重启后恢复热缓存。
"""
import atexit
import os
import sys
import time
import json
from functools import wraps
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Callable

from loguru import logger

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

CACHE_FILE = BASE_DIR / "data" / "cache" / "cache.json"
SAVE_INTERVAL = 300  # 每 5 分钟自动保存


_cache: dict[str, tuple[float, Any]] = {}
_lock = Lock()
_dirty = True


def _load_cache():
    """启动时从磁盘恢复缓存（仅恢复仍有效的条目）。"""
    global _dirty
    if not CACHE_FILE.exists():
        return
    try:
        raw = CACHE_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        now = time.time()
        with _lock:
            count = 0
            for key, (expires, value) in data.items():
                if now < expires:
                    _cache[key] = (expires, value)
                    count += 1
        _dirty = False
        if count:
            logger.info(f"缓存热启动: 恢复 {count} 条有效缓存")
    except Exception as e:
        logger.debug(f"缓存恢复失败（首次启动正常）: {e}")


def _save_cache():
    """持久化当前缓存到磁盘。"""
    global _dirty
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            payload = {k: list(v) for k, v in _cache.items()}
        CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        _dirty = False
    except Exception as e:
        logger.debug(f"缓存持久化失败: {e}")


def _periodic_save():
    """后台线程定期保存缓存。"""
    global _dirty
    while True:
        time.sleep(SAVE_INTERVAL)
        if _dirty:
            _save_cache()


def _mark_dirty():
    global _dirty
    _dirty = True


# 启动时加载
_load_cache()
# 后台定期保存
_save_thread = Thread(target=_periodic_save, daemon=True)
_save_thread.start()
# 进程退出时保存
atexit.register(_save_cache)


def cached(ttl_seconds: int):
    """装饰器：缓存函数返回值，TTL 过期后重新调用。"""
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"{fn.__name__}:{args}:{sorted(kwargs.items())}"
            now = time.time()
            with _lock:
                if key in _cache:
                    expires, value = _cache[key]
                    if now < expires:
                        return value
            result = fn(*args, **kwargs)
            with _lock:
                _cache[key] = (now + ttl_seconds, result)
                _mark_dirty()
            return result
        return wrapper
    return decorator


def cached_response(ttl_seconds: int):
    """FastAPI 端点装饰器：按请求路径+参数缓存整个响应。"""
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"api:{fn.__name__}:{json.dumps(kwargs, sort_keys=True, default=str)}"
            now = time.time()
            with _lock:
                if key in _cache:
                    expires, value = _cache[key]
                    if now < expires:
                        return value
            result = fn(*args, **kwargs)
            with _lock:
                _cache[key] = (now + ttl_seconds, result)
                _mark_dirty()
            return result
        return wrapper
    return decorator


def invalidate(prefix: str = ""):
    """清除匹配前缀的缓存条目。"""
    with _lock:
        if prefix:
            keys = [k for k in _cache if k.startswith(prefix)]
            for k in keys:
                del _cache[k]
        else:
            _cache.clear()
    _mark_dirty()


def cache_stats() -> dict:
    with _lock:
        return {
            "entries": len(_cache),
            "keys": list(_cache.keys())[:20],
        }


def save_now():
    """手动触发立即保存。"""
    _save_cache()


def shutdown_cache():
    """关闭时保存缓存。"""
    _save_cache()
    logger.debug("缓存已持久化")
