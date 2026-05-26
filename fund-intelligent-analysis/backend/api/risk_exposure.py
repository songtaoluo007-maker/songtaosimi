"""
组合风险暴露 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.risk_exposure_service import (
    get_industry_exposure, get_theme_exposure, get_style_exposure,
    get_concentration, get_full_report,
)
from backend.services.fund_tag_service import (
    get_fund_tags, auto_tag_fund, auto_tag_all,
    update_tag, delete_tag, create_manual_tag,
)

router = APIRouter(prefix="/api/risk-exposure", tags=["风险暴露"])


@router.get("/report")
def full_report(db: Session = Depends(get_db)):
    """全景报告"""
    return get_full_report(db)


@router.get("/industry")
def industry_exposure(db: Session = Depends(get_db)):
    return get_industry_exposure(db)


@router.get("/theme")
def theme_exposure(db: Session = Depends(get_db)):
    return get_theme_exposure(db)


@router.get("/style")
def style_exposure(db: Session = Depends(get_db)):
    return get_style_exposure(db)


@router.get("/concentration")
def concentration(db: Session = Depends(get_db)):
    return get_concentration(db)


# --- 标签管理 ---

@router.get("/fund/{fund_code}/tags")
def fund_tags(fund_code: str, db: Session = Depends(get_db)):
    return get_fund_tags(db, fund_code)


@router.post("/fund/{fund_code}/tags")
def add_tag(fund_code: str, data: dict, db: Session = Depends(get_db)):
    tag_type = data.get("tag_type", "")
    tag_name = data.get("tag_name", "")
    tag_value = float(data.get("tag_value", 1.0))
    if tag_type not in ("industry", "theme", "style", "risk"):
        raise HTTPException(status_code=400, detail="tag_type 必须为 industry/theme/style/risk")
    if not tag_name:
        raise HTTPException(status_code=400, detail="tag_name 不能为空")
    t = create_manual_tag(db, fund_code, tag_type, tag_name, tag_value)
    return t.to_dict()


@router.put("/tags/{tag_id}")
def edit_tag(tag_id: int, data: dict, db: Session = Depends(get_db)):
    t = update_tag(db, tag_id, data.get("tag_name"), data.get("tag_value"))
    if not t:
        raise HTTPException(status_code=404, detail="标签不存在")
    return t.to_dict()


@router.delete("/tags/{tag_id}")
def remove_tag(tag_id: int, db: Session = Depends(get_db)):
    ok = delete_tag(db, tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="标签不存在")
    return {"message": "已删除"}


# --- 自动打标 ---

@router.post("/auto-tag/{fund_code}")
def auto_tag_single(fund_code: str, db: Session = Depends(get_db)):
    tags = auto_tag_fund(db, fund_code)
    return {"fund_code": fund_code, "tags": [t.to_dict() for t in tags]}


@router.post("/auto-tag-all")
def auto_tag_all_funds(db: Session = Depends(get_db)):
    result = auto_tag_all(db)
    return result


# --- P0.3 持仓重叠度 ---

@router.get("/overlap")
def overlap_report(db: Session = Depends(get_db)):
    """组合两两持仓重叠度 + 真实分散度评分 + 重复重仓股"""
    from backend.services.overlap_analyzer_v3 import calc_overlap_report
    return calc_overlap_report(db)


@router.post("/overlap/sync")
def sync_overlap_holdings(db: Session = Depends(get_db)):
    """立即从 AKShare 拉所有持仓基金的前十大持股（季报披露日后手动触发）"""
    from backend.services.fund_top_holdings_collector_v3 import sync_all_holding_top_holdings
    return sync_all_holding_top_holdings(db)


@router.post("/overlap/sync/{fund_code}")
def sync_overlap_single(fund_code: str, db: Session = Depends(get_db)):
    """单只基金的前十大持股同步（用于在持仓页临时补数据）"""
    from backend.services.fund_top_holdings_collector_v3 import sync_fund_top_holdings
    return sync_fund_top_holdings(db, fund_code)
