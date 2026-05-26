# 老基民视角产品升级方案

> **生成日期**：2026-05-26
> **作者视角**：5+ 年基金投资经验的资深基民
> **文档定位**：区别于 `optimization-plan.md`（技术架构）和 `v2-improvement-log.md`（bug 修复 + 体验优化），本文档聚焦**业务能力**的产品升级，让系统从"自动化分析工具"进化为"私人投资顾问"。

## 进度看板（最近更新：2026-05-26）

| 任务 | 状态 | 备注 |
|---|---|---|
| **P0.1 收益口径专业化** | ✅ 已完成 | XIRR / 最大回撤 / 当前回撤 / 基准对比，已接入 Dashboard + Holdings |
| **P0.2 基金经理信息 + 离职预警** | ✅ 已完成 | 东财爬取历任经理 + 周日 20:00 自动检测 + 飞书 high 预警 + Dashboard 红色横幅 |
| **P0.3 持仓重叠度 + 真实分散度** | ✅ 已完成 | AKShare 前十大持股 + 加权 Jaccard + 真实分散度评分 + 重叠热力图 + 重复重仓股榜 |
| **P1.1 定投计划 + 微笑曲线** | ✅ 已完成 | 日/周/双周/月 4 种周期 + 摊薄成本曲线 + 每日 9:00 飞书提醒 + 自动 reconcile trades |
| **P1.2 目标资产配置 + 再平衡** | ✅ 已完成 | 6 大类（A股/港股/海外/债/金/现金）目标 + 偏离检测 + 集成到风险暴露页 |
| **P1.3 个人化用户档案** | ✅ 已完成 | 用户画像（年龄/资金性质/目标/风险偏好）+ AI Prompt 注入 + 推荐配置生成器 |
| P2.1 费率账本 | 待启动 | |
| P2.2 用户决策复盘 | 待启动 | |
| P2.3 OCR 持续闭环 | 待启动 | |
| P2.4 老基民小工具集 | 待启动 | |

### P0.1 已上线文件清单

**后端（新增）**
- `backend/models/portfolio_snapshot.py` — PortfolioDailySnapshot + FundBenchmark 模型
- `backend/services/return_metrics_v3.py` — XIRR (Brent 法二分) + 最大回撤 + Beta/IR 算法
- `backend/api/holding_metrics_v3.py` — `/api/holdings/metrics/{xirr,drawdown,benchmark-compare,snapshot}` 四个端点
- `backend/alembic/versions/7c2b9a8e51d4_p0_return_metrics.py` — 数据库迁移

**后端（修改）**
- `backend/models/holding.py` — 加 `xirr / max_drawdown / max_drawdown_date / recovery_days` 4 列
- `backend/database.py` — 注册新模型让 create_all 创建表
- `backend/main.py` — 注册 holding_metrics router
- `backend/scheduler/setup.py` + `jobs.py` — 注册 `job_snapshot_portfolio_daily`（交易日 15:35 自动快照）
- `backend/api/dashboard.py` — `/command-center` 返回 portfolio_xirr / max_drawdown / current_drawdown / drawdown_peak_date / drawdown_trough_date

**前端（修改）**
- `frontend/src/api/index.ts` — 加 `getHoldingXirrMetrics / getHoldingDrawdownMetrics / getHoldingBenchmarkCompare`
- `frontend/src/views/Dashboard.vue` — Hero 区加 "年化 XIRR" / "最大回撤" / "当前回撤" 三块
- `frontend/src/views/Holdings.vue` — 列表加 XIRR / 最大回撤 / 恢复天数列，顶部摘要显示组合 XIRR

### P0.2 已上线文件清单

**后端（新增）**
- `backend/models/fund_manager.py` — FundManager + ManagerAlert 模型
- `backend/services/fund_manager_service_v3.py` — 东财爬虫 + 变更检测算法 + 飞书钩子
- `backend/api/fund_manager_v3.py` — 5 个端点（fund managers / sync / sync-all / list-alerts / mark-read）
- `backend/alembic/versions/a3e5c91d8f02_p0_fund_managers.py` — 数据库迁移

**后端（修改）**
- `backend/database.py` — 注册 `fund_manager` 模型
- `backend/main.py` — 注册 `fund_manager_router`
- `backend/scheduler/setup.py` — 注册 `sync_fund_managers`（每周日 20:00，长任务线程池）
- `backend/scheduler/jobs.py` — 加 `job_sync_fund_managers` 包装
- `backend/services/notification.py` — 加 `send_manager_alert`（飞书红色卡片推送 high 预警）

**前端（修改）**
- `frontend/src/api/index.ts` — 加 5 个经理 / 预警 API 函数
- `frontend/src/views/FundDetail.vue` — 新增 "基金经理" tab（现任 + 历任 + 立即拉取按钮）
- `frontend/src/views/Dashboard.vue` — 顶部加红色经理预警横幅 + 全部预警弹层

### P1.2 已上线文件清单

**后端（新增）**
- `backend/models/asset_allocation.py` — AssetAllocationTarget + RebalanceAlert 模型
- `backend/services/asset_allocation_service_v3.py` — 基金归类 + 偏离检测 + 预警生成
- `backend/api/asset_allocation_v3.py` — 7 个端点（targets / current / deviations / alerts / ack）
- `backend/alembic/versions/e4f1c82b9d76_p1_asset_allocation.py` — 迁移

**后端 / 前端（修改）**
- `backend/database.py` + `main.py` — 注册模型与路由
- `frontend/src/api/index.ts` — 加 7 个资产配置 API 函数
- `frontend/src/views/RiskExposure.vue` — 插入"目标资产配置（纪律工具）"卡片 + 编辑弹层

### P1.3 已上线文件清单

**后端（新增）**
- `backend/api/user_profile_v3.py` — GET / PUT / 推荐配置 3 个端点
- `backend/alembic/versions/f5b3a64e29d8_p1_user_profile.py` — 迁移：user_accounts 加 10 列

**后端（修改）**
- `backend/models/user.py` — 扩展 10 列画像字段 + `to_profile_dict()`
- `backend/services/ai_advisor.py` — `_build_context_json` 增加 `user_profile` 字段；SYSTEM_PROMPT 加入第 8 条画像约束规则
- `backend/main.py` — 注册 user_profile 路由

**前端（修改）**
- `frontend/src/api/index.ts` — 加 3 个画像 API 函数
- `frontend/src/views/Settings.vue` — 新增"用户画像"tab：完整表单 + 推荐配置展示

### P1.2 上线后用户能感受到的变化

| 之前 | 现在 |
|---|---|
| 没有"目标"概念，凭感觉调仓 | 设定 60% 股 / 30% 债 / 10% 金 类目标，每个大类带 tolerance 容差 |
| 不知道当前偏离了多少 | RiskExposure 顶部表格直观展示 目标/当前/偏离/建议金额 |
| 不知道再平衡需要操作多少钱 | 系统按"偏离 × 总市值"算出"建议加仓/减仓 ¥XXXX" |
| 不分大类，全混在一起 | 自动归类（fund_type + 名称关键词 → 6 大类） |

### P1.3 上线后用户能感受到的变化

