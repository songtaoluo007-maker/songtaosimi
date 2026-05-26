"""
飞书/多渠道通知服务
将AI建议格式化为飞书卡片消息并推送
"""
import json
from loguru import logger
from backend.config import settings


def send_advice_notification(advice: dict) -> dict:
    """发送AI建议通知到所有已配置渠道"""
    result = {"feishu": None}

    if not advice or advice.get("error"):
        logger.info("AI建议无效，跳过通知")
        return result

    if settings.FEISHU_WEBHOOK_URL:
        result["feishu"] = _send_feishu(advice)
    else:
        logger.info("飞书Webhook未配置，跳过通知")

    return result


def _send_feishu(advice: dict) -> dict:
    """构建并发送飞书交互式卡片"""
    import requests

    card = _build_feishu_card(advice)

    try:
        resp = requests.post(settings.FEISHU_WEBHOOK_URL, json=card, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") == 0:
            logger.info("飞书通知发送成功")
            return {"success": True}
        else:
            logger.warning(f"飞书通知发送失败: {body}")
            return {"success": False, "error": body}
    except Exception as e:
        logger.error(f"飞书通知发送异常: {e}")
        return {"success": False, "error": str(e)}


def send_investment_reminder(items: list[dict]) -> dict:
    """P1.1 — 定投到期提醒（每日 9:00 跑）

    items 形如 [{fund_code, plan_name, amount}, ...]
    """
    if not items:
        return {"feishu": None, "skipped": "无到期定投"}
    if not settings.FEISHU_WEBHOOK_URL:
        logger.info("飞书 Webhook 未配置，跳过定投提醒")
        return {"feishu": None}

    import requests

    title = f"📅 今日定投到期 · {len(items)} 笔"
    lines = ["**今天计划执行的定投：**", ""]
    total_amount = 0.0
    for it in items[:10]:
        amount = float(it.get("amount") or 0)
        total_amount += amount
        plan_name = it.get("plan_name") or it.get("fund_code", "")
        lines.append(f"• `{it.get('fund_code', '')}` {plan_name} — **¥{amount:,.2f}**")
    lines.append("")
    lines.append(f"合计 ¥{total_amount:,.2f} — 请在支付宝/天天基金 App 完成扣款后导入截图。")

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [{
                        "tag": "plain_text",
                        "content": "⚡ 基金智能分析系统 · 定投计划",
                    }],
                },
            ],
        },
    }

    result = {"feishu": None}
    try:
        resp = requests.post(settings.FEISHU_WEBHOOK_URL, json=card, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") == 0:
            logger.info(f"定投提醒推送成功 ({len(items)} 笔)")
            result["feishu"] = {"success": True}
        else:
            logger.warning(f"定投提醒推送失败: {body}")
            result["feishu"] = {"success": False, "error": body}
    except Exception as e:
        logger.error(f"定投提醒推送异常: {e}")
        result["feishu"] = {"success": False, "error": str(e)}
    return result


def send_manager_alert(alerts: list[dict]) -> dict:
    """P0.2 — 基金经理变更高优先级飞书推送

    alerts 形如 [{fund_code, alert_type, old_manager, new_manager, severity, detail}, ...]
    仅推送 severity == 'high' 的事件；其余仅写库，前端红点提示。
    """
    high = [a for a in (alerts or []) if a.get("severity") == "high"]
    if not high:
        return {"feishu": None, "skipped": "无高优先级预警"}

    result = {"feishu": None}
    if not settings.FEISHU_WEBHOOK_URL:
        logger.info("飞书 Webhook 未配置，跳过基金经理预警推送")
        return result

    import requests

    title = f"⚠️ 基金经理离职预警 · {len(high)} 起"
    md_lines = [
        "**以下持仓基金的现任经理变动，可能影响业绩稳定性：**",
        "",
    ]
    for a in high[:8]:
        md_lines.append(
            f"• `{a.get('fund_code', '')}` — {a.get('detail') or a.get('old_manager') or ''}"
        )
    md_lines.extend([
        "",
        "建议立即在系统中查看基金详情页 → 评估是否调仓。",
    ])

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "red",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(md_lines)}},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [{
                        "tag": "plain_text",
                        "content": "⚡ 数据来源：东方财富经理变动表 | 基金智能分析系统",
                    }],
                },
            ],
        },
    }

    try:
        resp = requests.post(settings.FEISHU_WEBHOOK_URL, json=card, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") == 0:
            logger.info(f"基金经理预警飞书推送成功 ({len(high)} 起)")
            result["feishu"] = {"success": True}
        else:
            logger.warning(f"基金经理预警飞书推送失败: {body}")
            result["feishu"] = {"success": False, "error": body}
    except Exception as e:
        logger.error(f"基金经理预警飞书推送异常: {e}")
        result["feishu"] = {"success": False, "error": str(e)}
    return result


def _build_feishu_card(advice: dict) -> dict:
    """将AI建议转为飞书卡片消息"""

    # 市场判断
    market_map = {"bullish": "🟢 看多", "bearish": "🔴 看空", "neutral": "🟡 中性"}
    risk_map = {"low": "低", "medium": "中", "high": "高"}

    market_view = market_map.get(advice.get("market_view", "neutral"), "中性")
    risk_level = risk_map.get(advice.get("risk_level", "medium"), "中")
    advice_date = advice.get("advice_date", "")

    # 操作建议
    actions_lines = []
    for a in advice.get("actions", []):
        action_map = {"add": "📈 加仓", "reduce": "📉 减持", "hold": "➡️ 持有"}
        action_label = action_map.get(a.get("action", "hold"), "持有")
        fund_name = a.get("fund_name", a.get("fund_code", "?"))
        ratio = a.get("suggested_ratio", 0)
        ratio_text = f" {ratio*100:.0f}%" if a.get("action") != "hold" else ""
        actions_lines.append(f"• {fund_name} → {action_label}{ratio_text}")

    # 机会板块
    opp_lines = []
    for o in advice.get("opportunities", [])[:5]:
        act = o.get("action", "watch")
        act_map = {"buy": "✅ 买入", "watch": "👀 观察", "avoid": "❌ 回避"}
        name = o.get("name", "?")
        opp_lines.append(f"• {name} → {act_map.get(act, '观察')}")

    # 组装 Markdown
    parts = []
    parts.append(f"**市场判断：**{market_view}　|　**风险：**{risk_level}")
    parts.append("")

    if actions_lines:
        parts.append("**📌 持仓建议**")
        parts.extend(actions_lines[:10])
        parts.append("")

    if opp_lines:
        parts.append("**🔍 未持仓机会**")
        parts.extend(opp_lines)
        parts.append("")

    overall = advice.get("overall_suggestion", advice.get("reasoning", ""))
    if overall:
        clean = overall.strip()
        if len(clean) > 500:
            clean = clean[:500] + "…"
        parts.append(f"💡 {clean}")

    md = "\n".join(parts)

    title = f"📊 基金AI尾盘建议 | {advice_date}" if advice_date else "📊 基金AI尾盘建议"

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": md},
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "⚡ AI生成，不构成投资指令 | 数据来源：基金智能分析系统",
                        }
                    ],
                },
            ],
        },
    }
