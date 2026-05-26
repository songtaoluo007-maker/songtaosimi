from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from backend.config import BASE_DIR, settings
from backend.models.user import UserAccount


PBKDF2_ITERATIONS = 260_000
TOKEN_VERSION = "v1"
REFRESH_TOKEN_DAYS = 30
RECOVERY_KEY_FILE = Path(BASE_DIR) / "data" / "recovery_key.txt"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


_secret_key_cache: str | None = None

def get_secret_key() -> str:
    global _secret_key_cache
    if _secret_key_cache:
        return _secret_key_cache

    if settings.APP_SECRET_KEY:
        _secret_key_cache = settings.APP_SECRET_KEY
        return _secret_key_cache

    secret_file = Path(BASE_DIR) / "data" / "app_secret.key"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        secret = secret_file.read_text(encoding="utf-8").strip()
        if secret:
            _secret_key_cache = secret
            return _secret_key_cache

    secret = secrets.token_urlsafe(48)
    secret_file.write_text(secret, encoding="utf-8")
    _secret_key_cache = secret
    return _secret_key_cache


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(user: UserAccount) -> dict[str, Any]:
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "ver": TOKEN_VERSION,
        "sub": str(user.id),
        "username": user.username,
        "role": user.role or "owner",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_text = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signature = _b64url(
        hmac.new(get_secret_key().encode("utf-8"), payload_text.encode("ascii"), hashlib.sha256).digest()
    )
    return {
        "access_token": f"{payload_text}.{signature}",
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(sep=" "),
        "user": user.to_public_dict(),
    }


def create_refresh_token(user: UserAccount) -> str:
    """生成长期刷新令牌（30天有效期），用于记住我自动续期"""
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(days=REFRESH_TOKEN_DAYS)
    payload = {
        "ver": TOKEN_VERSION,
        "sub": str(user.id),
        "username": user.username,
        "purpose": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_text = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signature = _b64url(
        hmac.new(get_secret_key().encode("utf-8"), payload_text.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{payload_text}.{signature}"


def decode_refresh_token(token: str) -> dict[str, Any]:
    """解码刷新令牌，不检查过期（由调用方决定）"""
    try:
        payload_text, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("invalid refresh token format") from exc
    expected = _b64url(
        hmac.new(get_secret_key().encode("utf-8"), payload_text.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid refresh token signature")
    payload = json.loads(_b64url_decode(payload_text).decode("utf-8"))
    if payload.get("ver") != TOKEN_VERSION or payload.get("purpose") != "refresh":
        raise ValueError("invalid refresh token")
    return payload


def get_or_create_recovery_key() -> str:
    """获取或创建密码恢复密钥，存储在 data/recovery_key.txt"""
    if RECOVERY_KEY_FILE.exists():
        key = RECOVERY_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    key = secrets.token_hex(8)
    RECOVERY_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECOVERY_KEY_FILE.write_text(key, encoding="utf-8")
    return key


def verify_recovery_key(key: str) -> bool:
    """验证恢复密钥是否正确"""
    try:
        return hmac.compare_digest(key.strip(), get_or_create_recovery_key())
    except Exception:
        return False


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload_text, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("invalid token format") from exc

    expected = _b64url(
        hmac.new(get_secret_key().encode("utf-8"), payload_text.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid token signature")

    payload = json.loads(_b64url_decode(payload_text).decode("utf-8"))
    if payload.get("ver") != TOKEN_VERSION:
        raise ValueError("invalid token version")
    if int(payload.get("exp", 0)) < int(datetime.now(tz=timezone.utc).timestamp()):
        raise ValueError("token expired")
    return payload


def user_count(db: Session) -> int:
    return int(db.query(func.count(UserAccount.id)).scalar() or 0)


def get_user_by_username(db: Session, username: str) -> UserAccount | None:
    return (
        db.query(UserAccount)
        .options(load_only(
            UserAccount.id,
            UserAccount.username,
            UserAccount.password_hash,
            UserAccount.display_name,
            UserAccount.role,
            UserAccount.is_active,
            UserAccount.failed_login_count,
            UserAccount.locked_until,
            UserAccount.last_login_at,
            UserAccount.password_changed_at,
        ))
        .filter(UserAccount.username == username.strip())
        .first()
    )


def get_user_from_token(db: Session, token: str) -> UserAccount:
    payload = decode_access_token(token)
    user = (
        db.query(UserAccount)
        .options(load_only(
            UserAccount.id,
            UserAccount.username,
            UserAccount.display_name,
            UserAccount.role,
            UserAccount.is_active,
            UserAccount.last_login_at,
        ))
        .filter(UserAccount.id == int(payload["sub"]))
        .first()
    )
    if not user or not user.is_active:
        raise ValueError("user inactive or missing")
    return user


def password_strength_error(password: str) -> str:
    if len(password) < 8:
        return "密码至少需要 8 位"
    if password.strip() != password:
        return "密码首尾不能包含空格"
    if password.isdigit() or password.isalpha():
        return "密码不能只包含数字或字母"
    return ""
