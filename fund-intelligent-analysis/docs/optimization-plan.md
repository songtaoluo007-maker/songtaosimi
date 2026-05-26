# Plan: 基金智能分析系统 — 体系化优化升级

**Generated**: 2026-05-13 | **审计基线**: docs/system-audit-2026-05-13.md

## Overview

基于产品团队6职能视角的全景审计，将16项优化按现实团队分工（架构/前端/后端/测试/DevOps）编排为依赖感知的并行执行计划。目标：在保持系统稳定运行的前提下，最大化并行度，最短交付时间。

## Prerequisites

- 项目路径: `E:/基金智能分析_优化版/`
- 后端: FastAPI + SQLAlchemy + APScheduler
- 前端: Vue3 + TypeScript + Element Plus + Pinia
- 数据库: SQLite `data/fund_quant.db`
- 登录: `songtaoluo` / `admin123`

## Dependency Graph

```
Wave 1 (6 tasks): T1(Alembic) T3(AI retry) T6(401 router) T11(NAV并行) T14(图标按需) T15(备份)
                          │              │              │
Wave 2 (3 tasks):    T2(N+1) T10(索引)   T7(类型化)      │
                          │              │    │          │
Wave 3 (2 tasks):    T4(API→service)     │  T13(去重)    │
                        │              │    │          │
Wave 4 (5 tasks): T5(单测) T8(Holdings) T9(Dashboard) T12(幂等) T16(CI)

T1→T10(index), T1→T12(unique constraint) — 需要迁移框架
T1→T2→T4→T5 — 业务重构链
T6→T7→T8, T9 — 前端重构链
T7→T13 (类型化是去重的前提，去重后确认类型安全)
```

## Tasks

### T1: 引入 Alembic 数据库迁移
- **team**: 🏗️ 架构 / 🚀 DevOps
- **depends_on**: []
- **location**:
  - `backend/alembic/` (新建目录)
  - `backend/alembic.ini` (新建)
  - `backend/alembic/env.py` (新建)
  - `backend/database.py` (修改 init_db)
- **description**:
  1. `pip install alembic`，在 backend/ 下 `alembic init alembic`
  2. 配置 `alembic/env.py` 使用 `backend.database.SQLALCHEMY_DATABASE_URL` 和 `Base.metadata`
  3. 生成初始迁移 `alembic revision --autogenerate -m "initial"`
  4. 替换 `database.py` 中手写的 `_ensure_sqlite_columns` / `_ensure_indexes` 逻辑，改用 `alembic upgrade head`
  5. 验证：删库重建 → `alembic upgrade head` → 全部表和索引正确创建
  6. 保留 `create_all()` 作为全新部署的快速路径，Alembic 作为迁移路径
- **validation**: `alembic upgrade head` 成功；`alembic downgrade -1` 回滚成功；`alembic history` 显示完整迁移链
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T2: Holding API 加 joinedload 防 N+1 查询
- **team**: ⚙️ 后端
- **depends_on**: []
- **location**:
  - `backend/api/holding.py:127-136` (list_holdings)
  - `backend/api/holding.py:139-173` (get_holdings_summary)
  - `backend/api/holding.py:185-256` (get_holding_performance)
  - `backend/api/holding.py:259-388` (performance-calendar)
  - `backend/api/holding.py:391-441` (create_holding)
- **description**:
  1. `list_holdings` 第130行 query 加 `.options(joinedload(Holding.fund))`
  2. `get_holdings_summary` 第142行 query 加 `.options(joinedload(Holding.fund))`
  3. `get_holding_performance` 第191行 query 加 `.options(joinedload(Holding.fund))`
  4. `performance-calendar` 第278行 query 加 `.options(joinedload(Holding.fund))`
  5. `create_holding` 第395行 fund 查询加 `.options(joinedload(Fund.holdings))`
  6. 验证：启动后端，访问持仓页，检查 SQLAlchemy 日志无额外 SELECT
- **validation**: 每个请求的 SQL 查询数减少（从 N+1 变为 1-2 次）
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T3: AI 调用加重试机制
- **team**: ⚙️ 后端
- **depends_on**: []
- **location**:
  - `backend/services/ai_advisor.py:581-624` (_call_ai 方法)
