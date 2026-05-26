from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text, func

from backend.database import Base


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(40), unique=True, nullable=False, index=True)
    password_hash = Column(String(240), nullable=False)
    display_name = Column(String(80), default="")
    role = Column(String(20), default="owner")
    is_active = Column(Boolean, default=True)
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # P1.3 用户画像（AI 个性化的输入）
    birth_year = Column(Integer, nullable=True)
    retirement_target_year = Column(Integer, nullable=True)
    investment_horizon_years = Column(Integer, nullable=True)        # 资金锁定期
    funds_purpose = Column(String(30), nullable=True)                # emergency/house_down/children_edu/retirement/long_term
    target_annual_return = Column(Numeric(5, 2), nullable=True)      # 目标年化 %
    max_acceptable_drawdown = Column(Numeric(5, 2), nullable=True)   # 可承受最大回撤 %
    risk_appetite = Column(String(20), nullable=True)                # conservative/balanced/aggressive
    monthly_disposable_income = Column(Numeric(12, 2), nullable=True)
    profile_updated_at = Column(DateTime, nullable=True)
    profile_notes = Column(Text, default="")

    def to_public_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "role": self.role or "owner",
            "is_active": bool(self.is_active),
            "last_login_at": self.last_login_at.isoformat(sep=" ") if self.last_login_at else None,
        }

    def to_profile_dict(self):
        return {
            "birth_year": self.birth_year,
            "retirement_target_year": self.retirement_target_year,
            "investment_horizon_years": self.investment_horizon_years,
            "funds_purpose": self.funds_purpose,
            "target_annual_return": float(self.target_annual_return) if self.target_annual_return is not None else None,
            "max_acceptable_drawdown": float(self.max_acceptable_drawdown) if self.max_acceptable_drawdown is not None else None,
            "risk_appetite": self.risk_appetite,
            "monthly_disposable_income": float(self.monthly_disposable_income) if self.monthly_disposable_income is not None else None,
            "profile_updated_at": str(self.profile_updated_at) if self.profile_updated_at else None,
            "profile_notes": self.profile_notes or "",
        }