| 之前 | 现在 |
|---|---|
| AI 给所有用户同一套建议 | AI Prompt 注入 user_profile：年龄 / 资金性质 / 风险偏好 / 目标年化 / 可承受回撤 |
| 紧急资金被推荐买权益 | 系统提示 AI："紧急资金 → 不建议加仓权益" |
| 临近退休还在追高 | 系统提示 AI："horizon < 5 年 → 减仓权益，转向稳健" |
| 没有起点参考 | "生成推荐配置" 按钮：基于 100-年龄法则 + 风险偏好微调，给出 6 大类初始建议 |

### P1.1 已上线文件清单

**后端（新增）**
- `backend/models/investment_plan.py` — InvestmentPlan + InvestmentPlanExecution 两个模型
- `backend/services/investment_plan_service_v3.py` — 计划 CRUD / 调度算法 / 微笑曲线 / 自动 reconcile trades / 每日到期检查
- `backend/api/investment_plan_v3.py` — 8 个端点（list/create/update/delete/upcoming/smile-curve/reconcile/check-due）
- `backend/alembic/versions/d9e2a7f15834_p1_investment_plans.py` — 迁移
- `frontend/src/views/InvestmentPlan.vue` — 新页面：顶部统计 + 待执行 + 卡片列表 + 微笑曲线弹层

**后端（修改）**
- `backend/database.py` — 注册 `investment_plan` 模型
- `backend/main.py` — 注册 `investment_plan_router`
- `backend/scheduler/setup.py` + `jobs.py` — 加 `check_investment_plans`（每日 9:00）
- `backend/services/notification.py` — 加 `send_investment_reminder`（飞书蓝色卡片）

**前端（修改）**
- `frontend/src/api/index.ts` — 加 8 个定投相关 API 函数
- `frontend/src/router/index.ts` — 加 `/investment-plans` 路由
- `frontend/src/App.vue` — 侧栏"核心"组加 "定投计划" Calendar 图标入口
- `frontend/src/utils/icons.ts` — 注册 Calendar / MoreFilled / Memo / Histogram / RefreshLeft / RefreshRight / WarningFilled 图标

### P1.1 上线后用户能感受到的变化

| 之前 | 现在 |
|---|---|
| 按一次买入建模，定投党看不到累计/期数/摊薄成本 | 卡片列表展示"已执行 N 期 / 目标 M 期 / 累计已投 / 摊薄成本 / 当前浮盈 %" |
| 不知道下一笔定投什么时候到期 | 顶部统计"今日待定投 X 笔 ¥Y / 本周 X 笔 ¥Y" + "未来 7 天即将到期"表 |
| 没有微笑曲线，看不到"定投点 vs 摊薄成本 vs 当前 NAV" | 微笑曲线弹层：基金净值折线 + 定投点 scatter + 摊薄成本水平线 + dataZoom 区间缩放 |
| 在支付宝/天天扣完款，系统不知道 | 每个计划"关联交易"操作：自动 diff trades 表里同日同代码买入，标记 executed=True |
| 容易忘记当日定投 | 每日 09:00 自动检查到期，飞书蓝色卡片提醒"今日定投到期 N 笔，合计 ¥XXX" |

### P0.3 已上线文件清单

**后端（新增）**
- `backend/models/fund_top_holding.py` — FundTopHolding 模型（fund × stock × quarter 唯一）
- `backend/services/overlap_analyzer_v3.py` — 加权 Jaccard 算法 + 分散度评分 + 重复重仓股
- `backend/services/fund_top_holdings_collector_v3.py` — AKShare 持股采集器 + quarter 解析
- `backend/alembic/versions/c7d8b3e94612_p0_fund_top_holdings.py` — 迁移

**后端（修改）**
- `backend/database.py` — 注册 `fund_top_holding` 模型
- `backend/api/risk_exposure.py` — 加 3 个端点（`/overlap` `/overlap/sync` `/overlap/sync/{code}`）
- `backend/scheduler/setup.py` + `jobs.py` — 加 `sync_fund_top_holdings`（每月 5 号 21:00，仅在 1/4/5/8/9/10/11 月跑）

**前端（修改）**
- `frontend/src/api/index.ts` — 加 3 个 overlap API
- `frontend/src/views/RiskExposure.vue` — 加 "实际分散度" 卡片：评分 / 平均重叠 / 热力图（HeatmapChart + VisualMapComponent）/ 重复重仓股 Top10

### P0.3 上线后用户能感受到的变化

| 之前 | 现在 |
|---|---|
| 5 只医药基金各 15% 被判"集中度正常" | 加权重叠 → 真实分散度评分（0-100），低于 60 直接红色警示 |
| 不知道两只基金底层有多少重叠 | 全屏热力图：N × N 矩阵，颜色越深重叠越高，hover 看具体百分比 |
| 不知道哪只股票被组合"过度暴露" | "重复重仓股 Top 10" 表：股票名 + 被几只基金持有 + 组合实际暴露 % |
| 季报披露后要手动刷新数据 | 每月 5 号自动跑（仅季报披露窗口月份），季后第一天就能看到新数据 |

### P0.2 上线后用户能感受到的变化

| 之前 | 现在 |
|---|---|
| 完全不知道基金经理是谁、任职多久 | FundDetail "基金经理" tab 展示现任 + 历任 + 任职回报 |
| 经理离职几个月才从坊间消息知道 | 每周日 20:00 自动检测，发现离职 → 飞书红色卡片 + Dashboard 顶部红色横幅 |
| 看不到经理任期里程碑 | 任职满 1/3/5 年自动产生 low 预警（不打扰但留痕） |
| 不清楚预警分级 | severity = high（离职）/ medium（新任）/ low（里程碑）三档分类 |

### P0.1 上线后用户能感受到的变化

| 之前 | 现在 |
|---|---|
| 收益率 = `(市值 - 成本) / 成本`，定投党会被高估 50% | XIRR 现金流加权年化，定投党看到真实回报率 |
| 看不到"从最高点跌了多少" | Hero 卡片直接显示"最大回撤 -12.4%，38 天恢复" + "当前回撤 -3.2%" |
| 沪深300 单一基准 | 每只基金可绑定专属基准（fund_benchmarks 表），可拆 α/β/信息比率 |
| 每只基金独立看不到时间维度 | Holding 表新增 4 列持久化，APScheduler 每交易日 15:35 自动快照组合市值，长期沉淀供回撤计算 |

---

## 0. 总览

### 0.1 目标用户画像

| 属性 | 画像 |
|---|---|
| 投资经验 | 5 年以上，经历过 2018 / 2022 两轮熊市 |
| 持仓规模 | 30-100 万人民币 |
| 操作习惯 | 70% 定投 + 30% 主动交易，每月调仓 1-2 次 |
| 主要平台 | 蚂蚁财富 + 天天基金 + 雪球 + 同花顺 iFinD |
| 核心诉求 | "我每天打开它，能让我做出更好的决策、避开人性弱点" |

### 0.2 现状评估（用户视角）

