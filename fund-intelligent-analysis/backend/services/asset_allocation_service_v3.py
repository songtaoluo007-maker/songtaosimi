"""
目标资产配置 + 偏离检测 + 再平衡建议 — P1.2

核心算法：
1. 基金归类到资产大类（_classify_fund）— 基于 fund_type 字段关键词
2. 计算当前组合各大类实际占比
3. 与目标比较 → 偏离 > tolerance → 生成 RebalanceAlert（每天最多 1 条 per class）
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from backend.models.asset_allocation import AssetAllocationTarget, RebalanceAlert
from backend.models.fund import Fund
from backend.models.holding import Holding


ASSET_CLASS_LABELS = {
    "equity_a": "A股权益",
    "equity_hk": "港股权益",
    "equity_us": "海外权益 (QDII)",
    "bond": "债券",
    "gold": "黄金/贵金属",
    "cash": "货币/现金",
}


def _classify_fund(fund: Fund | None) -> str:
    if not fund:
        return "equity_a"
    ft = (fund.fund_type or "").lower()
    name = (fund.fund_name or "").lower()
    blob = ft + " " + name
    if any(k in blob for k in ("qdii", "海外", "美", "纳斯达克", "标普")):
        return "equity_us"
    if any(k in blob for k in ("港股", "恒生", "hkex")):
        return "equity_hk"
    if any(k in blob for k in ("黄金", "贵金属", "白银")):
        return "gold"
    if "债" in blob:
        return "bond"
    if any(k in blob for k in ("货币", "短债", "现金")):
        return "cash"
    return "equity_a"


# ──────────────── 目标 CRUD ────────────────

def upsert_targets(db: Session, items: list[dict]) -> list[dict]:
    """批量 upsert 目标配置；items 形如 [{asset_class, target_pct, tolerance_pct, notes}, ...]"""
    existing = {t.asset_class: t for t in db.query(AssetAllocationTarget).all()}
    saved: list[AssetAllocationTarget] = []
    for it in items:
        cls = it.get("asset_class")
        if cls not in ASSET_CLASS_LABELS:
            continue
        target_pct = float(it.get("target_pct") or 0)
        tolerance_pct = float(it.get("tolerance_pct") or 5.0)
        notes = it.get("notes") or ""
        row = existing.get(cls)
        if row:
            row.target_pct = target_pct
            row.tolerance_pct = tolerance_pct
            row.notes = notes
        else:
            row = AssetAllocationTarget(
                asset_class=cls,
                target_pct=target_pct,
                tolerance_pct=tolerance_pct,
                notes=notes,
            )
            db.add(row)
        saved.append(row)
    db.commit()
    return [r.to_dict() for r in saved]


def list_targets(db: Session) -> list[dict]:
    rows = db.query(AssetAllocationTarget).order_by(AssetAllocationTarget.id.asc()).all()
    return [{**r.to_dict(), "label": ASSET_CLASS_LABELS.get(r.asset_class, r.asset_class)} for r in rows]


def reset_targets(db: Session) -> int:
    n = db.query(AssetAllocationTarget).delete()
    db.commit()
    return n


# ──────────────── 当前配置 + 偏离 ────────────────

def compute_current_allocation(db: Session) -> dict:
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    total = sum(float(h.current_value or 0) for h in holdings)
    by_class: dict[str, float] = defaultdict(float)
    detail: list[dict] = []
    for h in holdings:
        cls = _classify_fund(h.fund)
        value = float(h.current_value or 0)
        by_class[cls] += value
        detail.append({
            "fund_code": h.fund_code,
            "fund_name": h.fund.fund_name if h.fund else "",
            "asset_class": cls,
            "value": round(value, 2),
        })
    current_pct = {
        cls: round(value / total * 100, 2) if total > 0 else 0
        for cls, value in by_class.items()
    }
    return {
        "total_value": round(total, 2),
        "by_class_value": {cls: round(v, 2) for cls, v in by_class.items()},
        "by_class_pct": current_pct,
        "fund_detail": detail,
    }


def compute_deviations(db: Session, persist: bool = False) -> dict:
    """与目标对比，偏离 > tolerance → 生成 RebalanceAlert（persist=True 时）"""
    targets = db.query(AssetAllocationTarget).all()
    if not targets:
        return {"targets": [], "current": {}, "deviations": [],
                "message": "尚未设置目标资产配置"}
    current = compute_current_allocation(db)
    total = current["total_value"]
    by_pct = current["by_class_pct"]

    deviations = []
    classes_seen = set()
    for t in targets:
        classes_seen.add(t.asset_class)
        cur_pct = float(by_pct.get(t.asset_class, 0))
        target_pct = float(t.target_pct or 0)
        dev = round(cur_pct - target_pct, 2)
        within_tolerance = abs(dev) <= float(t.tolerance_pct or 5)
        suggested_amount = round(abs(dev) / 100 * total, 2) if total > 0 else 0
        deviations.append({
            "asset_class": t.asset_class,
            "label": ASSET_CLASS_LABELS.get(t.asset_class, t.asset_class),
            "target_pct": target_pct,
            "current_pct": cur_pct,
            "deviation_pct": dev,
            "within_tolerance": within_tolerance,
            "suggested_action": "reduce" if dev > 0 else ("add" if dev < 0 else "hold"),
            "suggested_amount": suggested_amount,
        })

    # 还有当前持有但目标中没有设的资产类
    for cls, pct in by_pct.items():
        if cls in classes_seen:
            continue
        deviations.append({
            "asset_class": cls,
            "label": ASSET_CLASS_LABELS.get(cls, cls),
            "target_pct": 0,
            "current_pct": pct,
            "deviation_pct": pct,
            "within_tolerance": pct < 5,
            "suggested_action": "reduce",
            "suggested_amount": round(pct / 100 * total, 2) if total > 0 else 0,
        })

    # 持久化未达标项
    if persist:
        today = date.today()
        # 删除今日同类未确认的旧记录，避免重复
        db.query(RebalanceAlert).filter(
            RebalanceAlert.detect_date == today,
            RebalanceAlert.is_acknowledged == False,
        ).delete(synchronize_session=False)
        for d in deviations:
            if d["within_tolerance"]:
                continue
            db.add(RebalanceAlert(
                detect_date=today,
                asset_class=d["asset_class"],
                target_pct=d["target_pct"],
                current_pct=d["current_pct"],
                deviation_pct=d["deviation_pct"],
                suggested_action=d["suggested_action"],
                suggested_amount=d["suggested_amount"],
            ))
        db.commit()

    return {
        "targets": [{"asset_class": t.asset_class,
                     "label": ASSET_CLASS_LABELS.get(t.asset_class, t.asset_class),
                     "target_pct": float(t.target_pct), "tolerance_pct": float(t.tolerance_pct)}
                    for t in targets],
        "current": current,
        "deviations": deviations,
        "needs_rebalance": any(not d["within_tolerance"] for d in deviations),
    }


def list_alerts(db: Session, only_unack: bool = True, limit: int = 30) -> list[dict]:
    q = db.query(RebalanceAlert)
    if only_unack:
        q = q.filter(RebalanceAlert.is_acknowledged == False)
    rows = q.order_by(RebalanceAlert.detect_date.desc(), RebalanceAlert.id.desc()).limit(limit).all()
    return [{**r.to_dict(),
             "label": ASSET_CLASS_LABELS.get(r.asset_class, r.asset_class)}
            for r in rows]


def acknowledge_alert(db: Session, alert_id: int) -> bool:
    row = db.query(RebalanceAlert).filter(RebalanceAlert.id == alert_id).first()
    if not row:
        return False
    row.is_acknowledged = True
    db.commit()
    return True
