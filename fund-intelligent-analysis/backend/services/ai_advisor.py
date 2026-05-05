"""
AI智能顾问服务
使用DeepSeek API，结合行情+持仓+新闻，生成加减仓建议
"""
import json
import traceback
from datetime import date, datetime, timedelta
from loguru import logger

from sqlalchemy.orm import Session
from backend.config import settings
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.news import News
from backend.models.ai_advice import AiAdvice
from backend.models.fund import Fund
from backend.models import trade as _trade_model  # ensure SQLAlchemy relationships are registered


SYSTEM_PROMPT = """你是一位专业、谨慎的私人基金投资顾问，擅长A股市场和公募基金持仓分析。你需要根据提供的市场行情、全球环境、投资者持仓和近期新闻，给出当天收盘前最后半小时可执行的持仓建议。

分析要求：
1. 综合分析当前市场环境，判断大盘短期趋势。
2. 逐个分析持仓基金，考虑基金类型、仓位占比、浮盈浮亏、盘中估值和近期新闻。
3. 额外识别“投资者尚未明显持有、但未来机会可能较大”的行业/概念板块，给出是否值得观察、分批建仓或暂不追高的建议。
4. 对未持仓机会的买入建议必须克制：只在热度、资金流、趋势、政策/新闻共振较明确时给 watch/buy；如果已经涨幅过大或数据不足，给 watch 而不是 buy。
5. suggested_ratio 表示建议调整金额占当前该基金市值的比例，hold 必须为 0；机会板块的 suggested_position_ratio 表示建议占总资产比例上限。
6. 如果数据不足，要明确降级信心和风险等级。
7. 这不是保证收益的指令，必须给出风险提示。
8. 必须严格遵守“交易日语境”：如果数据新鲜度显示 is_trading_day=false，不得使用“今日主力净流入”“今日涨跌”“今日行情”“今日尾盘”等措辞；应改用“最近交易日”“上一交易日”“休市期间复盘”等措辞。

输出格式要求：严格按照以下JSON格式输出，不要输出其他内容：
{
  "market_view": "bullish/neutral/bearish",
  "market_reasoning": "市场判断的推理依据",
  "risk_level": "low/medium/high",
  "actions": [
    {
      "fund_code": "基金代码",
      "fund_name": "基金名称",
      "action": "add/reduce/hold",
      "suggested_ratio": 0.1,
      "confidence": 0.75,
      "reason": "具体原因"
    }
  ],
  "opportunities": [
    {
      "board_type": "sector/concept",
      "name": "板块或概念名称",
      "action": "buy/watch/avoid",
      "suggested_position_ratio": 0.05,
      "confidence": 0.65,
      "entry_strategy": "分批/回调/突破/暂不追高等具体方式",
      "reason": "资金流、热度、趋势、新闻和与当前持仓互补性的依据",
      "risk": "主要风险"
    }
  ],
  "overall_suggestion": "总体建议，包含风险提示"
}
"""


