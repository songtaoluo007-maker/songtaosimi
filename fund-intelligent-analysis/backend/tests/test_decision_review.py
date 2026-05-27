from datetime import date, time, timedelta

from backend.models.ai_advice import AiAdvice
from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.trade import Trade
from backend.services.decision_review_service_v3 import (
    compute_behavior_bias,
    materialize_decisions_from_trades,
)
from .conftest import TestingSessionLocal


def test_materialize_decisions_uses_loaded_advice_and_computes_bias():
    db = TestingSessionLocal()
    trade_day = date.today() - timedelta(days=1)
    month = trade_day.strftime("%Y-%m")
    try:
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选", fund_type="混合型"))
        db.add(Holding(
            fund_code="005827",
            shares=1000,
            cost_price=1,
            cost_amount=1000,
            current_nav=1.2,
            current_value=1200,
            is_active=True,
        ))
        db.add(AiAdvice(
            advice_date=trade_day,
            advice_time=time(14, 30),
            actions=[{"fund_code": "005827", "action": "add"}],
            market_view="bullish",
        ))
        db.add(Trade(
            fund_code="005827",
            trade_type="买入",
            shares=100,
            nav_price=1.1,
            amount=110,
            trade_date=trade_day,
        ))
        db.commit()

        assert materialize_decisions_from_trades(db, since_days=7) == 1
        assert materialize_decisions_from_trades(db, since_days=7) == 0

        snap = compute_behavior_bias(db, month=month)
        assert snap["totals"]["total_decisions"] == 1
        assert snap["totals"]["follow_count"] == 1
        assert snap["follow_advice_rate"] == 100
        assert snap["frequent_trade_score"] == 25
    finally:
        db.close()
