"""
OCR 识别 API — V2

V2 改动：
- BUG 修复：原 v1 在异常分支调用 logger.warning/debug 但未 import logger，触发 NameError
- 抽出公共的 _save_and_recognize 函数，避免上传与交易识别两份重复代码
- 临时文件清理逻辑统一：归档失败时降级为 unlink，并补 logger 上下文
"""
import os
import uuid
from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db

router = APIRouter(prefix="/api/ocr", tags=["OCR识别"])


def _archive_or_remove(temp_path: str, ext: str) -> None:
    """归档识别完的截图，归档失败时降级为直接删除，避免文件遗留。"""
    if not os.path.exists(temp_path):
        return
    try:
        archive_dir = os.path.join(settings.OCR_TEMP_DIR, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(archive_dir, f"{ts}_{uuid.uuid4().hex[:8]}{ext}")
        os.rename(temp_path, archive_path)
    except Exception as e:
        logger.warning(f"OCR 文件归档失败，转为删除: {e}")
        try:
            os.remove(temp_path)
        except Exception as clean_e:
            logger.debug(f"清理临时文件失败: {clean_e}")


async def _save_and_recognize(files: List[UploadFile], source: str) -> list[dict]:
    from backend.services.ocr_service import OcrService

    service = OcrService()
    results: list[dict] = []

    for file in files:
        ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
        temp_path = os.path.join(settings.OCR_TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
        try:
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            try:
                results.extend(service.recognize(temp_path, source))
            except Exception as e:
                logger.warning(f"OCR 识别失败 {file.filename}: {e}")
                results.append({"error": str(e), "filename": file.filename})
        finally:
            _archive_or_remove(temp_path, ext)

    return results


@router.post("/upload")
async def upload_screenshot(
    source: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    all_results = await _save_and_recognize(files, source)

    # 多图按 fund_code 去重，保留金额最大的（更可能是完整数据）
    if source in ("tiantian", "alipay"):
        merged: dict[str, dict] = {}
        errors_list: list[dict] = []
        for item in all_results:
            if "error" in item:
                errors_list.append(item)
                continue
            code = item.get("fund_code", "")
            if not code:
                errors_list.append(item)
                continue
            existing = merged.get(code)
            if not existing or float(item.get("amount", 0) or 0) > float(existing.get("amount", 0) or 0):
                merged[code] = item
        all_results = list(merged.values()) + errors_list

    return {"source": source, "results": all_results}


class OcrConfirmItem(BaseModel):
    fund_code: str = ""
    fund_name: str = ""
    shares: float = 0
    amount: float = 0
    cost_amount: float = 0
    daily_pnl: float = 0
    daily_pnl_date: Optional[str] = ""
    holding_pnl: float = 0
    holding_pnl_pct: float = 0
    source: str = "ocr"


class OcrSnapshotDiffRequest(BaseModel):
    items: list[OcrConfirmItem]
    trade_date: Optional[str] = None


class OcrSnapshotConfirmRequest(BaseModel):
    items: list[OcrConfirmItem]
    trade_date: Optional[str] = None
    generate_trades: bool = True


def _items_to_dicts(items: list[OcrConfirmItem]) -> list[dict[str, Any]]:
    return [item.model_dump() for item in items]


def _upsert_holding_items(items: list[OcrConfirmItem], db: Session) -> list[dict[str, str]]:
    from backend.models.fund import Fund
    from backend.models.holding import Holding

    created = []
    for item in items:
        fund_code = item.fund_code
        fund_name = item.fund_name
        shares = item.shares
        amount = item.amount
        cost_amount = item.cost_amount or amount

        if not fund_code:
            continue

        try:
            daily_pnl_date = (
                datetime.strptime(item.daily_pnl_date[:10], "%Y-%m-%d").date()
                if item.daily_pnl_date
                else date.today()
            )
        except ValueError:
            daily_pnl_date = date.today()

        fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
        if not fund:
            if not fund_name or fund_name.startswith("基金"):
                try:
                    from backend.services.fund_nav_collector import fetch_fund_info

                    info = fetch_fund_info(fund_code) or {}
                    fund_name = info.get("fund_name", fund_code) or fund_code
                except Exception as e:
                    logger.debug(f"基金信息补全失败 {fund_code}: {e}")
                    fund_name = fund_name or fund_code
            fund = Fund(fund_code=fund_code, fund_name=fund_name)
            db.add(fund)
            db.flush()
        elif fund_name and not fund_name.startswith("基金") and (
            not fund.fund_name
            or fund.fund_name.startswith("基金")
            or len(fund_name) > len(fund.fund_name or "")
        ):
            fund.fund_name = fund_name

        holding = db.query(Holding).filter(
            Holding.fund_code == fund_code,
            Holding.is_active == True,
        ).first()

        if holding:
            if shares > 0:
                holding.shares = shares
            if cost_amount > 0:
                holding.cost_amount = cost_amount
            if amount > 0:
                holding.current_value = amount
            if holding.shares > 0:
                holding.cost_price = holding.cost_amount / holding.shares
            holding.daily_pnl = item.daily_pnl
            holding.daily_pnl_date = daily_pnl_date
            if amount and amount != item.daily_pnl:
                base_value = amount - item.daily_pnl
                holding.daily_pnl_ratio = item.daily_pnl / base_value * 100 if base_value else 0
            calculated_pnl = float(holding.current_value or 0) - float(holding.cost_amount or 0)
            holding.pnl_amount = calculated_pnl
            if float(holding.cost_amount or 0) > 0:
                holding.pnl_ratio = calculated_pnl / float(holding.cost_amount) * 100
            elif item.holding_pnl_pct != 0:
                holding.pnl_ratio = item.holding_pnl_pct
            else:
                holding.pnl_ratio = 0
            holding.source = f"ocr_{item.source}"
        else:
            cost_price = cost_amount / shares if shares > 0 else 0
            current_nav = float(fund.latest_nav or 0)
            market_value = amount if amount > 0 else shares * current_nav
            holding = Holding(
                fund_code=fund_code,
                shares=shares,
                cost_price=cost_price,
                cost_amount=cost_amount,
                current_nav=current_nav,
                current_value=market_value,
                daily_pnl=item.daily_pnl,
                daily_pnl_date=daily_pnl_date,
                source=f"ocr_{item.source}",
                is_active=True,
            )
            if market_value and market_value != item.daily_pnl:
                base_value = market_value - item.daily_pnl
                holding.daily_pnl_ratio = item.daily_pnl / base_value * 100 if base_value else 0
            if item.holding_pnl != 0:
                holding.pnl_amount = item.holding_pnl
            else:
                holding.pnl_amount = market_value - cost_amount
            if item.holding_pnl_pct != 0:
                holding.pnl_ratio = item.holding_pnl_pct
            elif cost_amount > 0:
                holding.pnl_ratio = holding.pnl_amount / cost_amount * 100
            else:
                holding.pnl_ratio = 0
            db.add(holding)

        created.append({"fund_code": fund_code, "fund_name": fund_name})

    return created


@router.get("/status")
def get_ocr_status(db: Session = Depends(get_db)):
    """OCR 持仓同步状态，用于每周截图更新提醒。"""
    from backend.services.ocr_reconcile_service_v3 import get_ocr_sync_status

    return get_ocr_sync_status(db)


@router.post("/diff-preview")
def preview_ocr_snapshot_diff(payload: OcrSnapshotDiffRequest, db: Session = Depends(get_db)):
    """预览本次 OCR 持仓快照与当前持仓的差异，并推断交易记录。"""
    from backend.services.ocr_reconcile_service_v3 import build_snapshot_diff

    return build_snapshot_diff(db, _items_to_dicts(payload.items), payload.trade_date)


@router.post("/confirm")
def confirm_ocr_result(items: list[OcrConfirmItem], db: Session = Depends(get_db)):
    """用户确认 OCR 持仓结果，写入持仓表（兼容旧流程，不自动生成交易）"""
    created = _upsert_holding_items(items, db)
    db.commit()
    return {"message": f"成功导入 {len(created)} 只基金持仓", "created": created}


@router.post("/confirm-snapshot")
def confirm_ocr_snapshot(payload: OcrSnapshotConfirmRequest, db: Session = Depends(get_db)):
    """用户确认 OCR 持仓快照，先计算差异，再按截图更新持仓并记录推断交易。"""
    from backend.services.ocr_reconcile_service_v3 import (
        build_snapshot_diff,
        create_inferred_trades,
        get_ocr_sync_status,
    )

    item_dicts = _items_to_dicts(payload.items)
    diff = build_snapshot_diff(db, item_dicts, payload.trade_date)
    created = _upsert_holding_items(payload.items, db)
    trade_result = (
        create_inferred_trades(db, diff)
        if payload.generate_trades
        else {"created": [], "skipped": [], "created_count": 0, "skipped_count": 0}
    )
    db.commit()
    return {
        "message": f"成功同步 {len(created)} 只基金持仓，生成 {trade_result['created_count']} 条推断交易",
        "created": created,
        "trades": trade_result,
        "diff": diff,
        "sync_status": get_ocr_sync_status(db),
    }


@router.post("/upload-trades")
async def upload_trades_screenshot(files: List[UploadFile] = File(...)):
    results = await _save_and_recognize(files, "tiantian_trades")
    return {"source": "tiantian_trades", "results": results}


@router.post("/confirm-trades")
def confirm_trades(items: List[dict], db: Session = Depends(get_db)):
    """确认并导入 OCR 识别的交易记录（与 v1 相同逻辑）"""
    from backend.models.fund import Fund
    from backend.models.holding import Holding
    from backend.models.trade import Trade
    from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav

    created = []
    skipped = []
    errors = []

    for item in items:
        try:
            fund_code = (item.get("fund_code") or "").strip()
            fund_name = (item.get("fund_name") or "").strip()
            trade_type = item.get("trade_type", "")
            amount = float(item.get("amount", 0) or 0)
            shares = float(item.get("shares", 0) or 0)
            trade_date_str = item.get("trade_date", "")
            status = item.get("status", "")

            if "撤" in status:
                skipped.append({"fund_name": fund_name, "reason": status})
                continue
            if trade_type not in ("买入", "卖出"):
                errors.append({"fund_name": fund_name, "reason": "交易类型无效"})
                continue

            if fund_code:
                fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
                if not fund:
                    info = fetch_fund_info(fund_code) or {}
                    fund = Fund(
                        fund_code=fund_code,
                        fund_name=info.get("fund_name") or fund_name or fund_code,
                    )
                    db.add(fund)
                    db.flush()
            else:
                fund = db.query(Fund).filter(Fund.fund_name.contains(fund_name[:4])).first()
                if not fund:
                    errors.append({"fund_name": fund_name, "reason": "未找到基金代码"})
                    continue
                fund_code = fund.fund_code

            try:
                trade_date = (
                    datetime.strptime(trade_date_str[:10], "%Y-%m-%d").date()
                    if trade_date_str
                    else date.today()
                )
            except ValueError:
                trade_date = date.today()

            nav = fetch_latest_nav(fund_code)
            if trade_type == "买入" and amount > 0 and shares <= 0 and nav > 0:
                shares = round(amount / nav, 2)
            elif trade_type == "卖出" and shares > 0 and amount <= 0 and nav > 0:
                amount = round(shares * nav, 2)

            nav_price = nav if nav > 0 else (amount / shares if shares > 0 else 0)
            db.add(Trade(
                fund_code=fund_code,
                trade_type=trade_type,
                shares=shares,
                nav_price=nav_price,
                amount=amount,
                fee=0,
                trade_date=trade_date,
                source="ocr",
                note=item.get("note", ""),
            ))

            holding = db.query(Holding).filter(
                Holding.fund_code == fund_code,
                Holding.is_active == True,
            ).first()

            if trade_type == "买入":
                if holding:
                    new_total = float(holding.cost_amount or 0) + amount
                    new_shares = float(holding.shares or 0) + shares
                    holding.shares = new_shares
                    holding.cost_amount = new_total
                    holding.cost_price = new_total / new_shares if new_shares > 0 else 0
                    holding.current_nav = nav if nav > 0 else holding.current_nav
                    holding.current_value = new_shares * float(holding.current_nav or 0)
                    holding.pnl_amount = float(holding.current_value or 0) - new_total
                    holding.pnl_ratio = (holding.pnl_amount / new_total * 100) if new_total > 0 else 0
                else:
                    new_holding = Holding(
                        fund_code=fund_code,
                        shares=shares,
                        cost_price=nav_price,
                        cost_amount=amount,
                        current_nav=nav or nav_price,
                        current_value=shares * (nav or nav_price),
                        source="ocr_tiantian_trades",
                        is_active=True,
                    )
                    new_holding.pnl_amount = float(new_holding.current_value) - amount
                    new_holding.pnl_ratio = (new_holding.pnl_amount / amount * 100) if amount > 0 else 0
                    db.add(new_holding)
            else:  # 卖出
                if holding:
                    remaining = float(holding.shares or 0) - shares
                    if remaining <= 0:
                        holding.is_active = False
                        holding.shares = 0
                    else:
                        ratio = shares / float(holding.shares)
                        holding.shares = remaining
                        holding.cost_amount = float(holding.cost_amount or 0) * (1 - ratio)
                        holding.current_value = remaining * float(holding.current_nav or 0)
                        holding.pnl_amount = float(holding.current_value) - float(holding.cost_amount)
                        holding.pnl_ratio = (
                            holding.pnl_amount / float(holding.cost_amount) * 100
                            if float(holding.cost_amount) > 0
                            else 0
                        )

            created.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "trade_type": trade_type,
                "amount": amount,
                "shares": shares,
            })
        except Exception as e:
            errors.append({"fund_name": item.get("fund_name", ""), "reason": str(e)})

    db.commit()
    return {
        "message": f"成功导入 {len(created)} 条交易记录",
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }
