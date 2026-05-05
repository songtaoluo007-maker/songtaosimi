from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.ai_advice import AiAdvice
from backend.schemas.ai_advice import AiAdviceResponse

router = APIRouter(prefix="/api/ai", tags=["AI顾问"])


@router.get("/advice")
def list_advices(limit: int = 30, db: Session = Depends(get_db)):
    """历史建议列表"""
    advices = db.query(AiAdvice).order_by(AiAdvice.advice_date.desc()).limit(limit).all()
    return [a.to_dict() for a in advices]


@router.get("/advice/latest")
def get_latest_advice(db: Session = Depends(get_db)):
    """最新一条建议"""
    advice = db.query(AiAdvice).order_by(AiAdvice.advice_date.desc(), AiAdvice.advice_time.desc()).first()
    if not advice:
        return {"message": "暂无AI建议", "advice": None}
    return advice.to_dict()


@router.post("/advice/generate")
def generate_advice(db: Session = Depends(get_db)):
    """手动触发AI建议生成"""
    try:
        from backend.services.ai_advisor import AiAdvisorService
        service = AiAdvisorService(db)
        result = service.generate_close_advice()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI建议生成失败: {str(e)}")


@router.put("/advice/{advice_id}/read")
def mark_advice_read(advice_id: int, db: Session = Depends(get_db)):
    """标记已读"""
    advice = db.query(AiAdvice).filter(AiAdvice.id == advice_id).first()
    if not advice:
        raise HTTPException(status_code=404, detail="建议不存在")
    advice.is_read = True
    db.commit()
    return {"message": "已标记为已读"}