| 维度 | 现状评分 | 备注 |
|---|---|---|
| 数据采集（行情/新闻/估值） | ⭐⭐⭐⭐ | 比较扎实 |
| AI 建议 | ⭐⭐⭐ | 偏学院派，缺乏个性化 |
| 持仓管理 | ⭐⭐⭐ | 能用，但收益口径不专业 |
| 风险分析 | ⭐⭐ | 集中度算法不准（医药基金 × 5 算分散） |
| 复盘 | ⭐⭐ | 只复盘 AI 建议命中率，不复盘用户决策 |
| **基金经理信息** | ❌ | **完全缺失，老基民第一关心** |
| **定投支持** | ❌ | 按一次性买入建模 |
| **纪律性工具** | ❌ | 无目标配置、无再平衡、无止盈线 |
| **费率账本** | ❌ | 长期成本黑洞 |

### 0.3 升级路线图（P0 → P2）

```
P0 — 收益真相 + 基金经理 + 真实分散度  (4-6 周，最高优先级)
       │
       ▼
P1 — 定投 + 资产配置 + 个人化档案     (4-6 周，紧接着做)
       │
       ▼
P2 — 费率账本 + 决策复盘 + OCR闭环   (8-12 周，体验拉满)
       │
       ▼
P3 — 老基民小工具集                  (持续迭代)
```

### 0.4 V2 文件命名约定

本方案产出的新代码统一带 `_v3` 后缀（v1 原版 / v2 bug 修复 / **v3 产品升级**），与 v2 并存不冲突。

---

## P0 — 立刻就做的（4-6 周）

### P0.1 收益口径专业化 ⭐⭐⭐⭐⭐

#### 痛点
现有系统用 `(market_value - cost_amount) / cost_amount` 当收益率（见 [`backend/api/holding.py:147`](backend/api/holding.py:147)）。对定投基民来说这个数字**严重失真**：

- 1 年前一次买 10 万，今天市值 11 万 → 显示收益 10%（真实年化 10%）
- 12 个月每月定投 1 万共 12 万，今天市值 13.2 万 → 显示收益 10%（**真实年化 17%**）

老基民关心的真实指标：**XIRR 年化、最大回撤、回撤恢复天数、同类基准对比**。

#### 数据库 schema

**新增表 `portfolio_daily_snapshots`**（每日组合市值快照，用于回撤计算）：

```sql
CREATE TABLE portfolio_daily_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL UNIQUE,
    total_value DECIMAL(15,2) NOT NULL,
    total_cost  DECIMAL(15,2) NOT NULL,
    total_pnl   DECIMAL(15,2) NOT NULL,
    cash_flow   DECIMAL(15,2) DEFAULT 0,  -- 当日净申购金额（买入 - 卖出）
    note        TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_pds_date ON portfolio_daily_snapshots(snapshot_date);
```

**新增表 `fund_benchmarks`**（基金与基准指数关联）：

```sql
CREATE TABLE fund_benchmarks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code   VARCHAR(10) NOT NULL,
    benchmark_symbol VARCHAR(20) NOT NULL,  -- 如 '000932.CSI' 中证医药
    benchmark_name   VARCHAR(60),
    benchmark_type   VARCHAR(20),  -- 'broad' / 'industry' / 'theme' / 'custom'
    is_primary  BOOLEAN DEFAULT TRUE,
    auto_match  BOOLEAN DEFAULT TRUE,  -- 是否由系统自动归类
    UNIQUE(fund_code, benchmark_symbol)
);
```

**Holding 表新增字段**：

```sql
ALTER TABLE holdings ADD COLUMN xirr DECIMAL(8,4);        -- 单基金 XIRR
ALTER TABLE holdings ADD COLUMN max_drawdown DECIMAL(8,4); -- 最大回撤
ALTER TABLE holdings ADD COLUMN max_drawdown_date DATE;
ALTER TABLE holdings ADD COLUMN recovery_days INT;         -- 回撤恢复天数
```

#### 后端服务

**新建 `backend/services/return_metrics_v3.py`**：

```python
"""
专业收益指标计算服务

包含：
- XIRR 现金流加权年化收益率（scipy.optimize.brentq）
- 最大回撤 / 当前回撤 / 回撤恢复天数
- 夏普比率（年化超额收益 / 年化波动率）
- 同基准对比（α、β、信息比率）
"""
from datetime import date
from scipy.optimize import brentq

def xirr(cash_flows: list[tuple[date, float]]) -> float:
    """
    XIRR 算法
    cash_flows: [(date, amount), ...] 买入为负、卖出/最终市值为正
    返回：年化收益率（小数，如 0.083 = 8.3%）
    """
    def npv(rate):
        t0 = cash_flows[0][0]
        return sum(amt / (1 + rate) ** ((d - t0).days / 365.0) for d, amt in cash_flows)
    try:
        return brentq(npv, -0.99, 10.0, xtol=1e-6)
    except (ValueError, RuntimeError):
        return 0.0

def calc_max_drawdown(daily_values: list[tuple[date, float]]) -> dict:
    """
    最大回撤
    返回 {max_dd, peak_date, trough_date, recovery_days, current_dd}
    """
    if not daily_values:
        return {"max_dd": 0, "peak_date": None, "trough_date": None,
                "recovery_days": 0, "current_dd": 0}
    peak = daily_values[0][1]
    peak_date = daily_values[0][0]
    max_dd = 0
    max_peak_date = peak_date
    max_trough_date = peak_date
    recovery_days = 0
    for d, v in daily_values:
        if v > peak:
            peak = v
            peak_date = d
        dd = (peak - v) / peak if peak else 0
        if dd > max_dd:
            max_dd = dd
            max_peak_date = peak_date
            max_trough_date = d
    # 恢复天数：从 max_trough_date 起，距离再次创新高的天数
    for d, v in daily_values:
        if d >= max_trough_date and v >= peak:
            recovery_days = (d - max_trough_date).days
            break
    current_dd = (peak - daily_values[-1][1]) / peak if peak else 0
    return {
        "max_dd": round(max_dd * 100, 2),
        "peak_date": peak_date.isoformat(),
        "trough_date": max_trough_date.isoformat(),
        "recovery_days": recovery_days,
        "current_dd": round(current_dd * 100, 2),
    }

def calc_holding_xirr(db, fund_code: str) -> float:
    """单只基金 XIRR — 从 trades 表读现金流 + 当前市值收尾"""
    trades = db.query(Trade).filter(Trade.fund_code == fund_code).all()
    cash_flows = []
    for t in trades:
        amount = -float(t.amount) if t.trade_type == "买入" else float(t.amount)
        cash_flows.append((t.trade_date, amount))
    holding = db.query(Holding).filter(
        Holding.fund_code == fund_code, Holding.is_active == True,
    ).first()
    if holding:
        cash_flows.append((date.today(), float(holding.current_value or 0)))
    return xirr(cash_flows) if cash_flows else 0


def calc_portfolio_max_drawdown(db) -> dict:
    """组合最大回撤 — 从 portfolio_daily_snapshots 读"""
    from backend.models.portfolio_snapshot import PortfolioDailySnapshot
    rows = (
        db.query(PortfolioDailySnapshot)
        .order_by(PortfolioDailySnapshot.snapshot_date.asc())
        .all()
    )
    daily_values = [(r.snapshot_date, float(r.total_value)) for r in rows]
    return calc_max_drawdown(daily_values)
```

