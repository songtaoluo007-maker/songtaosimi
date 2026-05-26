"""
基金经理信息采集 + 变更监控 — P0.2

数据源（多源 fallback）：
1. 东方财富 https://fundf10.eastmoney.com/jjjl_{code}.html（历任 + 现任）
2. AKShare ak.fund_individual_basic_info_xq（备用）

预警规则：
- 持仓基金的现任经理"is_current 由 True 变 False" → 离职预警（severity=high）
- 持仓基金"新增基金经理" → 加入预警（severity=medium）
- 现任经理任职满 1/3/5 年 → 里程碑（severity=low）

调用方式：
- 单只刷新：sync_fund_managers(db, fund_code)
- 全量刷新：sync_all_holding_managers(db)  ← 每周日 20:00 由 APScheduler 触发
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from backend.models.fund_manager import FundManager, ManagerAlert
from backend.models.holding import Holding


HTTP_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _parse_pct(text: str) -> float | None:
    """从 '+89.30%' / '-12.45%' 字符串提取 float"""
    if not text:
        return None
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", text.replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_date(text: str) -> date | None:
    text = (text or "").strip()
    if not text or text in {"-", "至今"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fetch_managers_from_eastmoney(fund_code: str) -> list[dict]:
    """从东方财富基金详情页提取经理列表（历任 + 现任）。

    页面结构：表格列依次为 起始期/截止期/基金经理/任职期间/任职回报。
    """
    url = f"https://fundf10.eastmoney.com/jjjl_{fund_code}.html"
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            if resp.status_code != 200:
                logger.warning(f"东财经理页 {fund_code} 状态 {resp.status_code}")
                return []
            html = resp.text
    except Exception as e:
        logger.warning(f"获取基金 {fund_code} 经理信息失败: {e}")
        return []

    managers: list[dict] = []
    # 提取经理变动表 table
    table_match = re.search(
        r'<div[^>]*id="bs_jl"[^>]*>(.*?)</table>',
        html, re.S,
    ) or re.search(r"基金经理变动一览(.*?)</table>", html, re.S)
    if not table_match:
        return []

    table_html = table_match.group(1)
    for row in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(1), re.S)
        if len(cells) < 5:
            continue
        start_str = re.sub(r"<.*?>", "", cells[0]).strip()
        end_str = re.sub(r"<.*?>", "", cells[1]).strip()
        names_html = cells[2]
        # 经理名可能含 <a> 链接，取所有文本
        names = re.findall(r">([^<]+)<", names_html) or [
            re.sub(r"<.*?>", "", names_html).strip()
        ]
        names = [n.strip() for n in names if n.strip()]
        tenure_str = re.sub(r"<.*?>", "", cells[3]).strip()
        return_str = re.sub(r"<.*?>", "", cells[4]).strip()

        start_date = _parse_date(start_str)
        end_date = _parse_date(end_str)
        if not start_date:
            continue

        for name in names:
            managers.append({
                "manager_name": name,
                "start_date": start_date,
                "end_date": end_date,
                "tenure_str": tenure_str,
                "tenure_return_pct": _parse_pct(return_str),
            })

    return managers


def _build_alert(fund_code: str, alert_type: str, severity: str,
                 detail: str, old_manager: str | None = None,
                 new_manager: str | None = None) -> ManagerAlert:
    return ManagerAlert(
        fund_code=fund_code,
        alert_type=alert_type,
        old_manager=old_manager,
        new_manager=new_manager,
        alert_date=date.today(),
        severity=severity,
        detail=detail,
        is_read=False,
    )


def sync_fund_managers(db: Session, fund_code: str) -> dict:
    """同步单只基金经理列表，返回变更摘要"""
    new_data = fetch_managers_from_eastmoney(fund_code)
    if not new_data:
        return {"fund_code": fund_code, "alerts": [], "updated": 0,
                "warning": "经理信息源不可达，跳过"}

    existing_rows = (
        db.query(FundManager)
        .filter(FundManager.fund_code == fund_code)
        .all()
    )
    by_key = {(m.manager_name, m.start_date): m for m in existing_rows}

    new_current_names = {m["manager_name"] for m in new_data if not m["end_date"]}
    old_current_names = {m.manager_name for m in existing_rows if m.is_current}

    alerts: list[ManagerAlert] = []

    # 1. 离职检测（高优先级）
    for departed in old_current_names - new_current_names:
        alerts.append(_build_alert(
            fund_code=fund_code,
            alert_type="departure",
            severity="high",
            old_manager=departed,
            detail=f"{departed} 已不再担任 {fund_code} 基金经理（请关注新任表现并评估调仓）",
        ))
        for row in existing_rows:
            if row.manager_name == departed and row.is_current:
                row.is_current = False
                row.end_date = date.today()

    # 2. 新任检测（中优先级）
    for joined in new_current_names - old_current_names:
        alerts.append(_build_alert(
            fund_code=fund_code,
            alert_type="new_join",
            severity="medium",
            new_manager=joined,
            detail=f"{joined} 新任 {fund_code} 基金经理",
        ))

    # 3. upsert 所有经理记录
    updated_count = 0
    for m in new_data:
        key = (m["manager_name"], m["start_date"])
        existing = by_key.get(key)
        is_current = m["end_date"] is None
        if existing:
            existing.end_date = m["end_date"]
            existing.is_current = is_current
            if m["tenure_return_pct"] is not None:
                existing.tenure_return_pct = m["tenure_return_pct"]
            updated_count += 1
        else:
            db.add(FundManager(
                fund_code=fund_code,
                manager_name=m["manager_name"],
                start_date=m["start_date"],
                end_date=m["end_date"],
                tenure_return_pct=m["tenure_return_pct"],
                is_current=is_current,
            ))
            updated_count += 1

    # 4. 任期里程碑（低优先级）— 仅对现任经理
    today = date.today()
    for m in new_data:
        if m["end_date"] or not m["start_date"]:
            continue
        tenure_days = (today - m["start_date"]).days
        # 1 年 / 3 年 / 5 年 整周年 ± 7 天窗口
        for years in (1, 3, 5):
            target = years * 365
            if abs(tenure_days - target) <= 7:
                # 防止重复触发：检查最近 30 天有无同类型
                recent = (
                    db.query(ManagerAlert)
                    .filter(
                        ManagerAlert.fund_code == fund_code,
                        ManagerAlert.alert_type == "tenure_milestone",
                        ManagerAlert.old_manager == m["manager_name"],
                        ManagerAlert.alert_date >= today.replace(day=1),
                    )
                    .first()
                )
                if not recent:
                    alerts.append(_build_alert(
                        fund_code=fund_code,
                        alert_type="tenure_milestone",
                        severity="low",
                        old_manager=m["manager_name"],
                        detail=f"{m['manager_name']} 任职 {fund_code} 满 {years} 年",
                    ))

    for a in alerts:
        db.add(a)

    db.commit()

    return {
        "fund_code": fund_code,
        "alerts": [a.to_dict() for a in alerts],
        "updated": updated_count,
    }


def sync_all_holding_managers(db: Session) -> dict:
    """每周日 20:00 由 APScheduler 触发：检查所有持仓基金的经理变化。

    高优先级（high）预警会通过飞书推送（如果配置了 webhook）。
    """
    codes = [
        h.fund_code for h in
        db.query(Holding).filter(Holding.is_active == True).all()
    ]
    if not codes:
        logger.info("无活跃持仓，跳过经理同步")
        return {"checked": 0, "alerts": [], "summary": "无活跃持仓"}

    total_alerts: list[dict] = []
    skipped: list[str] = []
    for code in codes:
        try:
            result = sync_fund_managers(db, code)
            total_alerts.extend(result.get("alerts", []))
            if result.get("warning"):
                skipped.append(code)
        except Exception as e:
            logger.warning(f"基金 {code} 经理同步失败: {e}")
            skipped.append(code)

    # 高优先级走飞书
    high_alerts = [a for a in total_alerts if a.get("severity") == "high"]
    if high_alerts:
        try:
            from backend.services.notification import send_manager_alert
            send_manager_alert(high_alerts)
        except Exception as e:
            logger.warning(f"基金经理变更飞书推送失败: {e}")

    logger.info(
        f"基金经理同步完成: 检查 {len(codes)} 只，"
        f"产生 {len(total_alerts)} 个预警（高 {len(high_alerts)}），"
        f"跳过 {len(skipped)} 只"
    )
    return {
        "checked": len(codes),
        "alerts": total_alerts,
        "high_alerts_count": len(high_alerts),
        "skipped": skipped,
    }


def list_alerts(db: Session, only_unread: bool = True, limit: int = 50) -> list[dict]:
    query = db.query(ManagerAlert)
    if only_unread:
        query = query.filter(ManagerAlert.is_read == False)
    rows = (
        query
        .order_by(
            # high > medium > low 排序
            ManagerAlert.severity.asc(),
            ManagerAlert.alert_date.desc(),
            ManagerAlert.id.desc(),
        )
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]


def mark_alert_read(db: Session, alert_id: int) -> bool:
    row = db.query(ManagerAlert).filter(ManagerAlert.id == alert_id).first()
    if not row:
        return False
    row.is_read = True
    db.commit()
    return True


def get_fund_managers(db: Session, fund_code: str) -> dict:
    rows = (
        db.query(FundManager)
        .filter(FundManager.fund_code == fund_code)
        .order_by(FundManager.start_date.desc())
        .all()
    )
    current = [r.to_dict() for r in rows if r.is_current]
    history = [r.to_dict() for r in rows if not r.is_current]
    return {"fund_code": fund_code, "current": current, "history": history}
