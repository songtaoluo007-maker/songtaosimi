"""
基金标签服务 — AI 自动打标 + 手动管理
"""
import json
from loguru import logger
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.fund import Fund
from backend.models.fund_tag import FundTag

TAG_PROMPT = """分析以下基金信息，输出其行业暴露、主题归属、风格类型和风险等级。

基金代码: {fund_code}
基金名称: {fund_name}
基金类型: {fund_type}

输出严格 JSON（只输出 JSON）：
{
  "industries": [{"name": "半导体", "exposure": 0.35}, {"name": "医药", "exposure": 0.15}],
  "themes": [{"name": "AI算力", "exposure": 0.5}, {"name": "存储芯片", "exposure": 0.3}],
  "style": "成长/价值/均衡/大盘/小盘/高波动/低波动",
  "risk_level": "低/中/高"
}

规则：
- industry: 行业分类（半导体/医药/军工/消费/新能源/环保/金融/地产/传媒/宽基 等）
- theme: 主题概念（AI算力/CPO/存储芯片/机器人/创新药/中特估/红利低波/科创50/沪深300/创业板 等）
- style: 基金风格
- risk_level: 基于基金类型和波动特征判断
- 每个基金 industry 1-3 个, theme 1-4 个
- 只需要写出有实际暴露的标签，不要为了填满而编造"""


def _call_ai_for_tags(fund_code: str, fund_name: str, fund_type: str) -> dict | None:
    """调用 AI 为单只基金打标"""
    if not settings.has_api_key:
        return None

    from openai import OpenAI
    prompt = TAG_PROMPT.format(fund_code=fund_code, fund_name=fund_name, fund_type=fund_type)

    try:
        client = OpenAI(
            api_key=settings.decrypted_api_key,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=60,
        )
        response = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的基金分类分析师，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)
    except Exception as e:
        logger.warning(f"AI打标失败 {fund_code}: {e}")
        return None


def auto_tag_fund(db: Session, fund_code: str) -> list[FundTag]:
    """AI 自动为单只基金打标，返回新创建的标签列表"""
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
    if not fund:
        return []

    # 清除旧AI标签
    db.query(FundTag).filter(FundTag.fund_code == fund_code, FundTag.source == "ai").delete()

    result = _call_ai_for_tags(fund_code, fund.fund_name or "", fund.fund_type or "")

    tags = []

    def _add_tag(tag_type: str, name: str, value: float = 1.0):
        t = FundTag(fund_code=fund_code, tag_type=tag_type, tag_name=name, tag_value=value, source="ai")
        db.add(t)
        tags.append(t)

    if result:
        for item in result.get("industries", []):
            _add_tag("industry", item.get("name", ""), item.get("exposure", 1.0))
        for item in result.get("themes", []):
            _add_tag("theme", item.get("name", ""), item.get("exposure", 1.0))
        style = result.get("style", "")
        if style:
            for s in [s.strip() for s in style.split("/") if s.strip()]:
                _add_tag("style", s)
        risk = result.get("risk_level", "")
        if risk:
            _add_tag("risk", risk)

    db.commit()
    logger.info(f"AI打标完成 {fund_code}: {len(tags)} 个标签")
    return tags


def auto_tag_all(db: Session) -> dict:
    """批量 AI 打标所有无标签基金"""
    funds = db.query(Fund).all()
    tagged = 0
    failed = 0
    for f in funds:
        try:
            tags = auto_tag_fund(db, f.fund_code)
            if tags:
                tagged += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"打标失败 {f.fund_code}: {e}")
            failed += 1
    return {"tagged": tagged, "failed": failed, "total": len(funds)}


def get_fund_tags(db: Session, fund_code: str) -> dict:
    """获取单只基金的所有标签"""
    tags = db.query(FundTag).filter(FundTag.fund_code == fund_code).all()
    result = {"industry": [], "theme": [], "style": [], "risk": []}
    for t in tags:
        if t.tag_type in result:
            result[t.tag_type].append({"id": t.id, "name": t.tag_name, "value": t.tag_value, "source": t.source})
    return result


def update_tag(db: Session, tag_id: int, tag_name: str = None, tag_value: float = None) -> FundTag | None:
    t = db.query(FundTag).filter(FundTag.id == tag_id).first()
    if not t:
        return None
    if tag_name:
        t.tag_name = tag_name
    if tag_value is not None:
        t.tag_value = tag_value
    t.source = "manual"
    db.commit()
    return t


def delete_tag(db: Session, tag_id: int) -> bool:
    t = db.query(FundTag).filter(FundTag.id == tag_id).first()
    if not t:
        return False
    db.delete(t)
    db.commit()
    return True


def create_manual_tag(db: Session, fund_code: str, tag_type: str, tag_name: str, tag_value: float = 1.0) -> FundTag:
    t = FundTag(fund_code=fund_code, tag_type=tag_type, tag_name=tag_name, tag_value=tag_value, source="manual")
    db.add(t)
    db.commit()
    return t