**APScheduler 增加每日组合快照任务**（[`backend/scheduler/jobs.py`](backend/scheduler/jobs.py)）：

```python
def job_snapshot_portfolio_daily():
    """每日 15:30 收盘后保存组合市值快照（驱动最大回撤计算）"""
    from backend.services.return_metrics_v3 import save_daily_snapshot
    save_daily_snapshot()
```

注册：`CronTrigger(day_of_week="mon-fri", hour=15, minute=30)`

#### API 端点

新增到 [`backend/api/holding.py`](backend/api/holding.py)（或新建 `holding_metrics_v3.py`）：

```
GET /api/holdings/metrics/xirr
  → 返回 {portfolio_xirr, per_fund: [{fund_code, xirr}], updated_at}

GET /api/holdings/metrics/drawdown
  → 返回 {portfolio: {max_dd, current_dd, peak_date, trough_date, recovery_days},
          per_fund: [{fund_code, max_dd, current_dd, recovery_days}]}

GET /api/holdings/metrics/benchmark-compare
  → 返回 {per_fund: [{fund_code, fund_return, benchmark_return, alpha, beta,
                      information_ratio, benchmark_name}]}
```

#### 前端展示

修改 [`frontend/src/views/Dashboard.vue`](frontend/src/views/Dashboard.vue) Hero 区域：

- 总盈亏旁加 **"年化 XIRR"** 大字（替换/补充原 `total_pnl_ratio`）
- 加一行**"最大回撤"卡片**：显示 `-12.4% (峰值 2025-03-15 → 谷底 2025-04-22, 恢复 38 天)`
- 加 **"当前回撤"** 提示：如距前高 -3.2%，提示"组合处于浅回撤区"

修改 [`frontend/src/views/Holdings.vue`](frontend/src/views/Holdings.vue)：

- 持仓列表增加列：XIRR / 最大回撤 / 同类排名 / α
- 每只基金可点击查看"持有期收益曲线 + 基准对比"

#### 工作量

| 任务 | 人天 |
|---|---|
| 数据库迁移（3 张表） | 0.5 |
| `return_metrics_v3.py` 服务 | 2 |
| 定时任务 + 历史回填脚本（从 trades 重建 daily snapshots） | 1 |
| API 端点 | 0.5 |
| 前端 Dashboard / Holdings 改造 | 2 |
| 基准对接（AKShare 同类指数行情） | 1.5 |
| **合计** | **7.5 天** |

---

### P0.2 基金经理信息 + 离职预警 ⭐⭐⭐⭐⭐

#### 痛点
**老基民买基金本质上是买基金经理**。系统目前 0 经理信息，致命缺失：

- 不知道基金经理是谁、任职几年、历史业绩
- 经理离职没预警 — 现实里很多基金"换将即坑"
- 不能"沿着经理跟踪" — 经理换到新基金，老粉丝跟过去

#### 数据库 schema

**新增表 `fund_managers`**：

```sql
CREATE TABLE fund_managers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code       VARCHAR(10) NOT NULL,
    manager_name    VARCHAR(60) NOT NULL,
    manager_id      VARCHAR(40),  -- 天天基金内部 ID
    start_date      DATE NOT NULL,
    end_date        DATE,  -- NULL = 现任
    tenure_return_pct DECIMAL(8,2),  -- 任职期间累计收益率
    tenure_annualized_pct DECIMAL(8,2),
    is_current      BOOLEAN DEFAULT TRUE,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, manager_name, start_date)
);
CREATE INDEX idx_fm_fund ON fund_managers(fund_code);
CREATE INDEX idx_fm_current ON fund_managers(is_current);
```

**新增表 `manager_alerts`**（变更预警）：

```sql
CREATE TABLE manager_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code   VARCHAR(10) NOT NULL,
    alert_type  VARCHAR(40) NOT NULL,  -- 'departure' / 'new_join' / 'tenure_milestone'
    old_manager VARCHAR(60),
    new_manager VARCHAR(60),
    alert_date  DATE NOT NULL,
    is_read     BOOLEAN DEFAULT FALSE,
    severity    VARCHAR(10),  -- 'high' / 'medium' / 'low'
    detail      TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ma_fund ON manager_alerts(fund_code, is_read);
```

#### 后端服务

**新建 `backend/services/fund_manager_service_v3.py`**：

```python
"""
基金经理信息采集 + 变更监控

数据源：
- AKShare: fund_manager_em (基金经理列表)
- AKShare: fund_individual_basic_info_xq (个基详情中的经理信息)
- 天天基金 fund.eastmoney.com/{code}.html 详情页正则提取

预警规则：
- 持仓基金的现任经理"end_date 由 NULL 变成非 NULL" → 离职预警（high）
- 持仓基金"新增基金经理" → 加入预警（medium）
- 现任经理任职满 1 年 / 3 年 / 5 年 → 里程碑通知（low）
"""
import re
import httpx
from datetime import date, datetime
from sqlalchemy.orm import Session
from loguru import logger

from backend.models.fund_manager import FundManager
from backend.models.manager_alert import ManagerAlert
from backend.models.holding import Holding


def fetch_managers_from_eastmoney(fund_code: str) -> list[dict]:
    """从东方财富基金详情页提取基金经理（含历任）"""
    url = f"https://fundf10.eastmoney.com/jjjl_{fund_code}.html"
    try:
        resp = httpx.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        # 正则解析现任 + 历任表
        managers = []
        for match in re.finditer(
            r'<tr>.*?<td>([\d-]+)</td>.*?<td>([\d-]*)</td>.*?<td>(.+?)</td>.*?'
            r'<td>(\d+年又?\d*天)</td>.*?<td>([\d.+\-%]+)</td>',
            resp.text, re.S,
        ):
            managers.append({
                "start_date": match.group(1),
                "end_date": match.group(2) or None,
                "manager_name": re.sub(r'<.*?>', '', match.group(3)).strip(),
                "tenure_str": match.group(4),
                "tenure_return_pct": _parse_pct(match.group(5)),
            })
        return managers
    except Exception as e:
        logger.warning(f"获取基金 {fund_code} 经理信息失败: {e}")
        return []


def sync_fund_managers(db: Session, fund_code: str) -> dict:
    """同步单只基金的经理列表，返回变更摘要"""
    new_data = fetch_managers_from_eastmoney(fund_code)
    if not new_data:
        return {"fund_code": fund_code, "alerts": []}

    existing = {m.manager_name: m for m in db.query(FundManager).filter(
        FundManager.fund_code == fund_code,
    ).all()}

    alerts = []
    new_current_names = {m["manager_name"] for m in new_data if not m["end_date"]}
    old_current_names = {name for name, m in existing.items() if m.is_current}

    # 离职检测：原现任不在新现任名单
    for departed in old_current_names - new_current_names:
        alerts.append({
            "type": "departure", "fund_code": fund_code,
            "old_manager": departed, "severity": "high",
            "detail": f"{departed} 不再担任 {fund_code} 基金经理",
        })
        existing[departed].is_current = False
        existing[departed].end_date = date.today()

    # 新任检测
    for joined in new_current_names - old_current_names:
        alerts.append({
            "type": "new_join", "fund_code": fund_code,
            "new_manager": joined, "severity": "medium",
            "detail": f"{joined} 新任 {fund_code} 基金经理",
        })

    # upsert
    for m in new_data:
        if m["manager_name"] not in existing:
            db.add(FundManager(
                fund_code=fund_code,
                manager_name=m["manager_name"],
                start_date=m["start_date"],
                end_date=m["end_date"],
                tenure_return_pct=m["tenure_return_pct"],
                is_current=not m["end_date"],
            ))

    # 写入预警
    for a in alerts:
        db.add(ManagerAlert(
            fund_code=a["fund_code"],
            alert_type=a["type"],
            old_manager=a.get("old_manager"),
            new_manager=a.get("new_manager"),
            alert_date=date.today(),
            severity=a["severity"],
            detail=a["detail"],
        ))

    db.commit()
    return {"fund_code": fund_code, "alerts": alerts}


def sync_all_holding_managers(db: Session) -> dict:
    """每周日 20:00 自动跑：检查所有持仓基金的经理变化"""
    codes = [h.fund_code for h in db.query(Holding).filter(Holding.is_active == True)]
    total_alerts = []
    for code in codes:
        result = sync_fund_managers(db, code)
        total_alerts.extend(result["alerts"])

    if total_alerts:
        # 高优先级预警走飞书
        high_alerts = [a for a in total_alerts if a["severity"] == "high"]
        if high_alerts:
            from backend.services.notification import send_manager_alert
            send_manager_alert(high_alerts)

    return {"checked": len(codes), "alerts": total_alerts}
```