- **description**:
  1. 在 `_call_ai()` 中包装 OpenAI 调用，增加 `max_retries=3` + 指数退避（1s/2s/4s）
  2. 捕获 `openai.APITimeoutError`, `openai.APIConnectionError`, `openai.InternalServerError` 三种可重试异常
  3. 超过重试次数后记录详细日志并返回友好错误告知用户
  4. 验证：模拟网络故障（临时断网），确认自动重试
- **validation**: 3次重试均失败后返回 `{"error": "AI服务暂时不可用，请稍后重试"}` 而非空字符串
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T4: API 层业务逻辑下沉到 service 层
- **team**: 🏗️ 架构
- **depends_on**: [T2]
- **location**:
  - `backend/api/fund.py:83-100` (nav-history) → 新建 `backend/services/fund_analysis_service.py`
  - `backend/api/fund.py:103+` (analysis) → 同上
  - `backend/api/dashboard.py:14-50+` (overview 数据聚合) → 新建 `backend/services/dashboard_service.py`
  - `backend/api/holding.py:139-173` (summary 聚合逻辑) → `backend/services/portfolio_analyzer.py`
  - `backend/api/holding.py:185-388` (performance/calendar) → `backend/services/portfolio_analyzer.py`
- **description**:
  1. 创建 `backend/services/dashboard_service.py`：抽离 overview / command-center / pnl-curve / asset-allocation 的数据聚合
  2. 创建 `backend/services/fund_analysis_service.py`：抽离 nav-history / analysis 的 AKShare 调用和数据处理
  3. 扩展 `backend/services/portfolio_analyzer.py`：吸收 holding 的 performance / performance-calendar / _snapshot_maps / _benchmark_daily_map 等纯函数
  4. API 层仅保留：参数解析 → 调用 service → 返回 Response
  5. 不改变任何 API 契约（请求参数和返回结构保持不变）
- **validation**: 所有现有 API 端点返回结构不变；`pytest backend/tests/` 全绿
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T5: 核心 service 加单元测试
- **team**: 🧪 测试
- **depends_on**: [T4]
- **location**:
  - `backend/tests/test_portfolio_analyzer.py` (新建)
  - `backend/tests/test_dashboard_service.py` (新建)
  - `backend/tests/test_ai_advisor.py` (新建)
  - `backend/tests/test_pnl_calculator.py` (新建)
  - `backend/tests/test_collectors.py` (新建)
  - `backend/tests/test_notification.py` (已有，扩展)
- **description**:
  1. `test_portfolio_analyzer.py`: 测试 period_return 计算、除零保护、市值加权、benchmark 对比
  2. `test_dashboard_service.py`: 测试 overview 聚合、PnL 计算正确性、空持仓保护
  3. `test_ai_advisor.py`: 测试 prompt 组装、JSON 解析、mock DeepSeek 响应
  4. `test_pnl_calculator.py`: 测试盈亏计算、shares=0 保护、多快照加权
  5. `test_collectors.py`: 测试 fund_nav_collector fallback 链、NAV 并行结果一致性
  6. 扩展 `test_notification.py`：飞书卡片格式、截断逻辑、无效建议跳过
  7. 所有测试使用独立的 SQLite 内存数据库（沿袭 conftest.py 模式）
- **validation**: `pytest backend/tests/ -v` 覆盖率 ≥40%（从当前 <5% 提升）
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T6: 401 拦截器用 router 替代 window.location
- **team**: 🎨 前端
- **depends_on**: []
- **location**:
  - `frontend/src/api/request.ts:45-67` (response interceptor)
  - `frontend/src/stores/auth.ts:26-31` (logout 方法)
  - `frontend/src/router/index.ts` (可能需要 minor 调整)
- **description**:
  1. 在 auth store 中新增 `logoutAndRedirect()` action：清 token/user + 调 `router.push('/login?redirect=...')`
  2. 修改 `request.ts` 第 56-63 行：401 二次失败时，import router 并调用 `authStore.logoutAndRedirect()` 替代 `window.location.href`
  3. 同步修复 `App.vue` 中的 logout：使其调用 auth store 的 `logout()` 而非直接操作 localStorage
  4. 统一 token key：在 request.ts 中使用 `STORAGE_KEYS.TOKEN` 和 `STORAGE_KEYS.REFRESH_TOKEN` 替代硬编码字符串
