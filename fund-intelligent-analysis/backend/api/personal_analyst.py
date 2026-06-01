"""
P3 专属 AI 分析师 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from backend.database import get_db
from backend.services.memory_service import MemoryService
from backend.services.outcome_service import OutcomeService
from backend.services.similar_case_service import SimilarCaseService

router = APIRouter(prefix="/api/personal-analyst", tags=["personal-analyst"])


# ========== Pydantic 模型 ==========

class FeedbackRequest(BaseModel):
    is_accepted: bool
    feedback: str = ""
    feedback_tags: list[str] = []


class RecalculateRequest(BaseModel):
    pass


class RunOutcomesRequest(BaseModel):
    pass


# ========== 画像接口 ==========

@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    """获取 AI 推断画像"""
    from backend.models.user_ai_profile import UserAiProfile
    profile = db.query(UserAiProfile).first()
    if not profile:
        return {"profile": None, "message": "暂无 AI 推断画像"}
    return {"profile": profile.to_dict()}


@router.post("/profile/recalculate")
def recalculate_profile(db: Session = Depends(get_db)):
    """重新计算 AI 推断画像"""
    from backend.models.user_ai_profile import UserAiProfile
    memory_svc = MemoryService(db)

    total = memory_svc.count_total()
    accepted = memory_svc.count_accepted()
    rejected = memory_svc.count_rejected()

    # 获取或创建画像
    profile = db.query(UserAiProfile).first()
    if not profile:
        profile = UserAiProfile()
        db.add(profile)

    # 基于历史数据推断
    profile.total_advices = total
    profile.accepted_count = accepted
    profile.rejected_count = rejected

    if total > 0:
        acceptance_rate = accepted / total
        if acceptance_rate > 0.7:
            profile.confidence_adjustment = 0.1
            profile.evidence_summary = f"用户采纳率 {acceptance_rate:.0%}，建议可信度调高"
        elif acceptance_rate < 0.3:
            profile.confidence_adjustment = -0.1
            profile.evidence_summary = f"用户采纳率 {acceptance_rate:.0%}，建议需更贴合用户偏好"
        else:
            profile.confidence_adjustment = 0.0
            profile.evidence_summary = f"用户采纳率 {acceptance_rate:.0%}，保持当前策略"
    else:
        profile.evidence_summary = "暂无历史建议数据"

    db.commit()
    db.refresh(profile)
    return {"profile": profile.to_dict()}


# ========== 记忆接口 ==========

@router.get("/memories")
def get_memories(
    limit: int = 50,
    offset: int = 0,
    decision: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """查询历史建议记忆"""
    svc = MemoryService(db)
    memories = svc.get_memories(limit=limit, offset=offset, decision=decision)
    return {"memories": memories, "total": svc.count_total()}


@router.get("/memories/{memory_id}")
def get_memory(memory_id: int, db: Session = Depends(get_db)):
    """获取单条记忆详情"""
    svc = MemoryService(db)
    memory = svc.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"memory": memory}


@router.post("/memories/{memory_id}/feedback")
def submit_feedback(
    memory_id: int,
    req: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """提交用户反馈"""
    svc = MemoryService(db)
    success = svc.submit_feedback(
        memory_id=memory_id,
        is_accepted=req.is_accepted,
        feedback=req.feedback,
        feedback_tags=req.feedback_tags,
    )
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"success": True}


# ========== 复盘接口 ==========

@router.get("/outcomes")
def get_outcomes(
    memory_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """查询复盘结果"""
    svc = OutcomeService(db)
    outcomes = svc.get_outcomes(memory_id=memory_id, limit=limit)
    summary = svc.get_summary()
    return {"outcomes": outcomes, "summary": summary}


@router.post("/outcomes/run")
def run_outcomes(db: Session = Depends(get_db)):
    """手动触发复盘任务"""
    svc = OutcomeService(db)
    result = svc.run_review()
    return result


# ========== 相似案例接口 ==========

@router.get("/similar-cases")
def get_similar_cases(
    market_trend: str = "neutral",
    fund_type: str = "mixed",
    current_drawdown: float = 0.0,
    sector_concentration: float = 0.5,
    risk_level: str = "medium",
    db: Session = Depends(get_db),
):
    """检索相似历史案例"""
    svc = SimilarCaseService(db)
    cases = svc.find_similar(
        market_trend=market_trend,
        fund_type=fund_type,
        current_drawdown=current_drawdown,
        sector_concentration=sector_concentration,
        risk_level=risk_level,
    )
    return {"cases": cases, "count": len(cases)}


# ========== 成长报告接口 ==========

@router.get("/report")
def get_report(db: Session = Depends(get_db)):
    """获取 AI 分析师成长报告"""
    memory_svc = MemoryService(db)
    outcome_svc = OutcomeService(db)

    memory_summary = {
        "total": memory_svc.count_total(),
        "accepted": memory_svc.count_accepted(),
        "rejected": memory_svc.count_rejected(),
    }
    outcome_summary = outcome_svc.get_summary()

    return {
        "memory_summary": memory_summary,
        "outcome_summary": outcome_summary,
        "report_period": "all_time",
    }