class AiAdvisorService:
    def __init__(self, db: Session):
        self.db = db

    def generate_advice(self) -> dict:
        """生成AI投资建议"""
        # 1. 组装数据
        market_context = self._build_market_context()
        market_summary = self._build_market_summary(market_context)
        global_summary = self._build_global_summary()
        portfolio = self._build_portfolio_snapshot()
        opportunity_summary = self._build_opportunity_summary(market_context)
        news_summary = self._build_news_summary()
        data_quality = self._build_data_quality(market_context)

        # 检查是否有持仓
        if not portfolio:
            return {"error": "当前无持仓，请先添加持仓后再获取建议"}

        # 2. 组装Prompt
        user_prompt = f"""## 一、A股市场行情（{market_context['market_date_label']}）
{market_summary}

## 二、全球市场环境
{global_summary}

## 三、投资者当前持仓
{portfolio}

## 四、未持仓机会候选池
{opportunity_summary}

## 五、近期相关新闻
{news_summary}

## 六、数据新鲜度
{json.dumps(data_quality, ensure_ascii=False)}

请根据以上信息，给出今日收盘前最后半小时的持仓建议，并补充尚未明显持有但值得关注或分批买入的机会板块。"""
        if not market_context["is_trading_day"]:
            user_prompt += "\n\n特别注意：当前为A股休市日，本次建议是休市期间复盘建议。所有行情、资金流和板块热度只能表述为最近交易日数据，不得写“今日主力净流入”“今日涨跌”“今日尾盘”。"

        # 3. 调用AI API
        advice_content, model_name, token_usage = self._call_ai(user_prompt)

        if not advice_content:
            return {"error": "AI建议生成失败，请检查API Key配置"}

        # 4. 解析JSON
        actions = []
        opportunities = []
        market_view = "neutral"
        reasoning = ""
        overall = ""
        risk_level = "medium"

        try:
            parsed = json.loads(advice_content)
            if not market_context["is_trading_day"]:
                parsed = self._sanitize_temporal_language(parsed)
                advice_content = json.dumps(parsed, ensure_ascii=False)
            market_view = self._normalize_market_view(parsed.get("market_view", "neutral"))
            reasoning = parsed.get("market_reasoning", "")
            actions = self._normalize_actions(parsed.get("actions", []))
            opportunities = self._normalize_opportunities(parsed.get("opportunities", []))
            overall = parsed.get("overall_suggestion", "")
            risk_level = self._normalize_risk_level(parsed.get("risk_level", "medium"))
        except json.JSONDecodeError:
            logger.warning("AI返回内容非标准JSON，使用原始文本")
            overall = advice_content

        # 5. 存入数据库
        advice = AiAdvice(
            advice_date=date.today(),
            advice_time=datetime.now().time(),
            market_summary=market_summary,
            portfolio_snapshot=portfolio,
            advice_content=advice_content,
            actions=actions,
            market_view=market_view,
            overall_suggestion=overall,
            risk_level=risk_level,
            data_quality=data_quality,
            reasoning=reasoning,
            model_name=model_name,
            token_usage=token_usage,
            is_read=False,
        )
        self.db.add(advice)
        self.db.commit()
        self.db.refresh(advice)

        result = advice.to_dict()
        result["opportunities"] = opportunities
        return result

    def generate_close_advice(self) -> dict:
        """尾盘例行建议：刷新关键数据后生成AI建议。"""
        if settings.AI_ADVICE_PRE_REFRESH:
            self._refresh_close_data()
            self.db.expire_all()
        return self.generate_advice()

    def _refresh_close_data(self):
        """尾盘建议前刷新行情、板块、基金估值、新闻和盈亏。"""
        refresh_steps = [
            ("A股指数", "backend.services.market_collector", "collect_a_share_indices"),
            ("行业板块", "backend.services.market_collector", "collect_sectors"),
            ("概念板块", "backend.services.market_collector", "collect_concepts"),
            ("全球指数", "backend.services.global_index_collector", "collect_global_indices"),
            ("持仓基金估值", "backend.services.fund_nav_collector", "collect_fund_estimates"),
            ("财经新闻", "backend.services.news_collector", "collect_news"),
            ("持仓盈亏", "backend.services.pnl_calculator", "calculate_pnl"),
        ]
        import importlib

        for name, module_name, func_name in refresh_steps:
            try:
                module = importlib.import_module(module_name)
                getattr(module, func_name)()
            except Exception as e:
                logger.warning(f"尾盘建议前刷新{name}失败，继续使用已有数据: {e}")

    def _build_market_context(self) -> dict:
        today = date.today()
        try:
            from backend.services.market_collector import is_trading_day
            is_open_day = bool(is_trading_day())
        except Exception:
            is_open_day = today.weekday() < 5

        latest_market_date = self.db.query(MarketSnapshot.snapshot_date).filter(
            MarketSnapshot.snapshot_type.in_(["index", "sector", "concept"]),
        ).order_by(MarketSnapshot.snapshot_date.desc()).first()
        latest_date = latest_market_date[0] if latest_market_date else None
        market_date = today if is_open_day else (latest_date or today)
        label = f"今日 {today}" if is_open_day else "休市期间，展示最近可用交易数据"
        board_label = "交易日" if is_open_day else "最近交易日"
        return {
            "today": today,
            "is_trading_day": is_open_day,
            "latest_market_date": str(latest_date) if latest_date else None,
            "market_date": market_date,
            "market_date_label": label,
            "board_data_label": board_label,
        }

    def _build_market_summary(self, market_context: dict | None = None) -> str:
        """组装A股行情摘要"""
        market_context = market_context or self._build_market_context()
        market_date = market_context["market_date"]
        snapshots = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "index",
            MarketSnapshot.snapshot_date == market_date,
        ).order_by(MarketSnapshot.snapshot_time.desc()).all()

        if not snapshots:
            return f"暂无{market_context['board_data_label']}A股行情数据"

        # 去重取最新
        seen = set()
        lines = []
        for s in snapshots:
            if s.symbol not in seen:
                seen.add(s.symbol)
                change = float(s.change_pct or 0)
                sign = "+" if change >= 0 else ""
                lines.append(f"{s.name}: {float(s.price or 0):.2f} ({sign}{change:.2f}%)")

        # 板块TOP5
        sectors = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "sector",
            MarketSnapshot.snapshot_date == market_date,
        ).order_by(MarketSnapshot.change_pct.desc()).all()

        if sectors:
            lines.append("\n行业板块涨幅TOP5:")
            for s in sectors[:5]:
                lines.append(f"  {s.name}: +{float(s.change_pct or 0):.2f}%")
            lines.append("行业板块跌幅TOP5:")
            for s in sorted(sectors, key=lambda x: float(x.change_pct or 0))[:5]:
                lines.append(f"  {s.name}: {float(s.change_pct or 0):.2f}%")

        return "\n".join(lines)

    def _build_global_summary(self) -> str:
        """组装全球市场摘要"""
        snapshots = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "global",
        ).order_by(MarketSnapshot.snapshot_date.desc()).all()

        if not snapshots:
            return "暂无全球市场数据"

        seen = set()
        lines = []
        for s in snapshots:
            if s.symbol not in seen:
                seen.add(s.symbol)
                change = float(s.change_pct or 0)
                sign = "+" if change >= 0 else ""
                lines.append(f"{s.name}: {float(s.price or 0):.2f} ({sign}{change:.2f}%)")

        return "\n".join(lines)

    def _build_portfolio_snapshot(self) -> str:
        """组装持仓快照"""
        holdings = self.db.query(Holding).filter(Holding.is_active == True).all()

        if not holdings:
            return ""

        total_value = sum(float(h.current_value or 0) for h in holdings)
        total_cost = sum(float(h.cost_amount or 0) for h in holdings)
        total_pnl = total_value - total_cost

        lines = [f"总资产: {total_value:.2f} | 总成本: {total_cost:.2f} | 总盈亏: {total_pnl:.2f}", ""]

        for h in holdings:
            fund = self.db.query(Fund).filter(Fund.fund_code == h.fund_code).first()
            fund_type = fund.fund_type if fund else "未知"
            ratio = float(h.current_value or 0) / total_value * 100 if total_value > 0 else 0
            pnl_pct = float(h.pnl_ratio or 0)
            sign = "+" if pnl_pct >= 0 else ""

            lines.append(
                f"  {h.fund_code} {fund.fund_name if fund else ''} | "
                f"类型: {fund_type} | 份额: {float(h.shares or 0):.2f} | "
                f"成本: {float(h.cost_amount or 0):.2f} | 市值: {float(h.current_value or 0):.2f} | "
                f"盈亏: {sign}{pnl_pct:.2f}% | 占比: {ratio:.1f}%"
            )

        return "\n".join(lines)

    def _build_news_summary(self) -> str:
        """组装近期新闻摘要"""
        start_at = datetime.combine(
            date.today() - timedelta(days=settings.AI_NEWS_LOOKBACK_DAYS),
            datetime.min.time(),
        )

        news_list = self.db.query(News).filter(
            News.publish_time >= start_at,
        ).order_by(News.publish_time.desc()).limit(20).all()

        if not news_list:
            return "暂无近期新闻"

        lines = []
        for n in news_list[:15]:
            sentiment_map = {"positive": "利好", "negative": "利空", "neutral": "中性"}
            sentiment_label = sentiment_map.get(n.sentiment, "中性")
            pub_time = str(n.publish_time)[:16] if n.publish_time else ""
            lines.append(f"[{pub_time}] {n.title} | 情绪: {sentiment_label}")

        return "\n".join(lines)

    def _build_opportunity_summary(self, market_context: dict | None = None) -> str:
        """构建未持仓机会候选池：行业/概念热度、资金流、与当前持仓的重叠提示。"""
        market_context = market_context or self._build_market_context()
        board_label = market_context["board_data_label"]
        holdings = self.db.query(Holding).filter(Holding.is_active == True).all()
        held_text_parts = []
        for h in holdings:
            fund = self.db.query(Fund).filter(Fund.fund_code == h.fund_code).first()
            held_text_parts.extend([h.fund_code, fund.fund_name if fund else "", fund.fund_type if fund else ""])
        held_text = " ".join(part for part in held_text_parts if part)

        lines = [
            f"说明：以下是系统根据{board_label}行业/概念热度、主力净流入、涨跌幅筛选出的候选池；如果名称已明显出现在持仓基金主题中，应视为已有暴露，不要重复建议买入。",
            f"当前持仓主题关键词: {held_text or '暂无'}",
            "",
        ]

        try:
            from backend.services.market_collector import get_board_rankings

            for board_type, label in [("sector", "行业"), ("concept", "概念")]:
                ranking = get_board_rankings(board_type, 20)
                lines.append(f"{label}{board_label}热度Top10:")
                for item in ranking.get("heat_top", [])[:10]:
                    overlap = "可能已持有" if item.get("name") and item["name"] in held_text else "未见明显持仓"
                    lines.append(
                        f"  {item.get('name')} | 热度 {item.get('heat_score', 0):.0f} | "
                        f"涨跌 {item.get('change_pct', 0):+.2f}% | 主力净流入 {item.get('main_net_inflow', 0) / 1e8:+.2f}亿 | {overlap}"
                    )
                lines.append(f"{label}{board_label}资金流入Top10:")
                for item in ranking.get("inflow_top", [])[:10]:
                    overlap = "可能已持有" if item.get("name") and item["name"] in held_text else "未见明显持仓"
                    lines.append(
                        f"  {item.get('name')} | 主力净流入 {item.get('main_net_inflow', 0) / 1e8:+.2f}亿 | "
                        f"热度 {item.get('heat_score', 0):.0f} | 涨跌 {item.get('change_pct', 0):+.2f}% | "
                        f"领涨 {item.get('leading_stock', '')} | {overlap}"
                    )
                lines.append("")
        except Exception as e:
            logger.warning(f"机会候选池构建失败: {e}")
            lines.append(f"机会候选池暂不可用: {e}")

        return "\n".join(lines)

    def _build_data_quality(self, market_context: dict | None = None) -> dict:
        market_context = market_context or self._build_market_context()
        today = date.today()
        holdings_count = self.db.query(Holding).filter(Holding.is_active == True).count()
        latest_index = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "index",
            MarketSnapshot.snapshot_date == today,
        ).order_by(MarketSnapshot.snapshot_time.desc()).first()
        latest_fund = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "fund",
            MarketSnapshot.snapshot_date == today,
        ).order_by(MarketSnapshot.snapshot_time.desc()).first()
        recent_news_count = self.db.query(News).filter(
            News.publish_time >= datetime.combine(
                today - timedelta(days=settings.AI_NEWS_LOOKBACK_DAYS),
                datetime.min.time(),
            )
        ).count()

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_trading_day": market_context["is_trading_day"],
            "market_date_label": market_context["market_date_label"],
            "latest_market_date": market_context["latest_market_date"],
            "holdings_count": holdings_count,
            "latest_index_time": str(latest_index.snapshot_time) if latest_index else None,
            "latest_fund_estimate_time": str(latest_fund.snapshot_time) if latest_fund else None,
            "recent_news_count": recent_news_count,
            "news_lookback_days": settings.AI_NEWS_LOOKBACK_DAYS,
        }

    def _normalize_market_view(self, value: str) -> str:
        text = str(value or "").lower()
        if text in {"bullish", "看多", "偏多"}:
            return "bullish"
        if text in {"bearish", "看空", "偏空"}:
            return "bearish"
        return "neutral"

    def _normalize_risk_level(self, value: str) -> str:
        text = str(value or "").lower()
        if text in {"low", "medium", "high"}:
            return text
        if "高" in text:
            return "high"
        if "低" in text:
            return "low"
        return "medium"

    def _normalize_actions(self, actions: list) -> list:
        normalized = []
        for item in actions if isinstance(actions, list) else []:
            if not isinstance(item, dict):
                continue
            action = item.get("action", "hold")
            if action not in {"add", "reduce", "hold"}:
                action = "hold"
            suggested_ratio = float(item.get("suggested_ratio") or 0)
            if action == "hold":
                suggested_ratio = 0
            normalized.append({
                "fund_code": str(item.get("fund_code", "")),
                "fund_name": str(item.get("fund_name", "")),
                "action": action,
                "suggested_ratio": max(0, min(suggested_ratio, 1)),
                "confidence": max(0, min(float(item.get("confidence") or 0), 1)),
                "reason": str(item.get("reason", "")),
            })
        return normalized

    def _sanitize_temporal_language(self, payload):
        """休市日防止AI把最近交易日数据写成今日盘中数据。"""
        if isinstance(payload, dict):
            return {key: self._sanitize_temporal_language(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._sanitize_temporal_language(item) for item in payload]
        if not isinstance(payload, str):
            return payload
        replacements = {
            "今日尾盘": "休市期间",
            "今日主力": "最近交易日主力",
            "今日资金": "最近交易日资金",
            "今日行情": "最近交易日行情",
            "今日涨跌": "最近交易日涨跌",
            "今日": "最近交易日",
            "当天": "最近交易日",
        }
        text = payload
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _normalize_opportunities(self, opportunities: list) -> list:
        normalized = []
        for item in opportunities if isinstance(opportunities, list) else []:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "watch")).lower()
            if action not in {"buy", "watch", "avoid"}:
                action = "watch"
            board_type = str(item.get("board_type", "sector")).lower()
            if board_type not in {"sector", "concept"}:
                board_type = "sector"
            ratio = float(item.get("suggested_position_ratio") or 0)
            if action != "buy":
                ratio = 0
            normalized.append({
                "board_type": board_type,
                "name": str(item.get("name", "")),
                "action": action,
                "suggested_position_ratio": max(0, min(ratio, 0.3)),
                "confidence": max(0, min(float(item.get("confidence") or 0), 1)),
                "entry_strategy": str(item.get("entry_strategy", "")),
                "reason": str(item.get("reason", "")),
                "risk": str(item.get("risk", "")),
            })
        return normalized

    def _call_ai(self, user_prompt: str) -> tuple:
        """调用DeepSeek API"""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )

            response = client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=3200,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            model_name = response.model
            token_usage = response.usage.total_tokens if response.usage else 0

            return content, model_name, token_usage

        except Exception as e:
            logger.error(f"AI API调用失败: {e}\n{traceback.format_exc()}")
            return "", "", 0