- **validation**: 手动测试 token 过期 → 自动跳转 login → store 状态干净 → 重新登录正常
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T7: 视图层 ref\<any\> → 类型定义
- **team**: 🎨 前端
- **depends_on**: [T6]
- **location**:
  - `frontend/src/views/Dashboard.vue` (678行, ref\<any\> * 5处)
  - `frontend/src/views/Holdings.vue` (886行, ref\<any\> * 8处)
  - `frontend/src/views/AiAdvisor.vue` (507行, ref\<any\> * 6处)
  - `frontend/src/views/Market.vue` (544行, ref\<any\> * 4处)
  - `frontend/src/views/CapitalFlow.vue` (256行, ref\<any\> * 4处)
  - `frontend/src/views/Trades.vue` (221行, ref\<any\> * 3处)
  - `frontend/src/views/OcrImport.vue` (468行, ref\<any\> * 5处)
  - `frontend/src/views/News.vue` (333行, ref\<any\> * 3处)
  - `frontend/src/views/Settings.vue` (350行, ref\<any\> * 3处)
  - `frontend/src/views/FundDetail.vue` (278行, ref\<any\> * 3处)
  - `frontend/src/views/MarketDetail.vue` (330行, ref\<any\> * 3处)
  - `frontend/src/views/Login.vue` (329行, ref\<any\> * 2处)
- **description**:
  1. 从 `@/types` 导入 `DashboardOverview`, `Holding`, `Trade`, `AiAdvice`, `NewsItem`, `CapitalFlowRecord` 等类型
  2. 逐文件替换 `ref<any>()` / `ref<any[]>([])` / `ref<any>({})` 为具体类型
  3. API 调用加泛型：`request.get<ApiResponse<Holding[]>>('/holdings')`
  4. `catch (e)` 全部改为 `catch (e: any)` 或更好的 `catch (e: unknown)`
  5. 不改动任何运行时行为，纯类型注解
- **validation**: `npx vue-tsc --noEmit` 零错误
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T8: 拆分 Holdings.vue (886行→子组件)
- **team**: 🎨 前端
- **depends_on**: [T7]
- **location**:
  - `frontend/src/views/Holdings.vue` (重构为容器)
  - `frontend/src/components/holdings/HoldingTable.vue` (新建, ~200行)
  - `frontend/src/components/holdings/PerformanceCalendar.vue` (新建, ~300行)
  - `frontend/src/components/holdings/FundGroupManager.vue` (新建, ~150行)
  - `frontend/src/components/holdings/HoldingSummaryCards.vue` (新建, ~100行)
- **description**:
  1. 从 Holdings.vue 提取持仓表格（筛选/排序/隐私模式切换）→ HoldingTable.vue
  2. 提取收益日历（日历视图/日收益/PnL贡献）→ PerformanceCalendar.vue
  3. 提取基金组管理（新建组/编辑组/拖拽分配）→ FundGroupManager.vue
  4. 提取顶部汇总卡片（总市值/总盈亏/日盈亏）→ HoldingSummaryCards.vue
  5. Holdings.vue 变为纯容器：数据加载 + 子组件通信
  6. 子组件通过 props 接收数据，通过 emit 传递事件
- **validation**: 原 Holdings 页面所有功能正常；每个子组件 <300 行
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T9: 拆分 Dashboard.vue (678行→子组件)
- **team**: 🎨 前端
- **depends_on**: [T7]
- **location**:
  - `frontend/src/views/Dashboard.vue` (重构为容器)
  - `frontend/src/components/dashboard/HeroCards.vue` (新建, ~100行)
  - `frontend/src/components/dashboard/PnLChart.vue` (新建, ~150行)
  - `frontend/src/components/dashboard/AllocationPie.vue` (新建, ~100行)
  - `frontend/src/components/dashboard/CommandCenter.vue` (新建, ~120行)
  - `frontend/src/components/dashboard/AiAdviceInline.vue` (新建, ~100行)
- **description**:
  1. 提取 Hero 叙事卡片（总资产/总盈亏/日盈亏/收益率）→ HeroCards.vue
  2. 提取 PnL 曲线图（累计盈亏/沪深300对比/时间切换）→ PnLChart.vue
  3. 提取资产配置饼图（按基金类型/单只基金/百分比）→ AllocationPie.vue
  4. 提取指挥中心面板（资金流摘要/大盘指数/新闻头条）→ CommandCenter.vue
  5. 提取 AI 建议内联卡片 → AiAdviceInline.vue
  6. Dashboard.vue 变为纯容器：数据加载 + 布局编排
