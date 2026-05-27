import json
from datetime import date, datetime, timedelta

from backend.models.fund import Fund
from backend.models.fund_fee import FundFeeSchedule
from backend.models.holding import Holding
from backend.services.senior_toolbox_service_v3 import (
    _is_same_holiday_block,
    fee_health_summary,
    holding_milestones,
    switch_savings,
)
from .conftest import TestingSessionLocal


def _add_holding(db, code="005827", company="易方达基金", days=5, value=10000):
    db.add(Fund(
        fund_code=code,
        fund_name=f"测试基金{code}",
        company=company,
        latest_nav=1,
    ))
    db.add(Holding(
        fund_code=code,
        shares=value,
        cost_price=1,
        cost_amount=value,
        current_nav=1,
        current_value=value,
        source="manual",
        is_active=True,
        created_at=datetime.now() - timedelta(days=days),
    ))


def _add_fee(db, code="005827", redemption=None, mgmt=0.015, custody=0.0025, sales=0):
    db.add(FundFeeSchedule(
        fund_code=code,
        purchase_fee_rate=0.015,
        purchase_fee_discount=0.1,
        redemption_fee_schedule=json.dumps(redemption or [
            {"min_days": 0, "max_days": 6, "rate": 0.015},
            {"min_days": 7, "max_days": 29, "rate": 0.005},
            {"min_days": 30, "max_days": 99999, "rate": 0},
        ], ensure_ascii=False),
        management_fee_rate=mgmt,
        custody_fee_rate=custody,
        sales_service_fee_rate=sales,
    ))


def test_holding_milestones_calculates_fee_drop_savings():
    db = TestingSessionLocal()
    try:
        _add_holding(db, days=5, value=10000)
        _add_fee(db)
        db.commit()

        result = holding_milestones(db)
        row = result["items"][0]

        assert result["imminent"]
        assert row["holding_days"] == 5
        assert row["days_to_fee_drop"] == 2
        assert row["current_redemption_rate"] == 0.015
        assert row["next_fee_rate"] == 0.005
        assert row["savings_at_fee_drop"] == 100
    finally:
        db.close()


def test_switch_savings_calculates_fee_delta_and_company_warning():
    db = TestingSessionLocal()
    try:
        _add_holding(db, code="005827", company="易方达基金", days=10, value=10000)
        db.add(Fund(fund_code="110011", fund_name="目标基金", company="另一家公司"))
        _add_fee(db, code="005827")
        _add_fee(db, code="110011")
        db.commit()

        result = switch_savings(db, "005827", "110011", amount=10000, convert_fee_rate=0.005)

        assert result["same_company"] is False
        assert "公司不同" in result["company_warning"]
        assert result["from"]["redemption_fee"] == 50
        assert result["to"]["purchase_fee"] == 15
        assert result["direct_total_fee"] == 65
        assert result["convert_fee"] == 50
        assert result["savings"] == 15
    finally:
        db.close()


def test_fee_health_summary_marks_high_fee_and_missing_configs():
    db = TestingSessionLocal()
    try:
        _add_holding(db, code="005827", value=10000)
        _add_holding(db, code="161725", company="招商基金", value=5000)
        _add_fee(db, code="005827", mgmt=0.02, custody=0.003, sales=0)
        db.commit()

        result = fee_health_summary(db)

        assert result["high_fee_funds"] == ["005827"]
        assert result["missing_fee_data"] == ["161725"]
        assert result["items"][0]["annual_cost"] == 230
    finally:
        db.close()


def test_holiday_block_bridges_weekend_gap():
    assert _is_same_holiday_block(date(2026, 5, 1), date(2026, 5, 4)) is True
    assert _is_same_holiday_block(date(2026, 5, 1), date(2026, 5, 5)) is False