**调度器注册**：

```python
# scheduler/setup.py
_scheduler.add_job(
    job_sync_managers,
    CronTrigger(day_of_week="sun", hour=20, minute=0),
    id="sync_managers", name="基金经理变更检测",
)
```

#### API 端点

```
GET /api/funds/{code}/managers
  → 返回 {current: [...], history: [...]}

GET /api/manager-alerts
  → 返回未读的所有经理变更预警

PUT /api/manager-alerts/{id}/read

POST /api/funds/{code}/managers/sync
  → 立即同步该基金的经理信息
```

#### 前端展示

**基金详情页 [`FundDetail.vue`](frontend/src/views/FundDetail.vue)** 新增"基金经理"卡片：

```
┌──────────────────────────────────────────────┐
│ 基金经理                          [查看全部历任] │
├──────────────────────────────────────────────┤
│ 张坤   现任    任职 4 年 2 个月   累计 +89.3% │
│ 周应波 历任    2018-2021         累计 +156.2%│
└──────────────────────────────────────────────┘
```

**Dashboard 加红点提示**：

侧边栏"AI 顾问"下加一个"经理变更" tab，未读 > 0 时显示红点。

**离职预警弹窗**：登录首屏弹窗"⚠️ 你持仓的 5 只基金中，2 只发生基金经理变更"。

#### 工作量

| 任务 | 人天 |
|---|---|
| 数据库 schema + 模型 | 0.5 |
| 经理信息爬虫（东财 + AKShare 双源） | 1.5 |
| 变更检测算法 + 预警写入 | 1 |
| 定时任务 + 飞书推送 | 0.5 |
| API 端点 | 0.5 |
| FundDetail / Dashboard 前端 | 1.5 |
| **合计** | **5.5 天** |

---

### P0.3 持仓重叠度 + 真实分散度 ⭐⭐⭐⭐

#### 痛点

现在 [`risk_exposure_service.py:106 get_concentration`](backend/services/risk_exposure_service.py:106) 用"单只基金占比 > 15%"判集中度。但老基民经典陷阱：

> 我买了 5 只医药基金，每只 15% — 系统说"分散得很好"，其实**整个组合就是一只医药基金**。

需要按**底层股票重叠度**衡量真实分散度。

#### 算法

利用现有的 [`fund.py:get_fund_analysis`](backend/api/fund.py:103) 中 `fund_portfolio_hold_em` 拿到的"基金前十大持仓股票"，构建：

```
对每对基金 (A, B):
  weighted_overlap = Σ min(A.weight[stock], B.weight[stock])  for stock in A∩B

整体重叠度 = avg(weighted_overlap)  for all pairs

真实分散度 = 1 - 整体重叠度
```

#### 数据库 schema

**新增表 `fund_top_holdings`**（缓存基金前十大持仓，避免每次 AKShare 调用）：

```sql
CREATE TABLE fund_top_holdings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code   VARCHAR(10) NOT NULL,
    stock_code  VARCHAR(10) NOT NULL,
    stock_name  VARCHAR(60),
    weight_pct  DECIMAL(6,3),  -- 占基金净值比例
    quarter     VARCHAR(10),    -- 如 '2025Q1'
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, stock_code, quarter)
);
CREATE INDEX idx_fth_fund_q ON fund_top_holdings(fund_code, quarter);
CREATE INDEX idx_fth_stock ON fund_top_holdings(stock_code);
```

每季度披露后定时刷新（4/8 月底）。

#### 后端服务

**新建 `backend/services/overlap_analyzer_v3.py`**：

```python
"""
持仓重叠度分析

输出：
- 两两重叠矩阵
- 整体加权重叠度
- 实际分散度（1 - 重叠度）
- 实际行业暴露（基于真实持股，而非基金类型标签）
- 重复持股 Top N（多只基金共同重仓的股票）
"""
from collections import defaultdict
from sqlalchemy.orm import Session

from backend.models.holding import Holding
from backend.models.fund_top_holding import FundTopHolding


def calc_pairwise_overlap(db: Session) -> dict:
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    fund_codes = [h.fund_code for h in holdings]
    total_value = sum(float(h.current_value or 0) for h in holdings)

    # {fund_code: {stock_code: weight_pct}}
    fund_holdings: dict[str, dict[str, float]] = defaultdict(dict)
    for row in db.query(FundTopHolding).filter(
        FundTopHolding.fund_code.in_(fund_codes),
    ).all():
        # 取最新季度
        fund_holdings[row.fund_code][row.stock_code] = float(row.weight_pct or 0)

    pairs = []
    overlap_sum = 0
    overlap_count = 0
    for i, a in enumerate(fund_codes):
        for b in fund_codes[i + 1:]:
            common = set(fund_holdings[a]) & set(fund_holdings[b])
            weighted = sum(
                min(fund_holdings[a][s], fund_holdings[b][s]) for s in common
            )
            pairs.append({
                "fund_a": a, "fund_b": b,
                "overlap_pct": round(weighted, 2),
                "common_count": len(common),
            })
            overlap_sum += weighted
            overlap_count += 1

    avg_overlap = overlap_sum / overlap_count if overlap_count else 0
    diversification = max(0, 100 - avg_overlap)

    # 重复重仓股
    stock_funds: dict[str, list[dict]] = defaultdict(list)
    for fund_code, holdings_map in fund_holdings.items():
        h = next((x for x in holdings if x.fund_code == fund_code), None)
        if not h:
            continue
        fund_weight = float(h.current_value or 0) / total_value if total_value else 0
        for stock_code, weight in holdings_map.items():
            stock_funds[stock_code].append({
                "fund_code": fund_code,
                "weight_in_fund": weight,
                # 该股票在组合中的实际暴露 = 基金占组合权重 × 股票占基金权重
                "exposure": round(fund_weight * weight, 2),
            })

    duplicated_stocks = []
    for stock_code, funds in stock_funds.items():
        if len(funds) >= 2:
            total_exposure = sum(f["exposure"] for f in funds)
            duplicated_stocks.append({
                "stock_code": stock_code,
                "fund_count": len(funds),
                "total_exposure_pct": round(total_exposure, 2),
                "via_funds": [f["fund_code"] for f in funds],
            })
    duplicated_stocks.sort(key=lambda x: x["total_exposure_pct"], reverse=True)

    return {
        "pairs": sorted(pairs, key=lambda x: x["overlap_pct"], reverse=True),
        "avg_overlap_pct": round(avg_overlap, 2),
        "diversification_score": round(diversification, 1),
        "duplicated_stocks": duplicated_stocks[:20],
        "warning": _build_warning(avg_overlap, duplicated_stocks),
    }


def _build_warning(avg_overlap: float, dup_stocks: list[dict]) -> str:
    if avg_overlap > 30:
        return f"组合实际分散度低 — 平均重叠 {avg_overlap:.1f}%，建议替换部分相似度高的基金"
    if dup_stocks and dup_stocks[0]["total_exposure_pct"] > 5:
        s = dup_stocks[0]
        return (f"单只股票暴露过高 — {s['stock_code']} 通过 {s['fund_count']} 只基金"
                f"合计暴露 {s['total_exposure_pct']:.1f}%")
    return "组合分散度良好"
```