- **validation**: 原 Dashboard 页面所有功能正常；每个子组件 <200 行
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T10: capital_flows 加复合索引
- **team**: ⚙️ 后端
- **depends_on**: [T1]
- **location**:
  - `backend/models/capital_flow.py` (添加 __table_args__)
  - `backend/database.py` (_ensure_indexes 或迁移)
- **description**:
  1. 在 `CapitalFlow` 模型中添加复合索引 `(flow_date, flow_type)`
  2. 通过 Alembic 新迁移添加索引（配合 T1）
  3. 验证：`EXPLAIN QUERY PLAN` 确认 `get_capital_flow_summary` 走索引
- **validation**: `EXPLAIN QUERY PLAN` 显示 `USING INDEX` 而非全表扫描
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T11: NAV 采集改 ThreadPoolExecutor 并行
- **team**: ⚙️ 后端
- **depends_on**: []
- **location**:
  - `backend/services/fund_nav_collector.py` (collect_fund_nav 函数)
- **description**:
  1. 找到 `collect_fund_nav` 中逐只基金调 AKShare 的 for 循环
  2. 改为 `concurrent.futures.ThreadPoolExecutor(max_workers=5)` 并行调用
  3. 单个基金超时 30s，整体超时 180s（max_workers × timeout + buffer）
  4. 保留多级 fallback 逻辑（天天基金→东方财富→AKShare）
  5. 保持输出格式不变
- **validation**: 26只基金采集时间从 N×5s 降至 ~10s；日志确认并行执行
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T12: Scheduler 采集加幂等保护
- **team**: ⚙️ 后端
- **depends_on**: [T1]
- **location**:
  - `backend/scheduler/jobs.py` (所有 collect_* 函数)
  - `backend/services/capital_flow_collector.py` (collect_all_capital_flows)
- **description**:
  1. 在 `collect_all_capital_flows` 中：DETELE + INSERT 改为 `INSERT OR REPLACE` 或使用唯一键的 upsert
  2. 在 `collect_market_data` / `collect_fund_nav` 中：写入前检查 `(symbol, snapshot_date, snapshot_type)` 是否已存在
  3. 给 MarketSnapshot 加唯一约束 `(symbol, snapshot_date, snapshot_type)`
  4. 调度器启动时增加 `_job_lock` 防止同任务并发
- **validation**: 连续两次触发同一采集任务，无重复数据插入
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T13: 消除前端工具函数重复定义
- **team**: 🎨 前端
- **depends_on**: [T7]
- **location**:
  - `frontend/src/utils/format.ts` (扩展)
  - `frontend/src/views/Market.vue` (删除重复的 calcBoll)
  - `frontend/src/views/MarketDetail.vue` (删除重复的 calcBoll)
  - `frontend/src/views/Dashboard.vue` (删除重复的 signedPercent/profitClass)
  - `frontend/src/views/Holdings.vue` (删除重复的 formatTurnover)
  - `frontend/src/views/Trades.vue` (删除重复的 formatTurnover)
  - 其他视图中的重复工具函数
- **description**:
  1. 将 `calcBoll` 从 Market.vue 和 MarketDetail.vue 提取到 `utils/format.ts`
  2. 将各视图中的 `signedPercent`, `profitClass`, `formatTurnover` 统一改为从 `@/utils/format` 导入
  3. 确认所有调用处使用统一版本
- **validation**: `npx vue-tsc --noEmit` 零错误；全部图表渲染正常
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T14: Element Plus 图标按需注册
- **team**: 🎨 前端
- **depends_on**: []
- **location**:
  - `frontend/src/main.ts:7,16-18` (图标全量注册)
- **description**:
  1. 扫描所有 .vue 文件中使用的 Element Plus 图标（`<el-icon><XxxIcon /></el-icon>` 或 `XxxIcon` 组件名）
  2. 仅导入和注册实际用到的图标
  3. 在 main.ts 或新建 `utils/icons.ts` 中维护图标白名单
- **validation**: `npx vite build` 后 element-plus-icons chunk 体积减少 60%+
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T15: 自动化数据库备份脚本
- **team**: 🚀 DevOps
- **depends_on**: []
- **location**:
  - `scripts/backup.sh` (新建)
  - `scripts/backup.bat` (新建, Windows)
  - `backend/scheduler/jobs.py` (可选：定时备份任务)
