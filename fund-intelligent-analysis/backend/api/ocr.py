import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date, datetime
from backend.database import get_db
from backend.config import settings

router = APIRouter(prefix="/api/ocr", tags=["OCR识别"])


@router.post("/upload")
async def upload_screenshot(
    source: str = Form(...),  # alipay / tiantian
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """上传截图并识别，返回解析结果（待确认）"""
    from backend.services.ocr_service import OcrService
    service = OcrService()

    all_results = []
    for file in files:
        # 保存临时文件
        ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
        temp_path = os.path.join(settings.OCR_TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        try:
            results = service.recognize(temp_path, source)
            all_results.extend(results)
        except Exception as e:
            all_results.append({"error": str(e), "filename": file.filename})
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # 多图去重合并：按 fund_code 去重，保留数据最完整的一条
    if source in ("tiantian", "alipay"):
        merged = {}
        errors_list = []
        for item in all_results:
            if "error" in item:
                errors_list.append(item)
                continue
            code = item.get("fund_code", "")
            if not code:
                errors_list.append(item)
                continue
            if code in merged:
                # 保留金额更大的（更可能是完整数据）
                existing = merged[code]
                if float(item.get("amount", 0) or 0) > float(existing.get("amount", 0) or 0):
                    merged[code] = item
            else:
                merged[code] = item
        all_results = list(merged.values()) + errors_list

    return {"source": source, "results": all_results}


from pydantic import BaseModel
from typing import Optional


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


@router.post("/confirm")
def confirm_ocr_result(
    items: list[OcrConfirmItem],
    db: Session = Depends(get_db),
):
    """用户确认OCR结果，正式写入持仓"""
    from backend.models.fund import Fund
    from backend.models.holding import Holding

    created = []
    for item in items:
        fund_code = item.fund_code
        fund_name = item.fund_name
        shares = item.shares
        amount = item.amount
        cost_amount = item.cost_amount or amount  # 同花顺可推算成本
        source = item.source
        daily_pnl_date = date.today()
        if item.daily_pnl_date:
            try:
                daily_pnl_date = datetime.strptime(item.daily_pnl_date[:10], "%Y-%m-%d").date()
            except ValueError:
                daily_pnl_date = date.today()

        if not fund_code:
            continue

        # 确保基金存在
        fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
        if not fund:
            # 联网查询补全基金信息
            if not fund_name or fund_name.startswith("基金"):
                try:
                    from backend.services.fund_nav_collector import fetch_fund_info
                    info = fetch_fund_info(fund_code)
                    fund_name = info.get("fund_name", fund_code) or fund_code
                except Exception:
                    fund_name = fund_name or fund_code
            fund = Fund(fund_code=fund_code, fund_name=fund_name)
            db.add(fund)
            db.flush()
        else:
            # 基金已存在：用OCR提供的更完整名称更新
            if fund_name and not fund_name.startswith("基金") and (
                not fund.fund_name
                or fund.fund_name.startswith("基金")
                or len(fund_name) > len(fund.fund_name or "")
            ):
                fund.fund_name = fund_name

        # 创建或更新持仓
        holding = db.query(Holding).filter(
            Holding.fund_code == fund_code,
            Holding.is_active == True,
        ).first()

        if holding:
            # OCR持仓截图是“当前快照”，重复导入时更新而不是累加，避免仓位越导越大。
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
            if item.holding_pnl != 0:
                holding.pnl_amount = item.holding_pnl
            else:
                holding.pnl_amount = float(holding.current_value or 0) - float(holding.cost_amount or 0)
            if item.holding_pnl_pct != 0:
                holding.pnl_ratio = item.holding_pnl_pct
            elif float(holding.cost_amount or 0) > 0:
                holding.pnl_ratio = holding.pnl_amount / float(holding.cost_amount) * 100
            else:
                holding.pnl_ratio = 0
            holding.source = f"ocr_{source}"
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
                source=f"ocr_{source}",
                is_active=True,
            )
            if market_value and market_value != item.daily_pnl:
                base_value = market_value - item.daily_pnl
                holding.daily_pnl_ratio = item.daily_pnl / base_value * 100 if base_value else 0
            # 计算盈亏：优先使用OCR识别值，否则从市值和成本推算
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

    db.commit()
    return {"message": f"成功导入 {len(created)} 只基金持仓", "created": created}


@router.post("/upload-trades")
async def upload_trades_screenshot(
    files: List[UploadFile] = File(...),
):
    """上传同花顺交易记录截图并OCR识别"""
    from backend.services.ocr_service import OcrService
    ocr_service = OcrService()
    all_results = []

    for file in files:
        # 保存临时文件
        ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
        temp_path = os.path.join(settings.OCR_TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        try:
            results = ocr_service.recognize(temp_path, "tiantian_trades")
            all_results.extend(results)
        except Exception as e:
            all_results.append({"error": str(e), "filename": file.filename})
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return {"source": "tiantian_trades", "results": all_results}


@router.post("/confirm-trades")
def confirm_trades(items: List[dict], db: Session = Depends(get_db)):
    """确认并导入OCR识别的交易记录"""
    from backend.models.fund import Fund
    from backend.models.holding import Holding
    from backend.models.trade import Trade
    from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav
    from datetime import datetime, date as date_type

    created = []
    skipped = []
    errors = []

    for item in items:
        try:
            fund_code = item.get("fund_code", "").strip()
            fund_name = item.get("fund_name", "").strip()
            trade_type = item.get("trade_type", "")
            amount = float(item.get("amount", 0) or 0)
            shares = float(item.get("shares", 0) or 0)
            trade_date_str = item.get("trade_date", "")
            status = item.get("status", "")

            # 跳过已撤单
            if "撤" in status:
                skipped.append({"fund_name": fund_name, "reason": status})
                continue

            # 必须有交易类型
            if trade_type not in ("买入", "卖出"):
                errors.append({"fund_name": fund_name, "reason": "交易类型无效"})
                continue

            # 确保基金存在
            if fund_code:
                fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
                if not fund:
                    info = fetch_fund_info(fund_code)
                    fund = Fund(
                        fund_code=fund_code,
                        fund_name=info.get("fund_name") or fund_name or fund_code
                    )
                    db.add(fund)
                    db.flush()
            else:
                # 没有代码，尝试通过名称在数据库查找
                fund = db.query(Fund).filter(Fund.fund_name.contains(fund_name[:4])).first()
                if not fund:
                    errors.append({"fund_name": fund_name, "reason": "未找到基金代码"})
                    continue
                fund_code = fund.fund_code

            # 解析交易日期
            if trade_date_str:
                try:
                    trade_date = datetime.strptime(trade_date_str[:10], "%Y-%m-%d").date()
                except Exception:
                    trade_date = date_type.today()
            else:
                trade_date = date_type.today()

            # 获取净值用于计算
            nav = fetch_latest_nav(fund_code)

            # 买入：有金额，推算份额
            if trade_type == "买入":
                if amount > 0 and shares <= 0 and nav > 0:
                    shares = round(amount / nav, 2)
                nav_price = nav if nav > 0 else (amount / shares if shares > 0 else 0)
            else:
                # 卖出：有份额，推算金额
                if shares > 0 and amount <= 0 and nav > 0:
                    amount = round(shares * nav, 2)
                nav_price = nav if nav > 0 else (amount / shares if shares > 0 else 0)

            # 创建交易记录
            trade = Trade(
                fund_code=fund_code,
                trade_type=trade_type,
                shares=shares,
                nav_price=nav_price,
                amount=amount,
                fee=0,
                trade_date=trade_date,
                source="ocr",
                note=item.get("note", "")
            )
            db.add(trade)

            # 更新持仓
            holding = db.query(Holding).filter(
                Holding.fund_code == fund_code,
                Holding.is_active == True
            ).first()

            if trade_type == "买入":
                if holding:
                    old_total = float(holding.cost_amount or 0)
                    new_total = old_total + amount
                    old_shares = float(holding.shares or 0)
                    new_shares = old_shares + shares
                    holding.shares = new_shares
                    holding.cost_amount = new_total
                    holding.cost_price = new_total / new_shares if new_shares > 0 else 0
                    holding.current_nav = nav if nav > 0 else holding.current_nav
                    holding.current_value = new_shares * float(holding.current_nav or 0)
                    holding.pnl_amount = float(holding.current_value or 0) - new_total
                    holding.pnl_ratio = (holding.pnl_amount / new_total * 100) if new_total > 0 else 0
                else:
                    holding = Holding(
                        fund_code=fund_code,
                        shares=shares,
                        cost_price=nav_price,
                        cost_amount=amount,
                        current_nav=nav or nav_price,
                        current_value=shares * (nav or nav_price),
                        source="ocr_tiantian_trades"
                    )
                    holding.pnl_amount = float(holding.current_value) - amount
                    holding.pnl_ratio = (holding.pnl_amount / amount * 100) if amount > 0 else 0
                    db.add(holding)

            elif trade_type == "卖出":
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
                        holding.pnl_ratio = (holding.pnl_amount / float(holding.cost_amount) * 100) if float(holding.cost_amount) > 0 else 0

            created.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "trade_type": trade_type,
                "amount": amount,
                "shares": shares
            })

        except Exception as e:
            errors.append({"fund_name": item.get("fund_name", ""), "reason": str(e)})

    db.commit()

    return {
        "message": f"成功导入 {len(created)} 条交易记录",
        "created": created,
        "skipped": skipped,
        "errors": errors
    }
