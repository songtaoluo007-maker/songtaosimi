from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import UserAccount
from backend.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_or_create_recovery_key,
    get_user_by_username,
    get_user_from_token,
    hash_password,
    password_strength_error,
    user_count,
    verify_password,
    verify_recovery_key,
)


router = APIRouter(prefix="/api/auth", tags=["本地账号"])


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="基金账户所有者", max_length=80)


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class RecoverRequest(BaseModel):
    recovery_key: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return authorization.split(" ", 1)[1].strip()


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserAccount:
    try:
        return get_user_from_token(db, _bearer_token(authorization))
    except Exception:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


@router.get("/bootstrap-status")
def bootstrap_status(db: Session = Depends(get_db)):
    return {"has_user": user_count(db) > 0}


@router.post("/setup")
def setup_owner(data: SetupRequest, db: Session = Depends(get_db)):
    if user_count(db) > 0:
        raise HTTPException(status_code=409, detail="系统已完成账号初始化")

    username = data.username.strip()
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="用户名只能包含字母、数字、下划线或短横线")

    strength_error = password_strength_error(data.password)
    if strength_error:
        raise HTTPException(status_code=400, detail=strength_error)

    user = UserAccount(
        username=username,
        password_hash=hash_password(data.password),
        display_name=data.display_name.strip() or username,
        role="owner",
        password_changed_at=datetime.now(tz=timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    result = create_access_token(user)
    result["recovery_key"] = get_or_create_recovery_key()
    return result


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(db, data.username)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码不正确")

    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=423, detail=f"登录失败次数过多，请在 {user.locked_until:%H:%M:%S} 后重试")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_count = int(user.failed_login_count or 0) + 1
        if user.failed_login_count >= 5:
            user.locked_until = now + timedelta(minutes=10)
            user.failed_login_count = 0
        db.commit()
        raise HTTPException(status_code=401, detail="用户名或密码不正确")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    db.refresh(user)
    result = create_access_token(user)
    if data.remember_me:
        result["refresh_token"] = create_refresh_token(user)
    return result


@router.post("/refresh")
def refresh_token(refresh_token: str = Header(alias="X-Refresh-Token"), db: Session = Depends(get_db)):
    """用长期刷新令牌换取新的访问令牌"""
    try:
        payload = decode_refresh_token(refresh_token)
        user = db.query(UserAccount).filter(UserAccount.id == int(payload["sub"])).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户无效或已被禁用")
        return create_access_token(user)
    except ValueError:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")


@router.post("/recover")
def recover_password(data: RecoverRequest, db: Session = Depends(get_db)):
    """使用恢复密钥重置密码"""
    if not verify_recovery_key(data.recovery_key):
        raise HTTPException(status_code=400, detail="恢复密钥不正确")

    strength_error = password_strength_error(data.new_password)
    if strength_error:
        raise HTTPException(status_code=400, detail=strength_error)

    user = db.query(UserAccount).filter(UserAccount.role == "owner").first()
    if not user:
        raise HTTPException(status_code=404, detail="未找到管理员账号")
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.now(tz=timezone.utc)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return {"message": "密码已重置，请使用新密码登录"}


@router.get("/recovery-key-status")
def recovery_key_status():
    """检查是否有恢复密钥文件（仅告知存在性，不返回密钥）"""
    from backend.services.auth_service import RECOVERY_KEY_FILE
    return {"exists": RECOVERY_KEY_FILE.exists()}


@router.get("/me")
def me(user: UserAccount = Depends(current_user)):
    return user.to_public_dict()


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    user: UserAccount = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")

    strength_error = password_strength_error(data.new_password)
    if strength_error:
        raise HTTPException(status_code=400, detail=strength_error)

    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.now(tz=timezone.utc)
    db.commit()
    return {"message": "密码已更新，请使用新密码重新登录"}
