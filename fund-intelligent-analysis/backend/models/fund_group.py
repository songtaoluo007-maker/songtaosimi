from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from backend.database import Base


class FundGroup(Base):
    __tablename__ = "fund_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False, unique=True)
    description = Column(String(300), default="")
    color = Column(String(20), default="#2f6fef")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "color": self.color or "#2f6fef",
            "is_active": self.is_active,
        }


class FundGroupMember(Base):
    __tablename__ = "fund_group_members"
    __table_args__ = (UniqueConstraint("group_id", "fund_code", name="uq_group_fund"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("fund_groups.id"), nullable=False, index=True)
    fund_code = Column(String(6), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "fund_code": self.fund_code,
        }
