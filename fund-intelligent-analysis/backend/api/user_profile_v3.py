"""
用户画像 API — P1.3
"""
from datetime import datetime
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import UserAccount

router = APIRouter(prefix="/api/user/profile", tags=["用户画像"])


def _get_owner(db: Session) -> UserAccount | None:
    """单用户系统：取 owner 角色账号"""
    return db.query(UserAccount).filter(UserAccount.role == "owner").first()


@router.get("")
def get_profile(db: Session = Depends(get_db)):
    user = _get_owner(db)
    if not user:
        raise HTTPException(status_code=404, detail="未找到用户")
    return user.to_profile_dict()


PROFILE_FIELDS = {
    "birth_year", "retirement_target_year", "investment_horizon_years",
    "funds_purpose", "target_annual_return", "max_acceptable_drawdown",
    "risk_appetite", "monthly_disposable_income", "profile_notes",
}

ALLOWED_PURPOSE = {"emergency", "house_down", "children_edu", "retirement", "long_term"}
ALLOWED_RISK = {"conservative", "balanced", "aggressive"}


@router.put("")
def put_profile(payload: dict = Body(...), db: Session = Depends(get_db)):
    user = _get_owner(db)
    if not user:
        raise HTTPException(status_code=404, detail="未找到用户")

    if payload.get("funds_purpose") and payload["funds_purpose"] not in ALLOWED_PURPOSE:
        raise HTTPException(status_code=400, detail="funds_purpose 取值无效")
    if payload.get("risk_appetite") and payload["risk_appetite"] not in ALLOWED_RISK:
        raise HTTPException(status_code=400, detail="risk_appetite 取值无效")

    for k, v in payload.items():
        if k in PROFILE_FIELDS:
            setattr(user, k, v)
    user.profile_updated_at = datetime.now()
    db.commit()
    db.refresh(user)
    return user.to_profile_dict()


@router.post("/recommend-allocation")
def recommend_allocation(db: Session = Depends(get_db)):
    """根据画像生成推荐资产配置（极简规则引擎，作为新用户的起点参考）"""
    user = _get_owner(db)
    if not user:
        raise HTTPException(status_code=404, detail="未找到用户")
    return _recommend_from_profile(user)


def _recommend_from_profile(user: UserAccount) -> dict:
    """极简规则：基于年龄 + 风险偏好生成"目标资产配置建议"

    经典法则：股票占比 = 100 - 年龄；再根据风险偏好调整
    """
    age = None
    if user.birth_year:
        from datetime import date
        age = date.today().year - int(user.birth_year)

    purpose = user.funds_purpose or "long_term"
    appetite = user.risk_appetite or "balanced"

    # 基础股票占比
    if age:
        base_equity = max(20, min(85, 100 - age))
    else:
        base_equity = 60

    # 资金性质调整
    if purpose == "emergency":
        base_equity = min(base_equity, 10)
    elif purpose == "house_down":
        base_equity = min(base_equity, 30)
    elif purpose == "retirement":
        base_equity = min(base_equity, 70)

    # 风险偏好调整
    if appetite == "conservative":
        base_equity = max(0, base_equity - 20)
    elif appetite == "aggressive":
        base_equity = min(95, base_equity + 15)

    # 拆分到资产大类
    equity_a = round(base_equity * 0.6, 1)
    equity_hk_us = round(base_equity * 0.4, 1)
    bond = round((100 - base_equity) * 0.7, 1)
    gold = round((100 - base_equity) * 0.2, 1)
    cash = round((100 - base_equity) * 0.1, 1)

    return {
        "age": age,
        "purpose": purpose,
        "risk_appetite": appetite,
        "recommendation": [
            {"asset_class": "equity_a", "target_pct": equity_a, "tolerance_pct": 5, "notes": "A 股权益"},
            {"asset_class": "equity_us", "target_pct": equity_hk_us, "tolerance_pct": 5, "notes": "海外/港股"},
            {"asset_class": "bond", "target_pct": bond, "tolerance_pct": 5, "notes": "债券"},
            {"asset_class": "gold", "target_pct": gold, "tolerance_pct": 3, "notes": "贵金属对冲"},
            {"asset_class": "cash", "target_pct": cash, "tolerance_pct": 2, "notes": "现金 buffer"},
        ],
        "reasoning": (
            f"基于年龄 {age or '未填'} + 资金性质 '{purpose}' + 风险偏好 '{appetite}'，"
            f"建议权益占比 {base_equity}%。该比例为参考起点，请按个人情况微调。"
        ),
    }
