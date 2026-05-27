from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.trade import Trade


SHARE_EPSILON = 0.01
OCR_TRADE_SOURCE = "ocr_diff"


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _round_money(value: Any) -> float:
    return round(_f(value), 2)


def _round_share(value: Any) -> float:
    return round(_f(value), 2)


def _parse_day(value: Any | None) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return date.today()
    return date.today()


def _parse_datetime(value: Any | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value[:19], fmt)
                return parsed
            except ValueError:
                continue
    return None


def _normalize_snapshot_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deduplicate OCR rows by fund code, keeping the row with the largest market value."""
    by_code: dict[str, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []

    for raw in items:
        code = str(raw.get("fund_code") or "").strip()
        if not code:
            invalid.append({
                "fund_name": raw.get("fund_name") or "",
                "reason": "缺少基金代码，无法参与持仓差异对账",
            })
            continue

        item = {
            "fund_code": code,
            "fund_name": str(raw.get("fund_name") or "").strip(),
            "shares": _round_share(raw.get("shares")),
            "amount": _round_money(raw.get("amount")),
            "cost_amount": _round_money(raw.get("cost_amount")),
            "source": raw.get("source") or "ocr",
        }
        existing = by_code.get(code)
        if not existing or item["amount"] >= existing["amount"]:
            if existing:
                item["warnings"] = ["同一基金出现多条 OCR 结果，已保留市值较大的记录"]
            by_code[code] = item

    return list(by_code.values()), invalid


def _nav_for_snapshot(
    item: dict[str, Any],
    holding: Holding | None,
    fund: Fund | None,
) -> float:
    nav_candidates = [
        getattr(fund, "latest_nav", 0) if fund else 0,
        item["amount"] / item["shares"] if item["shares"] > 0 and item["amount"] > 0 else 0,
        getattr(holding, "current_nav", 0) if holding else 0,
        (float(holding.current_value or 0) / float(holding.shares or 0))
        if holding and float(holding.shares or 0) > 0 and float(holding.current_value or 0) > 0
        else 0,
    ]
    return round(next((_f(nav) for nav in nav_candidates if _f(nav) > 0), 0), 4)


def get_ocr_sync_status(db: Session, interval_days: int = 7) -> dict[str, Any]:
    """Return whether the user should refresh holdings from an OCR snapshot."""
    active_count = db.query(Holding).filter(Holding.is_active == True).count()
    last_holding_sync = (
        db.query(func.max(Holding.updated_at))
        .filter(Holding.source.like("ocr%"))
        .scalar()
    )
    last_trade_sync = (
        db.query(func.max(Trade.created_at))
        .filter(Trade.source.in_(("ocr", OCR_TRADE_SOURCE)))
        .scalar()
    )

    candidates = [_parse_datetime(last_holding_sync), _parse_datetime(last_trade_sync)]
    last_sync_at = max((dt for dt in candidates if dt), default=None)
    today = date.today()
    due_day = last_sync_at.date() + timedelta(days=interval_days) if last_sync_at else today
    days_since = (today - last_sync_at.date()).days if last_sync_at else None
    due = active_count > 0 and (last_sync_at is None or days_since is None or days_since >= interval_days)

    return {
        "active_holding_count": active_count,
        "last_sync_at": last_sync_at.isoformat(sep=" ") if last_sync_at else None,
        "days_since_last_sync": days_since,
        "interval_days": interval_days,
        "next_due_date": due_day.isoformat(),
        "due": due,
        "message": (
            "尚未通过 OCR 同步过持仓，请导入最新截图"
            if last_sync_at is None and active_count > 0
            else f"距上次 OCR 同步已 {days_since} 天，请更新持仓截图"
            if due
            else "OCR 持仓同步仍在有效期内"
        ),
    }


def build_snapshot_diff(
    db: Session,
    items: list[dict[str, Any]],
    trade_date: str | date | None = None,
) -> dict[str, Any]:
    """Compare current active holdings with a new OCR holdings snapshot."""
    as_of = _parse_day(trade_date)
    normalized, invalid_items = _normalize_snapshot_items(items)
    codes = [item["fund_code"] for item in normalized]

    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    holdings_by_code = {h.fund_code: h for h in holdings}

    funds_by_code = {
        fund.fund_code: fund
        for fund in db.query(Fund).filter(Fund.fund_code.in_(codes)).all()
    } if codes else {}

    existing_trades = (
        db.query(Trade)
        .filter(
            Trade.fund_code.in_(codes),
            Trade.trade_date == as_of,
            Trade.source.in_(("ocr", OCR_TRADE_SOURCE)),
        )
        .all()
    ) if codes else []
    trades_by_key = {
        (t.fund_code, t.trade_type, _round_share(t.shares))
        for t in existing_trades
    }

    diffs: list[dict[str, Any]] = []
    for item in normalized:
        code = item["fund_code"]
        holding = holdings_by_code.get(code)
        fund = funds_by_code.get(code) or (holding.fund if holding else None)
        prev_shares = _round_share(holding.shares if holding else 0)
        next_shares = _round_share(item["shares"])
        delta = round(next_shares - prev_shares, 2)
        prev_value = _round_money(holding.current_value if holding else 0)
        next_value = _round_money(item["amount"])
        nav_price = _nav_for_snapshot(item, holding, fund)
        warnings = list(item.get("warnings", []))

        trade_type = ""
        status = "unchanged"
        if not holding and next_shares > SHARE_EPSILON:
            status = "new"
            trade_type = "买入"
        elif abs(delta) <= SHARE_EPSILON:
            status = "unchanged"
        elif delta > 0:
            status = "increased"
            trade_type = "买入"
        else:
            status = "decreased"
            trade_type = "卖出"

        inferred_shares = _round_share(abs(delta))
        inferred_amount = _round_money(inferred_shares * nav_price)
        if trade_type and inferred_shares <= SHARE_EPSILON:
            warnings.append("OCR 未识别出有效份额，无法生成交易记录")
        if trade_type and nav_price <= 0:
            warnings.append("缺少可用净值，无法按当日 NAV 推断成交金额")

        duplicate_trade = (
            bool(trade_type)
            and (code, trade_type, inferred_shares) in trades_by_key
        )
        if duplicate_trade:
            warnings.append("已存在同日同份额 OCR 交易，确认时会跳过重复交易")

        can_create_trade = bool(
            trade_type
            and inferred_shares > SHARE_EPSILON
            and nav_price > 0
            and not duplicate_trade
        )
        diffs.append({
            "fund_code": code,
            "fund_name": item["fund_name"] or (fund.fund_name if fund else code),
            "status": status,
            "status_label": {
                "new": "新增持仓",
                "increased": "份额增加",
                "decreased": "份额减少",
                "unchanged": "份额未变",
            }.get(status, status),
            "previous_shares": prev_shares,
            "snapshot_shares": next_shares,
            "share_delta": delta,
            "previous_value": prev_value,
            "snapshot_value": next_value,
            "value_delta": _round_money(next_value - prev_value),
            "nav_price": nav_price,
            "trade_type": trade_type,
            "inferred_shares": inferred_shares,
            "inferred_amount": inferred_amount,
            "trade_date": as_of.isoformat(),
            "duplicate_trade": duplicate_trade,
            "can_create_trade": can_create_trade,
            "warnings": warnings,
        })

    snapshot_codes = set(codes)
    missing_holdings = [
        {
            "fund_code": h.fund_code,
            "fund_name": h.fund.fund_name if h.fund else h.fund_code,
            "previous_shares": _round_share(h.shares),
            "previous_value": _round_money(h.current_value),
            "warning": "当前持仓未出现在本次截图中，暂不自动按全部赎回处理",
        }
        for h in holdings
        if h.fund_code not in snapshot_codes and _f(h.shares) > SHARE_EPSILON
    ]

    tradable = [d for d in diffs if d["can_create_trade"]]
    summary = {
        "snapshot_count": len(normalized),
        "active_holding_count": len(holdings),
        "changed_count": sum(1 for d in diffs if d["status"] in ("new", "increased", "decreased")),
        "inferred_trade_count": len(tradable),
        "duplicate_trade_count": sum(1 for d in diffs if d["duplicate_trade"]),
        "missing_holding_count": len(missing_holdings),
        "invalid_item_count": len(invalid_items),
        "buy_amount": _round_money(sum(d["inferred_amount"] for d in tradable if d["trade_type"] == "买入")),
        "sell_amount": _round_money(sum(d["inferred_amount"] for d in tradable if d["trade_type"] == "卖出")),
        "total_previous_value": _round_money(sum(_f(h.current_value) for h in holdings)),
        "total_snapshot_value": _round_money(sum(item["amount"] for item in normalized)),
    }

    return {
        "as_of": as_of.isoformat(),
        "summary": summary,
        "diffs": diffs,
        "missing_holdings": missing_holdings,
        "invalid_items": invalid_items,
    }


def create_inferred_trades(db: Session, diff_result: dict[str, Any]) -> dict[str, Any]:
    """Persist non-duplicate inferred OCR trades. Caller owns transaction commit."""
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in diff_result.get("diffs", []):
        if not item.get("trade_type"):
            continue
        if item.get("duplicate_trade"):
            skipped.append({"fund_code": item["fund_code"], "reason": "重复交易"})
            continue
        if not item.get("can_create_trade"):
            skipped.append({"fund_code": item["fund_code"], "reason": "净值或份额不足"})
            continue

        trade = Trade(
            fund_code=item["fund_code"],
            trade_type=item["trade_type"],
            shares=item["inferred_shares"],
            nav_price=item["nav_price"],
            amount=item["inferred_amount"],
            fee=0,
            trade_date=_parse_day(item.get("trade_date")),
            source=OCR_TRADE_SOURCE,
            note=(
                "OCR持仓快照自动推断："
                f"{item['previous_shares']} -> {item['snapshot_shares']} 份"
            ),
        )
        db.add(trade)
        created.append({
            "fund_code": item["fund_code"],
            "fund_name": item.get("fund_name") or "",
            "trade_type": item["trade_type"],
            "shares": item["inferred_shares"],
            "amount": item["inferred_amount"],
            "nav_price": item["nav_price"],
            "trade_date": item["trade_date"],
        })

    return {
        "created": created,
        "skipped": skipped,
        "created_count": len(created),
        "skipped_count": len(skipped),
    }