#### API 端点

```
GET /api/risk-exposure/overlap
  → 返回 pairs / avg_overlap_pct / diversification_score / duplicated_stocks
```

#### 前端展示

修改 [`RiskExposure.vue`](frontend/src/views/RiskExposure.vue)：

- 增加"**真实分散度**"卡片，大字显示 1-100 评分
- "**重叠度热力图**"：N × N 矩阵，颜色越红重叠越高
- "**重复重仓股 Top 10**"表格：股票名 + 通过几只基金持有 + 合计暴露 %

#### 工作量

| 任务 | 人天 |
|---|---|
| schema + 模型 | 0.3 |
| 基金前十大持仓采集（每季度刷新） | 0.7 |
| 重叠度算法 | 1 |
| API | 0.3 |
| 前端热力图（echarts heatmap） | 1.5 |
| **合计** | **3.8 天** |

---

## P1 — 紧接着做（4-6 周）

### P1.1 定投计划 + 微笑曲线 ⭐⭐⭐⭐

#### 痛点

大部分基民是**定投**，不是一次买入。但系统按一次买入建模：

- 不能设置"每月 10 号扣 2000 买 005827"
- 没有"已定投 X 期 / 还有 Y 期"进度
- `cost_amount` 简单累加，看不到**定投微笑曲线**（这是定投党的灵魂图）

#### 数据库 schema

```sql
CREATE TABLE investment_plans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code       VARCHAR(10) NOT NULL,
    plan_name       VARCHAR(60),
    plan_type       VARCHAR(10) NOT NULL,  -- 'daily' / 'weekly' / 'monthly' / 'biweekly'
    amount          DECIMAL(10,2) NOT NULL,
    day_of_period   INT,  -- monthly=1-28, weekly=0-6（周一=0）
    start_date      DATE NOT NULL,
    end_date        DATE,  -- NULL = 长期
    target_amount   DECIMAL(12,2),  -- 总目标金额，自动算预计期数
    is_active       BOOLEAN DEFAULT TRUE,
    auto_execute    BOOLEAN DEFAULT FALSE,  -- 是否调用支付宝/天天接口自动定投（暂留扩展位）
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes           TEXT
);

CREATE TABLE investment_plan_executions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id         INTEGER NOT NULL,
    scheduled_date  DATE NOT NULL,
    executed        BOOLEAN DEFAULT FALSE,
    executed_at     DATETIME,
    trade_id        INTEGER,  -- 关联 trades.id
    skip_reason     TEXT,
    UNIQUE(plan_id, scheduled_date),
    FOREIGN KEY(plan_id) REFERENCES investment_plans(id)
);
```

#### 后端服务

**新建 `backend/services/investment_plan_v3.py`**：

```python
"""
定投计划管理 + 微笑曲线计算

功能：
- 计划 CRUD
- 每日 9:00 检查应执行的定投，发飞书提醒（持有人工执行）
- 自动 diff trades 与 plan_executions，关联实际买入到计划期
- 微笑曲线数据：每期 NAV + 累计份额 + 累计成本 + 摊薄成本
"""
def upcoming_executions(db, days_ahead: int = 7) -> list[dict]:
    """未来 N 天应执行的定投期数"""
    ...

def smile_curve_data(db, plan_id: int) -> dict:
    """
    定投微笑曲线
    返回：
    [
      {date, nav, cumulative_shares, cumulative_cost, average_cost, current_value, pnl},
      ...
    ]
    """
    ...

def daily_check_and_alert(db):
    """每日 9:00 跑一次"""
    today_due = db.query(InvestmentPlan).filter(
        InvestmentPlan.is_active == True,
        # ... 根据 plan_type + day_of_period 计算
    ).all()
    if today_due:
        from backend.services.notification import send_investment_reminder
        send_investment_reminder(today_due)
```

#### 前端

**新增页面 `frontend/src/views/InvestmentPlan_v3.vue`**：

- 顶部：今日待定投 / 本周待定投 / 本月已执行 X/Y 期
- 计划列表（卡片式）：基金名 / 周期 / 单期金额 / 累计已投 / 当前市值 / 摊薄成本 / 浮盈%
- 点击计划：**微笑曲线图**（NAV 折线 + 每期定投点 + 当前成本水平线）

#### 工作量

| 任务 | 人天 |
|---|---|
| schema + 模型 | 0.5 |
| 计划 CRUD + 服务 | 1.5 |
| 微笑曲线算法 + API | 1 |
| 飞书提醒 + 调度 | 0.5 |
| 前端页面 + ECharts 微笑曲线 | 2 |
| 路由 / 导航集成 | 0.3 |
| **合计** | **5.8 天** |

---

### P1.2 目标资产配置 + 再平衡提醒 ⭐⭐⭐⭐

#### 痛点

老基民都懂的纪律性工具：**目标 60% 股 / 30% 债 / 10% 黄金**，偏离 5% 自动提醒再平衡。系统目前完全没有。

#### 数据库 schema

