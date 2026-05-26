"""
敏感配置加解密模块。
使用 Fernet 对称加密 + keyring 存储主密钥。
"""
import base64
import os
import sys
from pathlib import Path

from loguru import logger

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

KEY_FILE = BASE_DIR / "data" / ".fernet_key"
APP_NAME = "FundAI"


def _get_or_create_key() -> bytes:
    """从 keyring 获取主密钥，或新建后存入 keyring。优先从本地文件加载备份。"""
    try:
        import keyring

        key_b64 = keyring.get_password(APP_NAME, "fernet_key")
        if key_b64:
            return base64.urlsafe_b64decode(key_b64)
    except Exception:
        logger.debug("keyring 不可用，回退到本地密钥文件")

    # 回退：本地文件
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    # 新生成并存入 keyring
    key = os.urandom(32)
    key_b64 = base64.urlsafe_b64encode(key).decode()
    try:
        import keyring

        keyring.set_password(APP_NAME, "fernet_key", key_b64)
    except Exception:
        pass
    # 同时写入本地备份
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key)
    return key


def encrypt_value(plain_text: str) -> str:
    """加密纯文本，返回 ENCRYPTED: 前缀的密文。"""
    from cryptography.fernet import Fernet

    key = _get_or_create_key()
    f = Fernet(base64.urlsafe_b64encode(key))
    token = f.encrypt(plain_text.encode("utf-8"))
    return f"ENCRYPTED:{base64.urlsafe_b64encode(token).decode()}"


def decrypt_value(maybe_encrypted: str) -> str:
    """解密以 ENCRYPTED: 开头的密文，否则原样返回。"""
    if not maybe_encrypted or not maybe_encrypted.startswith("ENCRYPTED:"):
        return maybe_encrypted

    from cryptography.fernet import Fernet

    try:
        key = _get_or_create_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        token = base64.urlsafe_b64decode(maybe_encrypted[len("ENCRYPTED:"):].encode())
        return f.decrypt(token).decode("utf-8")
    except Exception as e:
        logger.warning(f"配置解密失败，回退到原始值: {e}")
        return maybe_encrypted


def reencrypt_if_needed():
    """启动时检查是否需要更新加密（密钥轮换或首次加密）。"""
    from backend.config import settings

    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return

    raw = env_file.read_text(encoding="utf-8")
    if "DEEPSEEK_API_KEY" not in raw:
        return

    # 检查是否已有加密值
    for line in raw.splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            # 如果之前被加密过但现在被手动恢复了，跳过自动加密
            if val and val.startswith("ENCRYPTED:"):
                # 已有加密值，检查是否需要轮换密钥
                pass
            elif val and val != "your_deepseek_api_key_here":
                # 明文 Key：保留明文（EXE 兼容），不自动加密
                pass
            break
