from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func
from sqlalchemy.orm import relationship
from backend.database import Base


class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(6), unique=True, nullable=False, index=True)
    fund_name = Column(String(100), nullable=False)
    fund_type = Column(String(20), default="混合型")  # 股票型/混合型/债券型/指数型/QDII/FOF
    benchmark = Column(String(200), default="")
    risk_level = Column(String(10), default="")  # R1-R5
    manager = Column(String(50), default="")
    company = Column(String(50), default="")
    establish_date = Column(Date, nullable=True)
    latest_nav = Column(Numeric(8, 4), default=0)  # 最新净值
    latest_nav_date = Column(Date, nullable=True)
    acc_nav = Column(Numeric(10, 4), default=0)  # 累计净值
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    holdings = relationship("Holding", back_populates="fund", lazy="dynamic")
    trades = relationship("Trade", back_populates="fund", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "fund_type": self.fund_type,
            "benchmark": self.benchmark,
            "risk_level": self.risk_level,
            "manager": self.manager,
            "company": self.company,
            "establish_date": str(self.establish_date) if self.establish_date else None,
            "latest_nav": float(self.latest_nav) if self.latest_nav else 0,
            "latest_nav_date": str(self.latest_nav_date) if self.latest_nav_date else None,
            "acc_nav": float(self.acc_nav) if self.acc_nav else 0,
        }