```sql
CREATE TABLE asset_allocation_targets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_class     VARCHAR(20) NOT NULL,  -- 'equity_a' / 'equity_hk' / 'equity_us' / 'bond' / 'gold' / 'qdii' / 'cash'
    target_pct      DECIMAL(5,2) NOT NULL,
    tolerance_pct   DECIMAL(4,2) DEFAULT 5.0,
    notes           TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_class)
);

CREATE TABLE rebalance_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    detect_date     DATE NOT NULL,
    asset_class     VARCHAR(20) NOT NULL,
    target_pct      DECIMAL(5,2),
    current_pct     DECIMAL(5,2),
    deviation_pct   DECIMAL(5,2),
    suggested_action VARCHAR(20),  -- 'add' / 'reduce'
    suggested_amount DECIMAL(12,2),
    is_acknowledged BOOLEAN DEFAULT FALSE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 算法

```python
def compute_allocation_deviation(db) -> dict:
    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    total = sum(float(h.current_value or 0) for h in holdings)
    if not total:
        return {"current": {}, "deviations": []}

    current_by_class: dict[str, float] = defaultdict(float)
    for h in holdings:
        cls = _classify_fund_to_asset_class(h.fund)
        current_by_class[cls] += float(h.current_value or 0) / total * 100

    targets = {t.asset_class: t for t in db.query(AssetAllocationTarget).all()}
    deviations = []
    for cls, target in targets.items():
        cur = current_by_class.get(cls, 0)
        dev = cur - float(target.target_pct)
        if abs(dev) > float(target.tolerance_pct):
            deviations.append({
                "asset_class": cls,
                "current_pct": round(cur, 2),
                "target_pct": float(target.target_pct),
                "deviation_pct": round(dev, 2),
                "action": "reduce" if dev > 0 else "add",
                "suggested_amount": round(abs(dev) / 100 * total, 2),
            })

    return {"total_value": total, "current": current_by_class, "deviations": deviations}


def _classify_fund_to_asset_class(fund) -> str:
    """根据基金类型 + 投资范围归类资产大类"""
    ft = (fund.fund_type or "").lower()
    if "qdii" in ft or "海外" in ft or "美" in ft: return "equity_us"
    if "港股" in ft or "恒生" in ft: return "equity_hk"
    if "黄金" in ft or "贵金属" in ft: return "gold"
    if "债" in ft: return "bond"
    if "货币" in ft: return "cash"
    return "equity_a"  # 默认 A 股
```

#### 前端

**风险暴露页 [`RiskExposure.vue`](frontend/src/views/RiskExposure.vue) 加 tab "目标配置"**：

- 用户编辑目标百分比（环形图 + 滑块）
- 显示"当前 vs 目标"对比柱状图
- 偏离 > tolerance 时红色标注 + 推荐金额："建议加仓债基 ¥8,200"

#### 工作量：**3.5 天**

---

### P1.3 个人化用户档案 + AI 输入 ⭐⭐⭐⭐

#### 痛点

AI 顾问目前给所有用户同一套建议。但 30 岁攒首付 vs 60 岁退休养老，**完全不同的资金性质**。

#### 数据库 schema

```sql
ALTER TABLE users ADD COLUMN birth_year INT;
ALTER TABLE users ADD COLUMN retirement_target_year INT;
ALTER TABLE users ADD COLUMN investment_horizon_years INT;  -- 资金锁定期
ALTER TABLE users ADD COLUMN funds_purpose VARCHAR(30);  -- 'emergency' / 'house_down' / 'children_edu' / 'retirement' / 'long_term'
ALTER TABLE users ADD COLUMN target_annual_return DECIMAL(5,2);  -- 目标年化
ALTER TABLE users ADD COLUMN max_acceptable_drawdown DECIMAL(5,2);
ALTER TABLE users ADD COLUMN risk_appetite VARCHAR(20);  -- 'conservative' / 'balanced' / 'aggressive'
ALTER TABLE users ADD COLUMN monthly_disposable_income DECIMAL(10,2);  -- 月可投资收入
```

#### AI Prompt 注入

修改 [`ai_advisor.py:SYSTEM_PROMPT`](backend/services/ai_advisor.py:22) 增加用户档案段：

```
用户画像（必须结合该画像调整建议）：
- 年龄：{age}（资金期限：{horizon}年）
- 资金性质：{funds_purpose}（如紧急 / 首付 / 教育 / 养老）
- 目标年化：{target_annual_return}%
- 可承受最大回撤：{max_acceptable_drawdown}%
- 风险偏好：{risk_appetite}

调整规则：
- 紧急资金 / 短期目标 → 不建议加仓权益，优先现金/债券
- 临近退休（< 5 年）→ 减仓权益，转向稳健
- 当前回撤已接近用户可承受上限 → 不再推荐加仓
- 风险偏好"保守"且市场偏弱 → 优先推荐减仓而非"持有观察"
```

#### 前端

**新增"用户档案"页 `Profile_v3.vue`** 或集成到 [`Settings.vue`](frontend/src/views/Settings.vue)：

- 引导式向导：5 步问答（年龄→资金用途→投资期限→目标→风险偏好）
- 完成后自动生成"个人配置建议书"（推荐资产配置比例）

#### 工作量：**3 天**

---

## P2 — 中长期（8-12 周）

### P2.1 费率账本 ⭐⭐⭐

#### 痛点

10 年下来，主动基金的管理费就吞掉 14% 收益。但系统目前**完全不算费率**。

#### 数据库 schema

```sql
CREATE TABLE fund_fee_schedule (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code               VARCHAR(10) UNIQUE NOT NULL,
    purchase_fee_rate       DECIMAL(5,4),  -- 申购费率
    purchase_fee_discount   DECIMAL(4,3) DEFAULT 0.1,  -- 申购费打折（天天基金常 1 折）
    redemption_fee_schedule TEXT,  -- JSON: [{"min_days": 0, "max_days": 7, "rate": 0.015}, ...]
    management_fee_rate     DECIMAL(5,4),  -- 年管理费率
    custody_fee_rate        DECIMAL(5,4),  -- 年托管费率
    sales_service_fee_rate  DECIMAL(5,4),  -- C 类销售服务费
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fee_daily_accrual (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    accrual_date    DATE NOT NULL,
    fund_code       VARCHAR(10) NOT NULL,
    holding_value   DECIMAL(12,2),
    daily_mgmt_fee  DECIMAL(10,4),
    daily_custody_fee DECIMAL(10,4),
    daily_sales_fee DECIMAL(10,4),
    UNIQUE(accrual_date, fund_code)
);
```

#### 服务

```python
def daily_fee_accrual(db):
    """每日跑：按持仓市值 × 费率/365 计提费用"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    for h in holdings:
        fee_info = db.query(FundFeeSchedule).filter_by(fund_code=h.fund_code).first()
        if not fee_info:
            continue
        value = float(h.current_value or 0)
        db.add(FeeDailyAccrual(
            accrual_date=date.today(),
            fund_code=h.fund_code,
            holding_value=value,
            daily_mgmt_fee=value * float(fee_info.management_fee_rate or 0) / 365,
            daily_custody_fee=value * float(fee_info.custody_fee_rate or 0) / 365,
            daily_sales_fee=value * float(fee_info.sales_service_fee_rate or 0) / 365,
        ))
    db.commit()


def redemption_fee_estimate(db, fund_code: str, redeem_shares: float) -> dict:
    """预估赎回费 — 用户卖出前必看"""
    holding = db.query(Holding).filter_by(fund_code=fund_code, is_active=True).first()
    if not holding:
        return {"error": "未持有"}
    fee_info = db.query(FundFeeSchedule).filter_by(fund_code=fund_code).first()
    schedule = json.loads(fee_info.redemption_fee_schedule) if fee_info else []
    holding_days = (date.today() - holding.created_at.date()).days
    rate = next((s["rate"] for s in schedule
                 if s["min_days"] <= holding_days <= s.get("max_days", 99999)), 0)
    nav = float(holding.current_nav or 0)
    amount = redeem_shares * nav
    return {
        "holding_days": holding_days,
        "redemption_fee_rate": rate,
        "redemption_fee_amount": round(amount * rate, 2),
        "net_amount": round(amount * (1 - rate), 2),
    }
```

#### 前端

**新增 "费率账本" 页**：

- 顶部：今年累计被扣费 ¥X,XXX（占组合 X.X%）
- 按基金拆分：每只基金的年管理费 + 托管费 + 销售服务费
- "**赎回费预估器**"工具：选基金 + 输入份额 → 显示扣费

#### 工作量：**4 天**

---

### P2.2 用户决策复盘（替代 AI 命中率）⭐⭐⭐⭐

#### 痛点

现在 [`ai_advice_review`](backend/services/advice_review_service.py) 只复盘 "AI 建议命中率"。但用户真正关心的是 **"我自己的决策对不对"**。

#### 数据库 schema

```sql
CREATE TABLE user_decision_review (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    advice_id           INTEGER,
    decision_date       DATE NOT NULL,
    user_action         VARCHAR(20),  -- 'follow' / 'ignore' / 'reverse'
    market_state_then   VARCHAR(20),
    portfolio_value_then DECIMAL(12,2),
    -- 30 天后回填
    portfolio_value_30d DECIMAL(12,2),
    market_state_30d    VARCHAR(20),
    outcome             VARCHAR(20),  -- 'win' / 'loss' / 'neutral'
    outcome_pct         DECIMAL(6,2),
    lesson              TEXT,
    is_reviewed         BOOLEAN DEFAULT FALSE,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 服务输出

```python
def monthly_decision_report(db, month: str) -> dict:
    """
    月度决策复盘报告

    输出：
    - 本月你做了 X 次操作
    - 跟 AI 建议: 5 次（4 胜 1 负 → 胜率 80%）
    - 反 AI 建议: 2 次（0 胜 2 负 → 胜率 0%）
    - 高位加仓次数 + 后续结果
    - 低位减仓次数 + 后续结果（典型韭菜行为）
    - 长持不动 vs 频繁交易，哪个更赚？
    """
    ...
```

#### 前端

**AI 复盘页 [`AdviceReview.vue`](frontend/src/views/AdviceReview.vue) 增加 tab "我的决策"**：

- 月度报告卡片
- "**人性弱点雷达图**"：追涨杀跌 / 频繁交易 / 高位加仓 / 浮亏不止损（5 维评分）
- "**最让你后悔的 3 次决策**"

#### 工作量：**4 天**

---

### P2.3 OCR 持续闭环 ⭐⭐⭐

#### 痛点

用户在支付宝/天天基金继续操作时系统不知道。OCR 只是"一次性导入"。

#### 方案

- 每周一定时弹窗"请导入本周最新持仓截图"
- 自动 diff "上周 holdings vs 本次 OCR 解析结果"
- 识别新增/减少的份额 → 自动生成 trades 表记录（推断买入/赎回价格 = 当日 NAV）
- 用户确认后落库

#### 工作量：**2.5 天**

---

### P2.4 老基民必备小工具集 ⭐⭐⭐

每个独立工具，预计 0.5-1 天/个：

| 工具 | 功能 |
|---|---|
| **同公司基金转换计算器** | 在同基金公司之间转换，免赎回费、节省 1.5% |
| **持有时长里程碑提醒** | 7 天 / 30 天 / 365 天 / 2 年的赎回费门槛即将到达提醒 |
| **大额持有人变动监控** | 季报披露后，机构持仓比例突变 > 30% 预警 |
| **季报披露日历** | 4/8 月底自动追踪持仓基金的季报发布 |
| **分红方式管理** | 现金分红 vs 红利再投资，长期收益对比模拟 |
| **节假日提醒** | 长假前/后操作建议、避免节中无法赎回的资金占用 |
| **市场恐贪指数 + 你的情绪** | 接入百度指数 / 雪球热度，叠加用户操作频率 |

#### 工作量：**5 天**（小工具集合）

---

## 路线图与里程碑

### 时间表（按周）

| 周 | P0 | P1 | P2 |
|---|---|---|---|
| W1-W2 | P0.1 收益口径 | | |
| W3-W4 | P0.2 经理信息 | | |
| W4-W5 | P0.3 重叠度 | | |
| W6 | （P0 体验回归） | | |
| W7-W8 | | P1.1 定投 | |
| W9-W10 | | P1.2 资产配置 | |
| W10-W11 | | P1.3 个人化 | |
| W12 | | （P1 体验回归） | |
| W13-W14 | | | P2.1 费率账本 |
| W15-W16 | | | P2.2 决策复盘 |
| W17 | | | P2.3 OCR 闭环 |
| W18-W19 | | | P2.4 小工具集 |

### 里程碑验收标准

**M1（P0 完成）—— "看得懂"**
- [ ] 持仓页显示 XIRR 年化 / 最大回撤 / 当前回撤
- [ ] 基金详情页显示历任基金经理 + 离职预警
- [ ] 风险暴露页显示真实分散度评分 + 重叠度热力图

**M2（P1 完成）—— "管得住"**
- [ ] 定投计划支持 月/周/日 三种周期，飞书提醒到期
- [ ] 目标资产配置编辑界面 + 偏离 > 阈值时再平衡提醒
- [ ] 用户档案完整收集，AI 建议结合用户画像调整

**M3（P2 完成）—— "看得久"**
- [ ] 费率账本展示年累计被扣费金额
- [ ] 月度决策复盘 + 人性弱点雷达图
- [ ] OCR 自动 diff 生成交易记录
- [ ] 至少 5 个老基民小工具上线

---

## 总工作量汇总

| 模块 | 人天 |
|---|---|
| P0.1 收益口径 | 7.5 |
| P0.2 基金经理 | 5.5 |
| P0.3 重叠度 | 3.8 |
| P1.1 定投 | 5.8 |
| P1.2 资产配置 | 3.5 |
| P1.3 个人化 | 3.0 |
| P2.1 费率账本 | 4.0 |
| P2.2 决策复盘 | 4.0 |
| P2.3 OCR 闭环 | 2.5 |
| P2.4 小工具集 | 5.0 |
| **合计** | **44.6 人天** |

按个人 50% 时间投入计算，**约 4 个月可全部上线**。

---

## V3 文件命名约定

- 后端：`backend/services/return_metrics_v3.py`、`backend/api/holding_metrics_v3.py` 等
- 前端：`frontend/src/views/InvestmentPlan_v3.vue`、`Profile_v3.vue` 等
- 数据库：每个 P 阶段一个 Alembic 迁移版本（`xxx_p0_metrics.py` / `xxx_p1_planning.py` 等）

与现有 `_v2` 文件不冲突；待整体验证通过后，可统一去除版本后缀作为正式版本。

---

## 不在本方案范围（但值得记录）

- **接入券商/银行 API 自动交易** — 隐私和合规风险高，超出"私人本地工具"定位
- **多用户多账户** — 当前定位是单用户本地工具，不做
- **移动端 App** — Web 桌面端已能覆盖核心场景
- **社交功能（晒收益/跟单）** — 与"反人性纪律工具"理念冲突
