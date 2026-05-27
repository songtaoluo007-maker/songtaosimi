from datetime import date

from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.trade import Trade
from backend.services.ocr_reconcile_service_v3 import (
    build_snapshot_diff,
    create_inferred_trades,
    get_ocr_sync_status,
)
from .conftest import TestingSessionLocal


def test_snapshot_diff_infers_buy_trade_and_skips_duplicate():
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选", latest_nav=2.0))
        db.add(Holding(
            fund_code="005827",
            shares=100,
            cost_price=1.8,
            cost_amount=180,
            current_nav=2.0,
            current_value=200,
            source="manual",
            is_active=True,
        ))
        db.commit()

        items = [{
            "fund_code": "005827",
            "fund_name": "易方达蓝筹精选",
            "shares": 120,
            "amount": 240,
            "cost_amount": 220,
        }]
        diff = build_snapshot_diff(db, items, trade_date="2026-05-27")

        assert diff["summary"]["inferred_trade_count"] == 1
        row = diff["diffs"][0]
        assert row["status"] == "increased"
        assert row["trade_type"] == "买入"
        assert row["inferred_shares"] == 20
        assert row["inferred_amount"] == 40

        created = create_inferred_trades(db, diff)
        db.commit()
        assert created["created_count"] == 1

        trade = db.query(Trade).filter(Trade.fund_code == "005827").one()
        assert trade.source == "ocr_diff"
        assert float(trade.shares) == 20

        duplicate_diff = build_snapshot_diff(db, items, trade_date="2026-05-27")
        assert duplicate_diff["diffs"][0]["duplicate_trade"] is True
        assert duplicate_diff["summary"]["duplicate_trade_count"] == 1
    finally:
        db.close()


def test_snapshot_diff_warns_missing_holdings_and_invalid_rows():
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="161725", fund_name="招商中证白酒", latest_nav=1.0))
        db.add(Holding(
            fund_code="161725",
            shares=300,
            cost_price=1,
            cost_amount=300,
            current_nav=1,
            current_value=300,
            source="manual",
            is_active=True,
        ))
        db.commit()

        diff = build_snapshot_diff(db, [{"fund_name": "缺代码基金", "shares": 10}], trade_date=date(2026, 5, 27))

        assert diff["summary"]["invalid_item_count"] == 1
        assert diff["summary"]["missing_holding_count"] == 1
        assert diff["missing_holdings"][0]["fund_code"] == "161725"
    finally:
        db.close()


def test_ocr_sync_status_due_when_active_holdings_have_no_ocr_sync():
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="000001", fund_name="测试基金", latest_nav=1.0))
        db.add(Holding(
            fund_code="000001",
            shares=100,
            cost_price=1,
            cost_amount=100,
            current_nav=1,
            current_value=100,
            source="manual",
            is_active=True,
        ))
        db.commit()

        status = get_ocr_sync_status(db)

        assert status["active_holding_count"] == 1
        assert status["due"] is True
        assert status["last_sync_at"] is None
    finally:
        db.close()
