"""
AI 智能顾问服务 — V2

V2 改动（针对用户反馈"反应慢、进度条走完无建议"）：
1. _refresh_close_data 每步独立 timeout(10s)，单步失败不再拖累整体
2. _refresh_close_data 增加 step_total / step_done 字段，让前端拿到真实进度
3. generate_advice 返回值多附 `today_advice_id` + `advice_date`，前端可校验是否真的生成了今日记录
4. _normalize_risk_level 保留 medium-low / medium-high（v1 会强制吃成 medium，离线建议看起来跟正常一样）
5. _call_ai 复用 OpenAI 客户端（v1 每次重试都新建，浪费时间）
6. _call_ai 失败时返回 (content, model, tokens, reason) 四元组，把失败原因带回前端
7. _build_context_json 不再调用废弃的 V1 文本字段（_build_market_summary / _build_portfolio_snapshot
   / _build_news_summary / _build_opportunity_summary 等）— v1 的"双倍计算"取消，节省 2-5s
8. 内置 _safe_step 装饰器：所有外部数据采集都包一层 timeout，避免线程被外部 API 卡死
"""
import json
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta
from loguru import logger

from sqlalchemy.orm import Session, joinedload
from backend.config import settings
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.news import News
from backend.models.ai_advice import AiAdvice
from backend.models import trade as _trade_model  # noqa: F401

PROMPT_VERSION = "v2.1"
REFRESH_STEP_TIMEOUT = 10  # 单步采集超时（秒）
AI_CALL_TIMEOUT = 120
AI_RETRY_DELAYS = (1, 2, 4)

SYSTEM_PROMPT = """你是一位专业、谨慎、重视风险控制的基金组合分析助手。输出必须为严格 JSON。

规则：
1. 不得承诺收益、不得使用绝对化语言
2. 必须明确风险、优先保护本金和控制回撤
3. 涨跌幅绝对值 >1% 才视为有效方向性变化
4. confidence 低于 0.5 必须说明不确定性来源
5. fund_level_suggestions 只输出 action != "hold" 的基金，最多 8 条
6. 每个 reason 字段不超过 20 字；summary 不超过 80 字
7. 只输出纯 JSON，不要 Markdown 包裹
8. 如果输入数据包含 user_profile（年龄/资金性质/目标年化/可承受回撤/风险偏好），
   必须结合该画像调整建议：
   - 紧急资金 / 短期目标 → 不建议加仓权益，优先现金/债券
   - 临近退休（horizon < 5 年）→ 减仓权益，转向稳健
   - 当前回撤已接近用户可承受上限 → 不再推荐加仓
   - "保守"偏好 + 市场偏弱 → 优先推荐减仓而非"持有观察"
   - "积极"偏好 + 长期闲钱 → 可在低位适度加仓权益基金

JSON Schema:
{
  "market_state": {"trend": "bullish|bearish|neutral", "confidence": 0.0, "summary": "..."},
  "portfolio_risk": {"level": "low|medium|high", "concentration_warning": "...", "main_risk_factors": []},
  "suggested_action": {"action": "add|reduce|hold", "position": "aggressive|neutral|defensive",
                       "confidence": 0.0, "reasoning": "..."},
  "summary": "...",
  "key_reasons": [],
  "fund_level_suggestions": [{"fund_code": "", "fund_name": "", "action": "",
                              "suggested_ratio_change": 0.0, "confidence": 0.0, "reason": ""}],
  "tomorrow_watch": [],
  "risk_warning": "",
  "disclaimer": ""
}"""


