from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.fund_group import FundGroup, FundGroupMember
from backend.models.holding import Holding

router = APIRouter(prefix="/api/groups", tags=["基金组管理"])


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#2f6fef"


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class GroupMembersUpdate(BaseModel):
    fund_codes: list[str]


def group_payload(group: FundGroup, db: Session):
    members = db.query(FundGroupMember).filter(FundGroupMember.group_id == group.id).all()
    fund_codes = [m.fund_code for m in members]
    holdings = db.query(Holding).filter(Holding.is_active == True, Holding.fund_code.in_(fund_codes)).all() if fund_codes else []
    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    payload = group.to_dict()
    payload.update({
        "fund_codes": fund_codes,
        "holding_count": len(holdings),
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_value - total_cost, 2),
        "total_pnl_ratio": round((total_value - total_cost) / total_cost * 100, 2) if total_cost else 0,
    })
    return payload


@router.get("")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(FundGroup).filter(FundGroup.is_active == True).order_by(FundGroup.id).all()
    return [group_payload(g, db) for g in groups]


@router.post("")
def create_group(data: GroupCreate, db: Session = Depends(get_db)):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="组名不能为空")
    existing = db.query(FundGroup).filter(FundGroup.name == data.name.strip(), FundGroup.is_active == True).first()
    if existing:
        raise HTTPException(status_code=400, detail="基金组已存在")
    group = FundGroup(name=data.name.strip(), description=data.description, color=data.color)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group_payload(group, db)


@router.put("/{group_id}")
def update_group(group_id: int, data: GroupUpdate, db: Session = Depends(get_db)):
    group = db.query(FundGroup).filter(FundGroup.id == group_id, FundGroup.is_active == True).first()
    if not group:
        raise HTTPException(status_code=404, detail="基金组不存在")
    if data.name is not None:
        group.name = data.name.strip()
    if data.description is not None:
        group.description = data.description
    if data.color is not None:
        group.color = data.color
    db.commit()
    return group_payload(group, db)


@router.put("/{group_id}/members")
def replace_group_members(group_id: int, data: GroupMembersUpdate, db: Session = Depends(get_db)):
    group = db.query(FundGroup).filter(FundGroup.id == group_id, FundGroup.is_active == True).first()
    if not group:
        raise HTTPException(status_code=404, detail="基金组不存在")
    db.query(FundGroupMember).filter(FundGroupMember.group_id == group_id).delete()
    for code in sorted(set(data.fund_codes)):
        if code:
            db.add(FundGroupMember(group_id=group_id, fund_code=code))
    db.commit()
    return group_payload(group, db)


@router.delete("/{group_id}")
def delete_group(group_id: int, delete_holdings: bool = False, db: Session = Depends(get_db)):
    group = db.query(FundGroup).filter(FundGroup.id == group_id, FundGroup.is_active == True).first()
    if not group:
        raise HTTPException(status_code=404, detail="基金组不存在")
    members = db.query(FundGroupMember).filter(FundGroupMember.group_id == group_id).all()
    codes = [m.fund_code for m in members]
    if delete_holdings and codes:
        db.query(Holding).filter(Holding.is_active == True, Holding.fund_code.in_(codes)).update(
            {Holding.is_active: False},
            synchronize_session=False,
        )
    db.query(FundGroupMember).filter(FundGroupMember.group_id == group_id).delete()
    group.is_active = False
    db.commit()
    return {"message": "基金组已删除", "deleted_holdings": delete_holdings, "fund_codes": codes}