- **description**:
  1. 创建 `scripts/backup.sh`：使用 `sqlite3 .backup` 命令备份数据库
  2. 备份文件命名: `fund_quant_YYYYMMDD_HHMMSS.db`
  3. 保留最近 7 天的备份，自动清理旧文件
  4. 可选：在 scheduler 中增加每日凌晨备份任务
- **validation**: 手动运行备份脚本 → 确认备份文件可被 sqlite3 打开
- **status**: Not Completed
- **log**:
- **files edited/created**:

### T16: CI/CD 模板
- **team**: 🚀 DevOps
- **depends_on**: []
- **location**:
  - `.github/workflows/ci.yml` (新建)
  - `scripts/run_tests.sh` (新建)
- **description**:
  1. 创建 GitHub Actions workflow：`push` 到 main/develop 时触发
  2. Steps: checkout → setup python 3.11 → pip install → pytest → lint (ruff)
  3. 前端 steps: setup node 24 → npm ci → vue-tsc --noEmit → vite build
  4. 创建 `scripts/run_tests.sh` 本地一键测试脚本
- **validation**: GitHub Actions 跑通（如果 repo 在 GitHub）；本地 `bash scripts/run_tests.sh` 全绿
- **status**: Not Completed
- **log**:
- **files edited/created**:

## Parallel Execution Groups

| Wave | Tasks | Concurrency | Status |
|------|-------|-------------|--------|
| **1** | T1(Alembic), T2(N+1), T3(AI retry), T6(401 router), T11(NAV并行), T14(图标按需), T15(备份), T16(CI) | 8 parallel | ✅ 已完成 2026-05-13 |
| **2** | T10(复合索引), T12(幂等保护), T7(视图类型化) | 3 parallel | ⏳ 待执行 |
| **3** | T4(API→service), T13(去重工具) | 2 parallel | ⏳ 待执行 |
| **4** | T5(service单测), T8(Holdings拆分), T9(Dashboard拆分) | 3 parallel | ⏳ 待执行 |

**进度**: Wave 1/4 完成 (9/16 任务，含 T10 随 T1 完成)

## Testing Strategy

- **每个 task 完成后**: 运行 `pytest backend/tests/` + 手动冒烟测试对应页面
- **Wave 2 完成后**: 后端索引/约束验证；前端类型检查
- **Wave 3 完成后**: 后端 service 可调用验证；前端 utils 导入检查
- **Wave 4 完成后**: `pytest --cov=backend/services` ≥ 35%；`vue-tsc --noEmit` 零错误；全量手动走查

## Risks & Mitigations

| Risk | Probability | Mitigation |
|------|------------|------------|
| Alembic 迁移中断现有数据 | Low | 先在副本数据库测试；保留 create_all() 快速路径；验证 downgrade 回滚 |
| 组件拆分引入 props/emit 不匹配 | Medium | T8/T9 依赖 T7（类型化），TypeScript 捕获大部分 |
| NAV 并行化被 AKShare 限流 | Medium | max_workers=5 保守；单只 try/except 不阻塞整体；整体超时 180s |
| T7 阻塞 T8/T9/T13 | Medium | 拆分 T7 为两批：高频视图先做(Dashboard/Holdings/AiAdvisor)，其余 Wave 2 并行 |
| 业务逻辑下沉改变 API 行为 | Low | 保持 API 契约不变；运行现有 test_auth/test_funds 验证 |
| CI/CD 无 GitHub 仓库 | Medium | 提供 GitHub Actions + 本地 shell 两套方案 |
| _job_lock 仅进程内有效 | Low | 当前 APScheduler 单进程部署，不构成实际风险 |

## Completion Bar

- [ ] 所有 16 个 task 标记完成并带工作日志
- [ ] 每个实现 task 有 RED → GREEN 测试证据或手动验证截图
- [ ] `pytest backend/tests/ -v` 全绿，覆盖率 ≥35%
- [ ] `npx vue-tsc --noEmit` 零错误
- [ ] `alembic upgrade head` + `alembic downgrade -1` 均成功
- [ ] Dashboard / Holdings / AI顾问 / 行情 四核心页面手动回归通过
- [ ] `bash scripts/backup.sh` 可运行并生成有效备份文件