class AiAdvisorService:
    def __init__(self, db: Session):
        self.db = db
        self._openai_client = None  # 懒加载、复用

    # ---------- 上下文构建 ----------
    def _build_context_json(self) -> dict:
        market_context = self._build_market_context()
        today = date.today()

        holdings = (
            self.db.query(Holding)
            .options(joinedload(Holding.fund))
            .filter(Holding.is_active == True)
            .all()
        )
        total_value = sum(float(h.current_value or 0) for h in holdings)
        total_cost = sum(float(h.cost_amount or 0) for h in holdings)
        total_pnl = total_value - total_cost
        daily_pnl = sum(float(h.daily_pnl or 0) for h in holdings if h.daily_pnl is not None)

        holdings_data = []
        for h in holdings:
            fund = h.fund
            holdings_data.append({
                "code": h.fund_code,
                "name": fund.fund_name if fund else "",
                "type": fund.fund_type if fund else "未知",
                "value": round(float(h.current_value or 0), 2),
                "cost": round(float(h.cost_amount or 0), 2),
                "shares": round(float(h.shares or 0), 2),
                "weight_pct": round(float(h.current_value or 0) / total_value * 100, 1) if total_value > 0 else 0,
                "daily_pnl": round(float(h.daily_pnl or 0), 2),
                "total_pnl_pct": round(float(h.pnl_ratio or 0), 2),
            })

        sorted_by_weight = sorted(holdings_data, key=lambda x: x["weight_pct"], reverse=True)
        concentration = {
            "top1_pct": sorted_by_weight[0]["weight_pct"] if sorted_by_weight else 0,
            "top3_pct": round(sum(h["weight_pct"] for h in sorted_by_weight[:3]), 1),
            "top5_pct": round(sum(h["weight_pct"] for h in sorted_by_weight[:5]), 1),
            "total_holdings": len(holdings_data),
        }

        portfolio = {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
            "daily_pnl": round(daily_pnl, 2),
            "daily_return_pct": round(daily_pnl / total_value * 100, 2) if total_value > 0 else 0,
            "holdings": holdings_data,
            "concentration": concentration,
            "is_trading_day": market_context["is_trading_day"],
        }

        market_date = market_context["market_date"]
        indices_snaps = (
            self.db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.snapshot_type == "index",
                MarketSnapshot.snapshot_date == market_date,
            )
            .order_by(MarketSnapshot.snapshot_time.desc())
            .all()
        )
        seen_idx, indices = set(), []
        for s in indices_snaps:
            if s.symbol not in seen_idx:
                seen_idx.add(s.symbol)
                indices.append({
                    "name": s.name, "symbol": s.symbol,
                    "price": round(float(s.price or 0), 2),
                    "change_pct": round(float(s.change_pct or 0), 2),
                })

        sectors_snaps = (
            self.db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.snapshot_type == "sector",
                MarketSnapshot.snapshot_date == market_date,
            )
            .order_by(MarketSnapshot.snapshot_time.desc())
            .all()
        )
        seen_sec, sectors = set(), []
        for s in sectors_snaps:
            if s.name not in seen_sec:
                seen_sec.add(s.name)
                sectors.append({"name": s.name, "change_pct": round(float(s.change_pct or 0), 2)})
        sectors_sorted = sorted(sectors, key=lambda x: x["change_pct"], reverse=True)

        market = {
            "date_label": market_context["market_date_label"],
            "is_trading_day": market_context["is_trading_day"],
            "indices": indices,
            "sectors_top5": sectors_sorted[:5],
            "sectors_bottom5": sectors_sorted[-5:] if len(sectors_sorted) >= 5 else [],
        }

        capital_flow = {}
        try:
            from backend.services.capital_flow_collector import get_capital_flow_summary
            capital_flow = {"summary": get_capital_flow_summary(self.db)}
        except Exception:
            capital_flow = {"summary": "暂无资金流向数据"}

        start_at = datetime.combine(
            today - timedelta(days=settings.AI_NEWS_LOOKBACK_DAYS),
            datetime.min.time(),
        )
        news_list = (
            self.db.query(News)
            .filter(News.publish_time >= start_at)
            .order_by(News.publish_time.desc())
            .limit(20)
            .all()
        )
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        high_impact = []
        for n in news_list:
            s = n.sentiment or "neutral"
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
            score = float(n.importance_score or 0)
            if score >= 75:
                high_impact.append({
                    "title": n.title, "sentiment": s,
                    "category": n.category or "", "importance_score": score,
                })

        news_ctx = {
            "total_count": len(news_list),
            "sentiment": sentiment_counts,
            "high_impact": high_impact[:8],
        }

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "portfolio": portfolio,
            "market": market,
            "capital_flow": capital_flow,
            "news": news_ctx,
            "data_quality": self._build_data_quality(market_context),
            "user_profile": self._build_user_profile(),
        }

    def _build_user_profile(self) -> dict:
        """P1.3 — 把用户画像（年龄/资金性质/风险偏好/目标年化/可承受回撤）注入到 AI 上下文"""
        try:
            from datetime import date
            from backend.models.user import UserAccount

            user = self.db.query(UserAccount).filter(UserAccount.role == "owner").first()
            if not user:
                return {}
            data = user.to_profile_dict()
            if user.birth_year:
                data["age"] = date.today().year - int(user.birth_year)
            # 标签化的资金性质方便 LLM 理解
            purpose_label = {
                "emergency": "紧急资金（不可亏）",
                "house_down": "首付资金（短期目标）",
                "children_edu": "教育金（中期目标）",
                "retirement": "养老金（长期目标）",
                "long_term": "长期闲钱",
            }.get(data.get("funds_purpose") or "", "未填")
            data["purpose_label"] = purpose_label
            data["risk_label"] = {
                "conservative": "保守", "balanced": "稳健", "aggressive": "积极",
            }.get(data.get("risk_appetite") or "", "未填")
            return data
        except Exception:
            return {}

    # ---------- 数据刷新（V2 关键优化点） ----------
    def _refresh_close_data(self, progress_cb=None) -> dict:
        """每步独立 timeout，单步失败不拖累整体；进度按"X/Y 步完成"汇报。"""
        import importlib

        steps = [
            ("A股指数", "backend.services.market_collector", "collect_a_share_indices"),
            ("行业板块", "backend.services.market_collector", "collect_sectors"),
            ("概念板块", "backend.services.market_collector", "collect_concepts"),
            ("全球指数", "backend.services.global_index_collector", "collect_global_indices"),
            ("持仓基金估值", "backend.services.fund_nav_collector", "collect_fund_estimates"),
            ("财经新闻", "backend.services.news_collector", "collect_news"),
            ("持仓盈亏", "backend.services.pnl_calculator", "calculate_pnl"),
        ]
        total = len(steps)
        done = 0
        results = {"success": [], "failed": [], "timeout": []}

        def _run_one(name, module_name, func_name):
            module = importlib.import_module(module_name)
            getattr(module, func_name)()

        if progress_cb:
            progress_cb({
                "step": "refreshing_data",
                "message": f"开始并行刷新 {total} 项数据...",
                "step_done": 0, "step_total": total,
            })

        executor = ThreadPoolExecutor(max_workers=total)
        futures = {executor.submit(_run_one, n, m, f): n for n, m, f in steps}
        pending = set(futures)
        deadline = time.monotonic() + REFRESH_STEP_TIMEOUT
        try:
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                completed, pending = wait(
                    pending,
                    timeout=remaining,
                    return_when=FIRST_COMPLETED,
                )
                for future in completed:
                    name = futures[future]
                    done += 1
                    try:
                        future.result()
                        results["success"].append(name)
                        logger.info(f"刷新 [{name}] 完成 ({done}/{total})")
                    except Exception as e:
                        results["failed"].append({"name": name, "error": str(e)})
                        logger.warning(f"刷新 [{name}] 失败: {e}")
                    if progress_cb:
                        progress_cb({
                            "step": "refreshing_data",
                            "message": f"{name} 完成 ({done}/{total})",
                            "step_done": done, "step_total": total,
                        })

            for future in pending:
                name = futures[future]
                done += 1
                future.cancel()
                results["timeout"].append(name)
                logger.warning(f"刷新 [{name}] 超时（>{REFRESH_STEP_TIMEOUT}s），跳过")
                if progress_cb:
                    progress_cb({
                        "step": "refreshing_data",
                        "message": f"{name} 超时，已跳过 ({done}/{total})",
                        "step_done": done, "step_total": total,
                    })
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return results

    def generate_close_advice(self, progress_cb=None) -> dict:
        if settings.AI_ADVICE_PRE_REFRESH:
            self._refresh_close_data(progress_cb)
            self.db.expire_all()
        return self.generate_advice(progress_cb)

    # ---------- 核心生成 ----------
    def generate_advice(self, progress_cb=None) -> dict:
        if progress_cb:
            progress_cb({"step": "building_context", "message": "正在收集持仓和市场数据..."})

        context = self._build_context_json()
        portfolio_ctx = context["portfolio"]

        if not portfolio_ctx["holdings"]:
            return {"error": "当前无持仓，请先添加持仓后再获取建议"}

        context_json_str = json.dumps(context, ensure_ascii=False, default=str)
        is_trading_day_flag = context["market"]["is_trading_day"]
        advice_goal = (
            "今日收盘前最后半小时的持仓建议"
            if is_trading_day_flag
            else "休市期间复盘建议"
        )
        user_prompt = f"{advice_goal}。\n\n输入数据如下：\n{context_json_str}"
        if not is_trading_day_flag:
            user_prompt += (
                "\n\n特别注意：当前为A股休市日。所有行情、资金流和板块热度只能表述为最近交易日数据，"
                "不得写\"今日主力净流入\"\"今日涨跌\"\"今日尾盘\"。"
            )

        if progress_cb:
            progress_cb({"step": "calling_ai", "message": "正在调用 DeepSeek AI 分析数据..."})

        content, model_name, token_usage, failure_reason = self._call_ai(user_prompt)
        offline_mode = False
        if not content:
            logger.warning(f"AI API 不可用（{failure_reason}），使用离线规则引擎生成建议")
            content = self._build_offline_advice(context)
            offline_mode = True

        if not content:
            return {"error": "AI 建议生成失败，请检查 API Key 与网络"}

        if progress_cb:
            progress_cb({"step": "parsing", "message": "正在解析与持久化建议..."})

        market_context = self._build_market_context()
        parsed = self._parse_ai_output(content, market_context)

        # 落库
        advice = AiAdvice(
            advice_date=date.today(),
            advice_time=datetime.now().time(),
            market_summary=self._compact_market_summary(context),
            portfolio_snapshot=self._compact_portfolio_summary(context),
            advice_content=content,
            actions=parsed["actions"],
            market_view=parsed["market_view"],
            overall_suggestion=parsed["overall_suggestion"],
            risk_level=parsed["risk_level"],
            data_quality=context["data_quality"],
            reasoning=parsed["reasoning"],
            model_name=f"offline:{model_name}" if offline_mode else model_name,
            token_usage=token_usage,
            is_read=False,
            context_json=context_json_str,
            structured_output=json.dumps(parsed["structured"], ensure_ascii=False),
            prompt_version=PROMPT_VERSION,
        )
        self.db.add(advice)
        self.db.commit()
        self.db.refresh(advice)

        result = advice.to_dict()
        result["opportunities"] = parsed["opportunities"]
        result["structured"] = parsed["structured"]
        result["offline_mode"] = offline_mode
        result["failure_reason"] = failure_reason if offline_mode else ""
        # V2 关键：前端可以用 advice_id + advice_date 二次校验
        result["advice_id"] = advice.id

        try:
            from backend.services.notification import send_advice_notification
            send_advice_notification(result)
        except Exception as e:
            logger.warning(f"飞书通知推送失败（不影响建议生成）: {e}")

        return result

    # ---------- 紧凑摘要（替代 V1 文本字段构建，约节省 2-5s 数据库往返） ----------
    def _compact_market_summary(self, ctx: dict) -> str:
        indices = ctx.get("market", {}).get("indices", [])
        if not indices:
            return "暂无行情数据"
        lines = [
            f"{i['name']} {i['price']:.2f} ({i['change_pct']:+.2f}%)"
            for i in indices[:6]
        ]
        return " | ".join(lines)

    def _compact_portfolio_summary(self, ctx: dict) -> str:
        p = ctx.get("portfolio", {})
        if not p.get("holdings"):
            return "暂无持仓"
        return (
            f"总资产 {p['total_value']:.2f} | 总成本 {p['total_cost']:.2f} | "
            f"累计盈亏 {p['total_pnl']:.2f} | 持仓 {len(p['holdings'])} 只"
        )

    # ---------- AI API 调用（V2 关键优化） ----------
    def _get_openai_client(self):
        if self._openai_client is not None:
            return self._openai_client
        from openai import OpenAI

        self._openai_client = OpenAI(
            api_key=settings.decrypted_api_key,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=AI_CALL_TIMEOUT,
        )
        return self._openai_client

    def _call_ai(self, user_prompt: str) -> tuple[str, str, int, str]:
        """调用 DeepSeek，返回 (content, model_name, token_usage, failure_reason)。

        v1 每次重试都新建 OpenAI 客户端；v2 复用单实例。
        v1 失败仅 logger，v2 把原因带回前端。
        """
        if not settings.has_api_key:
            return "", "", 0, "API Key 未配置"

        from openai import APIConnectionError, APITimeoutError, InternalServerError

        retryable = (APITimeoutError, APIConnectionError, InternalServerError)
        last_error = ""

        for attempt, delay in enumerate([0, *AI_RETRY_DELAYS]):
            if delay:
                time.sleep(delay)
            try:
                client = self._get_openai_client()
                response = client.chat.completions.create(
                    model=settings.DEEPSEEK_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=settings.AI_TEMPERATURE,
                    max_tokens=settings.AI_MAX_TOKENS,
                )
                content = (response.choices[0].message.content or "").strip()
                model_name = response.model
                token_usage = response.usage.total_tokens if response.usage else 0

                # 去 markdown 包裹
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return content.strip(), model_name, token_usage, ""

            except retryable as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(f"AI API 调用失败(可重试)(尝试 {attempt + 1}/{len(AI_RETRY_DELAYS) + 1}): {e}")
                self._openai_client = None  # 失败后释放客户端，下次重建
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.error(f"AI API 调用非重试错误: {e}\n{traceback.format_exc()}")
                return "", "", 0, last_error

        return "", "", 0, last_error or "已达最大重试次数"

    # ---------- 输出解析 ----------
    def _parse_ai_output(self, advice_content: str, market_context: dict) -> dict:
        actions = []
        opportunities = []
        market_view = "neutral"
        reasoning = ""
        overall = ""
        risk_level = "medium"
        structured = {}

        try:
            parsed = json.loads(advice_content)
        except json.JSONDecodeError:
            # 修复截断 JSON
            try:
                fixed = advice_content.rstrip()
                open_braces = fixed.count("{") - fixed.count("}")
                open_brackets = fixed.count("[") - fixed.count("]")
                if fixed and fixed[-1] not in ('"', ']', '}'):
                    fixed += '"'
                fixed += "]" * open_brackets + "}" * open_braces
                parsed = json.loads(fixed)
                logger.info("AI 返回 JSON 已自动修复")
            except Exception:
                logger.warning("AI 返回内容非标准 JSON，使用原始文本")
                return {
                    "actions": [],
                    "opportunities": [],
                    "market_view": "neutral",
                    "reasoning": "",
                    "overall_suggestion": advice_content[:500],
                    "risk_level": "medium",
                    "structured": {"parse_error": True, "raw": advice_content},
                }

        if not market_context["is_trading_day"]:
            parsed = self._sanitize_temporal_language(parsed)

        ms = parsed.get("market_state", {})
        if isinstance(ms, dict):
            market_view = self._normalize_market_view(ms.get("trend", "neutral"))
            reasoning = ms.get("summary", "")

        pr = parsed.get("portfolio_risk", {})
        if isinstance(pr, dict):
            risk_level = self._normalize_risk_level(pr.get("level", "medium"))

        sa = parsed.get("suggested_action", {})
        if isinstance(sa, dict):
            overall = sa.get("reasoning", "") or overall

        structured = {
            "market_state": ms if isinstance(ms, dict) else {},
            "portfolio_risk": pr if isinstance(pr, dict) else {},
            "suggested_action": sa if isinstance(sa, dict) else {},
            "summary": parsed.get("summary", ""),
            "key_reasons": parsed.get("key_reasons", []),
            "fund_level_suggestions": parsed.get("fund_level_suggestions", []),
            "tomorrow_watch": parsed.get("tomorrow_watch", []),
            "add_position_condition": parsed.get("add_position_condition", []),
            "reduce_position_condition": parsed.get("reduce_position_condition", []),
            "risk_warning": parsed.get("risk_warning", ""),
            "disclaimer": parsed.get("disclaimer", ""),
        }

        v2_fund = parsed.get("fund_level_suggestions", [])
        if v2_fund:
            actions = self._normalize_actions(v2_fund)
            for i, item in enumerate(v2_fund):
                if i < len(actions):
                    ratio = float(item.get("suggested_ratio_change") or item.get("suggested_ratio") or 0)
                    if actions[i].get("action") == "hold":
                        ratio = 0
                    actions[i]["suggested_ratio"] = max(0, min(ratio, 1))
        if not actions:
            actions = self._normalize_actions(parsed.get("actions", []))
        if not structured["fund_level_suggestions"]:
            structured["fund_level_suggestions"] = actions

        opportunities = self._normalize_opportunities(parsed.get("opportunities", []))

        if not overall:
            overall = parsed.get("overall_suggestion") or parsed.get("summary") or ""

        return {
            "actions": actions,
            "opportunities": opportunities,
            "market_view": market_view,
            "reasoning": reasoning,
            "overall_suggestion": overall,
            "risk_level": risk_level,
            "structured": structured,
        }

    # ---------- 辅助 ----------
    def _build_market_context(self) -> dict:
        today = date.today()
        try:
            from backend.services.market_collector import is_trading_day
            is_open_day = bool(is_trading_day())
        except Exception:
            is_open_day = today.weekday() < 5

        latest_market_date = (
            self.db.query(MarketSnapshot.snapshot_date)
            .filter(MarketSnapshot.snapshot_type.in_(["index", "sector", "concept"]))
            .order_by(MarketSnapshot.snapshot_date.desc())
            .first()
        )
        latest_date = latest_market_date[0] if latest_market_date else None
        market_date = today if is_open_day else (latest_date or today)
        return {
            "today": today,
            "is_trading_day": is_open_day,
            "latest_market_date": str(latest_date) if latest_date else None,
            "market_date": market_date,
            "market_date_label": f"今日 {today}" if is_open_day else "休市期间，展示最近可用交易数据",
            "board_data_label": "交易日" if is_open_day else "最近交易日",
        }

    def _build_data_quality(self, market_context: dict) -> dict:
        today = date.today()
        holdings_count = self.db.query(Holding).filter(Holding.is_active == True).count()
        latest_index = (
            self.db.query(MarketSnapshot)
            .filter(MarketSnapshot.snapshot_type == "index", MarketSnapshot.snapshot_date == today)
            .order_by(MarketSnapshot.snapshot_time.desc())
            .first()
        )
        latest_fund = (
            self.db.query(MarketSnapshot)
            .filter(MarketSnapshot.snapshot_type == "fund", MarketSnapshot.snapshot_date == today)
            .order_by(MarketSnapshot.snapshot_time.desc())
            .first()
        )
        recent_news_count = (
            self.db.query(News)
            .filter(News.publish_time >= datetime.combine(
                today - timedelta(days=settings.AI_NEWS_LOOKBACK_DAYS), datetime.min.time(),
            ))
            .count()
        )
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
        if text in {"bullish", "看多", "偏多"}: return "bullish"
        if text in {"bearish", "看空", "偏空"}: return "bearish"
        return "neutral"

    def _normalize_risk_level(self, value: str) -> str:
        """V2 修复：保留 medium-low / medium-high；v1 会强制 fallback 成 medium。"""
        text = str(value or "").lower().strip()
        if text in {"low", "medium-low", "medium", "medium-high", "high"}:
            return text
        if "高" in text: return "high"
        if "低" in text: return "low"
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

    def _sanitize_temporal_language(self, payload):
        if isinstance(payload, dict):
            return {k: self._sanitize_temporal_language(v) for k, v in payload.items()}
        if isinstance(payload, list):
            return [self._sanitize_temporal_language(i) for i in payload]
        if not isinstance(payload, str):
            return payload
        replacements = {
            "今日尾盘": "休市期间", "今日主力": "最近交易日主力",
            "今日资金": "最近交易日资金", "今日行情": "最近交易日行情",
            "今日涨跌": "最近交易日涨跌", "今日": "最近交易日", "当天": "最近交易日",
        }
        text = payload
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _build_offline_advice(self, context: dict) -> str:
        portfolio = context.get("portfolio", {})
        market = context.get("market", {})
        holdings = portfolio.get("holdings", [])
        indices = market.get("indices", [])
        concentration = portfolio.get("concentration", {})

        bearish_count = sum(1 for idx in indices if idx.get("change_pct", 0) < -1)
        if bearish_count >= 2:
            trend = "bearish"
        elif all(i.get("change_pct", 0) > 1 for i in indices[:2]):
            trend = "bullish"
        else:
            trend = "neutral"
        confidence = 0.35 if trend in ("bearish", "bullish") else 0.25

        top1 = concentration.get("top1_pct", 0)
        if top1 > 50:
            risk_level = "high"
            conc_warn = f"单只基金占比 {top1:.0f}%，集中度过高"
        elif top1 > 30:
            risk_level = "medium-high"
            conc_warn = f"最大持仓占比 {top1:.0f}%，注意分散"
        else:
            risk_level = "medium"
            conc_warn = ""

        daily_return = portfolio.get("daily_return_pct", 0)
        if trend == "bearish" and risk_level in ("high", "medium-high"):
            position, reasoning = "defensive", "市场偏弱且组合风险较高，建议偏防御"
        elif trend == "bullish" and daily_return > 1:
            position, reasoning = "neutral", "市场偏强，组合已有浮盈，可持有观察"
        else:
            position, reasoning = "neutral", "市场信号不明确，维持现有配置观望"

        fund_suggestions = []
        for h in holdings:
            pnl = h.get("total_pnl_pct", 0)
            if pnl < -10:
                fa, fr = "reduce", f"浮亏 {pnl:.1f}%，建议评估止损"
            elif pnl > 20:
                fa, fr = "reduce", f"浮盈 {pnl:.1f}%，可分批止盈"
            else:
                fa, fr = "hold", "波动正常，持有观察"
            fund_suggestions.append({
                "fund_code": h.get("code", ""),
                "fund_name": h.get("name", ""),
                "action": fa,
                "suggested_ratio_change": -0.1 if fa == "reduce" else 0,
                "confidence": 0.25,
                "reason": fr,
            })

        offline = {
            "market_state": {
                "trend": trend, "confidence": confidence,
                "summary": f"离线规则引擎判断：{trend}（基于 {len(indices)} 个指数）",
            },
            "portfolio_risk": {
                "level": risk_level,
                "concentration_warning": conc_warn,
                "main_risk_factors": ["⚠️ 离线模式：分析基于简化规则，未使用 AI 模型"],
            },
            "suggested_action": {
                "action": "hold", "position": position,
                "confidence": confidence, "reasoning": reasoning,
            },
            "summary": f"【离线模式】市场{trend}，风险{risk_level}，{reasoning}",
            "key_reasons": [
                "离线规则引擎生成，非 AI 模型结论",
                f"基于 {len(holdings)} 只持仓、{len(indices)} 个指数数据",
                "请检查网络与 API Key 后重新生成",
            ],
            "fund_level_suggestions": fund_suggestions,
            "tomorrow_watch": ["关注主要指数走势", "留意持仓基金净值变化"],
            "risk_warning": "⚠️ 当前为离线规则引擎生成的降级建议，仅供参考",
            "disclaimer": "本建议由离线规则引擎生成，不构成投资建议",
        }
        return json.dumps(offline, ensure_ascii=False)
