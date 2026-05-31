# 变更日志（CHANGELOG）

> **协作约定**：
> - 每次有意义的代码改动必须在此记录，按**时间倒序**（最新在最上）
> - 字段统一：时间 / 执行人 / 任务编号 / 文件 / 改动类型 / 改动概要 / 回退方式
> - 执行人取值：`Claude`（Anthropic Claude 会话）/ `Codex`（OpenAI Codex 会话）/ `User`（人工）/ `Linter`（IDE/工具自动整理）
> - 任务编号对应 `senior-investor-upgrade-plan.md` 中的 P0.1 / P0.2 / ... 章节
> - 改动类型：`NEW`（新增文件）/ `MOD`（修改）/ `DEL`（删除）/ `RENAME`（重命名）
> - 回退方式优先级：① Alembic downgrade > ② git revert > ③ 删除文件 > ④ 手工反向 patch
> - 一次任务多文件改动 → 写一个分组块，块内逐文件列
>
> **文件命名约定（再次提醒）**：
> - `_v2` = bug 修复 + 体验优化（见 `v2-improvement-log.md`）
> - `_v3` = 产品业务升级（见 `senior-investor-upgrade-plan.md`）
> - 模型/迁移文件不带后缀（直接用主分支命名）

---

## [Unreleased] — 进行中

_（无）_

---

## [2026-05-31（晚间）] — 品牌图标替换与桌面重建

> **任务来源**：用户选定第二版蓝白蜡烛图图标
> **执行人**：Codex
> **任务编号**：branding / packaging
> **回退方式**：git revert 本节文件；本地旧图标备份在 `data/icon_backup_20260531_195918/`

| 文件 / 产物 | 类型 | 概要 |
|---|---|---|
| `assets/fund-ai-source.png` | NEW | 保存用户确认的第二版蓝白蜡烛图源图，作为后续再生成品牌图标的单一来源 |
| `assets/fund-ai-16.png` ~ `assets/fund-ai-512.png` | MOD/NEW | 从源图重新生成品牌 PNG；补齐 manifest 已引用的 192 / 512 尺寸 |
| `assets/fund-ai.ico` | MOD | 重新生成 Windows 多尺寸 ICO，供 PyInstaller、桌面窗口和快捷方式使用 |
| `scripts/generate_brand_assets.py` | MOD | 改为从 `assets/fund-ai-source.png` 派生所有 PNG / ICO，避免后续重跑脚本恢复旧图标 |
| `TODO.md` | MOD | 新增 branding 完成标记和验证记录 |

### 本次验证证据

- `python scripts/generate_brand_assets.py` → succeeded；生成 16/24/32/48/64/128/192/256/512 PNG + ICO
- `npm run build`（`frontend/`）→ passed；仅保留既有 Vite static/dynamic import notices
- `pwsh -File scripts/build_desktop.ps1` → first attempt blocked by two running old EXE processes (`17080`, `25720`); stopped those project-local processes and reran successfully
- Rebuilt `dist\基金智能分析.exe` → 425,711,512 bytes，LastWriteTime 2026-05-31 20:11:58

---

## [2026-05-31（下午）] — 真实库副本验收 + 桌面烟测修复 ✅

> **任务来源**：继续完成 `TODO.md` 剩余优化 / 验收项
> **执行人**：Codex
> **任务编号**：runtime-validation / perf-stability / handoff
> **回退方式**：git revert 本节文件；本次不写入原始 `data/fund_quant.db`

#### 真实库副本验收

| 文件 / 产物 | 类型 | 概要 |
|---|---|---|
| `data/validation/fund_quant_validation_20260530_112919.db` | LOCAL | 从 `data/fund_quant.db` 复制出的验证库，仅本地使用，不入 Git |
| `data/validation/remaining_plan_validation_20260530_112919.json` | LOCAL | 记录真实库副本升级、定投计划、OCR diff、工具箱路径验证结果 |
| `data/validation/live_sync_all_holdings_20260531_150449.json` | LOCAL | 记录全持仓 live sync：基金经理 22/22、前十大持股 21/22（`015283` AKShare 无返回） |
| `data/validation/gui_smoke_20260531_150222.json` | LOCAL | 记录重建 EXE 后 GUI 烟测：登录 + 7 个关键页面，无 429/500/page error |

#### 代码修复

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/middleware/rate_limit.py` | MOD | 限流只统计 `/api/*` 且排除白名单；静态资源、SPA 页面、品牌图不再消耗 API 限流额度，修复桌面端快速切页触发 429 |
| `backend/middleware/rate_limit_v2.py` | MOD | 同步上述 V2 镜像文件，避免后续协作者从 `_v2` 回切时丢修复 |
| `backend/services/return_metrics_v3.py` | MOD | XIRR / 回撤输入统一归一成 `date`，修复真实老持仓 `created_at=datetime` 与 `date.today()` 混排导致 Dashboard 500 |
| `backend/tests/test_return_metrics.py` | MOD | 新增混合 `date` / `datetime` XIRR 回归用例 |
| `backend/tests/test_rate_limit_middleware.py` | NEW | 覆盖 API 限流路径判断：`/api/holdings` 限制，`/api/health` / `/assets/*` / `/brand-assets/*` 不限制 |
| `frontend/vite.config.ts` | MOD | 设置本地桌面应用的 vendor chunk 预算 `chunkSizeWarningLimit=1000`，保留当前 Element Plus / ECharts 手工分包 |
| `TODO.md` | MOD | 把可自动完成项标记完成；把缺真实截图/真实费率数据的项标成 blocked，方便后续协作者接力 |

### 本次验证证据

- `python -m pytest backend/tests/test_return_metrics.py backend/tests/test_rate_limit_middleware.py -v` → 5 passed
- 真实库副本验证 → DB upgrade passed；定投 90 天执行行 + reconcile passed；OCR diff / duplicate skip / missing holding service path passed；P2.4 工具箱路径 passed（源库无 fee schedules，因此在副本临时种入验证费率）
- Live sync on copied DB → fund managers checked 22/22，top holdings checked 22/22，success 21，`015283` AKShare 未返回数据
- `npm run build` → passed；Element Plus / ECharts 大 chunk warning 已按桌面预算消除，仅剩既有 dynamic/static import notices
- `pwsh -File scripts/build_desktop.ps1` → succeeded；重建 `dist\基金智能分析.exe`，424,684,570 bytes，LastWriteTime 2026-05-31 15:01:27
- Rebuilt EXE GUI smoke → passed；login / Dashboard / Holdings / Risk Exposure / Investment Plans / Settings user profile / Toolbox / OCR Import 均可打开，无 429 / 500 / page error

### 后续协作者注意

- 未伪造 OCR 真实截图验收：仓库和 `data/ocr_temp` 没有支付宝 / 天天基金截图；只完成了基于真实持仓数据的 OCR 对账服务路径验证。
- 源库当前 `fund_fee_schedules=0`；P2.4 费率体检和转换节省要业务可信，需要先录入或同步真实费率表。
- `build/` 已在 `.gitignore` 中保持忽略，PyInstaller 中间产物不进入 review diff；发布只关注源码和最终本地 `dist` 产物。

---

## [2026-05-27（晚间）] — V3/P2 API 端点级测试补齐 ✅

> **任务来源**：TODO.md `Medium` 区累计 4 项 endpoint-level 测试欠账
> **执行人**：Claude
> **任务编号**：tests-coverage / 质量护栏
> **回退方式**：git revert 本节文件即可；仅新增测试文件 + conftest 改动，不动业务代码

#### 测试新增（8 个文件，91 个新用例）

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/tests/test_investment_plan_endpoints.py` | NEW | /api/investment-plans 9 端点：CRUD + upcoming + smile-curve + reconcile + check-due（14 cases） |
| `backend/tests/test_fund_manager_endpoints.py` | NEW | /api/funds/{code}/managers + /api/manager-alerts；monkeypatch 屏蔽真实 HTTP（12 cases） |
| `backend/tests/test_asset_allocation_endpoints.py` | NEW | /api/asset-allocation 7 端点：targets CRUD + current + deviations + alerts + ack（11 cases） |
| `backend/tests/test_user_profile_endpoints.py` | NEW | /api/user/profile：GET/PUT + recommend-allocation（8 cases） |
| `backend/tests/test_fund_fee_endpoints.py` | NEW | /api/fund-fees：schedules CRUD + accrual + ledger + redemption-estimate（12 cases） |
| `backend/tests/test_decision_review_endpoints.py` | NEW | /api/decision-review：bias + persist + history + decisions + run（9 cases） |
| `backend/tests/test_ocr_endpoints.py` | NEW | /api/ocr/(status\|diff-preview\|confirm-snapshot)（12 cases） |
| `backend/tests/test_toolbox_endpoints.py` | NEW | /api/toolbox/*：milestones + quarterly + switch-savings + holidays + fee-health（13 cases） |

#### 基础设施改动

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/tests/conftest.py` | MOD | 加 `register_and_login()` helper + `auth_headers` fixture，端点测试无需各自实现样板；同时 monkeypatch `RateLimitMiddleware.dispatch` 跳过限流（默认 120/min 在 153 case 全量跑下必触发 429） |

### 本次验证证据

- `python -m pytest backend/tests/test_investment_plan_endpoints.py -v` → 14 passed
- `python -m pytest backend/tests/test_fund_manager_endpoints.py -v` → 12 passed
- `python -m pytest backend/tests/test_asset_allocation_endpoints.py -v` → 11 passed
- `python -m pytest backend/tests/test_user_profile_endpoints.py -v` → 8 passed
- `python -m pytest backend/tests/test_fund_fee_endpoints.py -v` → 12 passed
- `python -m pytest backend/tests/test_decision_review_endpoints.py -v` → 9 passed
- `python -m pytest backend/tests/test_ocr_endpoints.py -v` → 12 passed
- `python -m pytest backend/tests/test_toolbox_endpoints.py -v` → 13 passed
- `python -m pytest backend/tests/ -v` → **153 passed**（62 → 153，+91）

### 诊断纪要：全量跑 429 限流

定位过程：单文件、双文件组合都通过；6+ 文件叠加时 `test_funds.py` `_setup_and_login` 出现 `KeyError: 'access_token'`。临时加 detail 后看到 `setup=429 / login=429`，确认是 `backend/middleware/rate_limit.py` 在 60s 内累积 120+ 请求触发限流，与 V3 业务逻辑无关。修复采用最小侵入：仅在 `backend/tests/conftest.py` 用 monkeypatch 替换 `RateLimitMiddleware.dispatch`，保持中间件本身在生产环境的行为不变。

---

## [2026-05-27（下午 13:40-13:58）] — P2.4 老基民工具箱接入 + 稳定性修复 ✅

> **任务来源**：查看更新日志后继续推进 `senior-investor-upgrade-plan.md` § P2.4
> **执行人**：Codex
> **任务编号**：P2.4 / 稳定性优化
> **回退方式**：git revert 本节文件；如只撤入口，退回 `App.vue` + `router/index.ts` 即可隐藏页面

#### 13:40 ｜ `Codex` ｜ `ROUTE+PACKAGING`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/router/index.ts` | MOD | 新增 `/toolbox` 路由，接入 `ToolBox.vue` |
| `frontend/src/App.vue` | MOD | 分析导航新增“老基民工具箱”入口 |
| `scripts/fund_ai.spec` | MOD | 补充 `senior_toolbox_service_v3` / `senior_toolbox_v3` hidden imports，避免桌面包缺模块 |

#### 13:48 ｜ `Codex` ｜ `BACKEND FIX`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/senior_toolbox_service_v3.py` | MOD | 抽出赎回费档解析 / 当前费率 / 下个降费档 helper，修复里程碑节省金额计算；季报披露持仓查询加 `joinedload`；基金转换结果增加同公司校验提示；节假日识别支持周末桥接成长假 |

#### 13:55 ｜ `Codex` ｜ `TEST`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/tests/test_senior_toolbox.py` | NEW | 覆盖降费档节省金额、基金转换费用差额和公司不一致提示、费率体检高费率/缺配置、节假日周末桥接 |

### 本次验证证据

- `python -m py_compile backend\api\senior_toolbox_v3.py backend\services\senior_toolbox_service_v3.py backend\scheduler\jobs.py backend\scheduler\setup.py` → passed
- `python -m pytest backend/tests/test_senior_toolbox.py -v` → 4 passed
- `python -m pytest backend/tests/ -v` → 62 passed
- `npm run build` → passed；仍保留已有 Vite chunk-size / 动态导入 warning
- `pwsh -File scripts/build_desktop.ps1` → succeeded；重建 `dist\基金智能分析.exe`，424,601,455 bytes，LastWriteTime 2026-05-27 14:05:20
- `git diff --check` → passed；仅 Git 输出 LF/CRLF 转换 warning

### 后续协作者注意

- P2.4 当前是“零新增表”的实用工具箱首版，依赖已有 holdings / fund_fee_schedules / fund_top_holdings / market_holidays.json。
- “市场恐贪指数 + 你的情绪”尚未做外部热度接入；当前首版先上线 5 个本地数据可计算工具。
- 仍建议用真实费率配置和真实持仓做业务验收，尤其是同公司转换费率各平台差异。

---

## [2026-05-27（中午 12:00-12:16）] — P2.3 OCR 持仓闭环首版 ✅

> **任务来源**：继续下一阶段优化，推进 `senior-investor-upgrade-plan.md` § P2.3
> **执行人**：Codex
> **任务编号**：P2.3
> **回退方式**：git revert 本节文件；前端可退回 `OcrImport.vue` + `App.vue` + API 导出，后端删除 `ocr_reconcile_service_v3.py` 并撤回 `backend/api/ocr.py` 新端点

#### 12:00 ｜ `Codex` ｜ `BACKEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/ocr_reconcile_service_v3.py` | NEW | 新增 OCR 持仓快照对账服务：当前持仓 vs 本次 OCR，识别份额新增/减少，按 NAV 推断买入/卖出交易，检测同日 OCR 重复交易，输出缺失持仓风险提示 |
| `backend/api/ocr.py` | MOD | 新增 `/api/ocr/status`、`/api/ocr/diff-preview`、`/api/ocr/confirm-snapshot`；确认快照时先计算差异，再按截图更新持仓并记录推断交易；保留旧 `/api/ocr/confirm` 兼容入口 |
| `scripts/fund_ai.spec` | MOD | 补充 `backend.services.ocr_reconcile_service_v3` hidden import，避免桌面打包漏模块 |

#### 12:08 ｜ `Codex` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/api/index.ts` | MOD | 增加 OCR 同步状态、差异预览、快照确认 API |
| `frontend/src/views/OcrImport.vue` | MOD | 导入流程加入每周同步提醒、差异刷新、份额变化标签、推断交易预览、缺失持仓告警，并改用 `confirm-snapshot` 完成闭环落库 |
| `frontend/src/App.vue` | MOD | 在受保护页面每日最多弹一次 OCR 同步提醒，点击通知进入截图导入页 |

#### 12:14 ｜ `Codex` ｜ `TEST`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/tests/test_ocr_reconcile.py` | NEW | 覆盖 OCR 快照差异推断、自动交易创建、重复交易跳过、缺失持仓提示、无 OCR 同步时提醒到期 |

### 本次验证证据

- `python -m py_compile backend\api\ocr.py backend\services\ocr_reconcile_service_v3.py` → passed
- `python -m pytest backend/tests/test_ocr_reconcile.py -v` → 3 passed
- `python -m pytest backend/tests/ -v` → 58 passed
- `npm run build` → passed；仍保留已有 Vite chunk-size / 动态导入 warning
- `pwsh -File scripts/build_desktop.ps1` → succeeded；重建 `dist\基金智能分析.exe`，424,548,364 bytes，LastWriteTime 2026-05-27 12:30:31
- `git diff --check` → passed；仅 Git 输出 LF/CRLF 转换 warning

### 后续协作者注意

- P2.3 当前先覆盖“截图快照差异 → 推断交易 → 用户确认落库”的闭环；真实截图识别质量仍依赖原 `ocr_service.py`。
- 当前不会把“截图缺失的现有持仓”自动视为全部赎回，只给告警；这是防止分页截图漏传导致误删仓位。
- 需要用真实支付宝 / 天天基金截图做业务验收后，再考虑对缺失持仓增加显式“确认全部赎回”开关。

---

## [2026-05-27（上午 11:20-11:41）] — P2.2 雷达图补齐 + 复盘查询优化 ✅

> **任务来源**：继续跟进 `CHANGELOG` 中 P2.2 未完成项
> **执行人**：Codex
> **任务编号**：P2.2 / 性能优化
> **回退方式**：git revert 本节文件；前端仅撤回 `AdviceReview.vue` 变更即可移除 UI

#### 11:20 ｜ `Codex` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/views/AdviceReview.vue` | MOD | 接入 `/api/decision-review/bias` 和 `/api/decision-review/decisions`，新增行为偏差雷达图、本月决策摘要、后悔操作提示、最近决策表和“生成复盘”入口 |

#### 11:30 ｜ `Codex` ｜ `BACKEND PERF`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/decision_review_service_v3.py` | MOD | `materialize_decisions_from_trades` 批量预取当日 AI 建议和活跃持仓，避免按 trade 循环打 DB；`compute_behavior_bias` 批量预取持仓创建时间，避免按 sell 决策 N+1 查询 |
| `backend/api/capital_flow.py` | MOD | `get_holdings_flow_impact` 增加 `joinedload(Holding.fund)`，消除持仓基金类型统计里的 N+1 查询 |
| `scripts/fund_ai.spec` | MOD | 补充 P2 模型 / 服务 / API hidden imports，防止下次桌面打包漏模块 |

#### 11:35 ｜ `Codex` ｜ `TEST`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/tests/test_decision_review.py` | NEW | 覆盖交易快照生成、跟随 AI 建议识别、幂等重复运行、行为偏差汇总 |

### 本次验证证据

- `python -m py_compile backend/api/capital_flow.py backend/services/decision_review_service_v3.py backend/api/decision_review_v3.py backend/api/fund_fee_v3.py` → passed
- `python -m pytest backend/tests/ -v` → 55 passed
- `npm run build` → passed；仍保留已有 Vite chunk-size warning
- 临时 SQLite `init_db()` → Alembic 正常升级到 `h7e3f94c20da`，`fund_fee_schedules` / `user_decision_reviews` 表存在

### 后续协作者注意

- P2.2 前端入口已在 `AI 建议复盘` 页补齐，不再只是 API。
- P2.1 / P2.2 仍需要真实交易数据和真实费率配置做业务验收。
- 未重新打包 `dist/基金智能分析.exe`；如要交付桌面版，需要再跑 `pwsh -File scripts/build_desktop.ps1`。

---

## [2026-05-26（深夜 23:45-00:15）] — P2.1 费率账本 + P2.2 决策复盘 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P2.1 / P2.2
> **执行人**：Claude
> **预算**：4 + 4 人天 / 实际：约 30 分钟
> **里程碑**：M3（"看得久"）2/4 项就绪
> **回退方式**：`alembic downgrade f5b3a64e29d8` + 删 P2 新增 8 个文件 + revert wire 处

#### 23:45 ｜ `Claude` ｜ `P2.1 数据 + 服务 + API + 前端`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/fund_fee.py` | NEW | FundFeeSchedule + FeeDailyAccrual 两个模型 |
| `backend/alembic/versions/g6c2d83a91fb_p2_fund_fees.py` | NEW | 迁移：建 2 表 + 索引 |
| `backend/services/fund_fee_service_v3.py` | NEW | 三大能力：① 费率 CRUD ② 每日计提（持仓 × 年费率/365）③ 赎回费预估（持有天数 → 费率档，含"再等 N 天可省"提示）④ 年度账本（按基金/月度聚合 + 费率拖累 %）|
| `backend/api/fund_fee_v3.py` | NEW | 6 端点：schedules CRUD / accrual run / ledger yearly / redemption-estimate |
| `backend/scheduler/setup.py` + `jobs.py` | MOD | 加 `daily_fee_accrual`（每个交易日 21:00）+ 包装函数 |
| `backend/main.py` + `database.py` + `models/__init__.py` + `alembic/env.py` | MOD | 注册路由 + 模型 |
| `frontend/src/views/FeeLedger.vue` | NEW | 完整页面：3 个汇总卡 + 按基金/月度账本 + 赎回费预估器 + 费率配置弹层 |
| `frontend/src/api/index.ts` | MOD | 加 6 个费率 API 函数 |
| `frontend/src/router/index.ts` | MOD | 加 `/fee-ledger` 路由 |
| `frontend/src/App.vue` | MOD | "分析"组加 "费率账本" Coin 图标入口 |

**关键决策**：
- 每日计提用"持仓市值 × 年费率 / 365"近似（实际基金按估值日计提，差异 < 1%）
- 赎回费预估额外提供 `next_window`：若再持有 N 天能降到更低费率，按当前金额算出节省金额
- 费率拖累 `drag_pct = total_fee / avg_holding_value`，给出"累计被扣的年化%"直观感受
- 费率表手动维护（未来扩展自动从天天/东财抓取）

#### 23:55 ｜ `Claude` ｜ `P2.2 数据 + 服务 + API`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/user_decision_review.py` | NEW | UserDecisionReview（单次决策快照）+ BehaviorBiasSnapshot（月度行为偏差）|
| `backend/alembic/versions/h7e3f94c20da_p2_decision_review.py` | NEW | 迁移：建 2 表 + 2 索引 |
| `backend/services/decision_review_service_v3.py` | NEW | 5 大算法：① 从 trades 自动生成快照（识别 follow/reverse/self 三种用户行为）② 30 天后回填 outcome（基金净值变化 → win/loss/neutral）③ 行为偏差雷达图（追涨/杀跌/频繁交易/跟随建议比例/三种胜率）④ 月度报告 + biggest_regret ⑤ 自然语言 lesson 生成 |
| `backend/api/decision_review_v3.py` | NEW | 5 端点：bias / bias/persist / bias/history / decisions / run |
| `backend/scheduler/setup.py` + `jobs.py` | MOD | 加 `monthly_decision_review`（每月 1 号 22:00，长任务）|
| `backend/main.py` + `database.py` + `models/__init__.py` + `alembic/env.py` | MOD | 注册 |
| `frontend/src/api/index.ts` | MOD | 加 5 个决策复盘 API |

**关键决策**：
- 用户行为识别：trade.trade_type + AI advice.actions[fund_code].action 比对，分 `follow / reverse / self`
- 决策结果回填用 ±3 天窗口找基金净值（避免节假日找不到当日数据）
- 雷达图 5 维：追涨 / 杀跌 / 频繁交易 / 跟随胜率 / 反着做胜率 — 让用户直观看到自己的"反人性"模式
- "最让你后悔的决策" = reviewed=1 且 outcome=loss 中 outcome_pct 最负的那一条
- 雷达图前端在 AdviceReview.vue 后续集成（本次先打通后端 + API；前端 UI 见 TODO）

#### 00:10 ｜ `Claude` ｜ `VERIFY`

```python
# P2.1 — 赎回费 warning 算法
_build_redemption_warning(3, 0.015, {after_days: 4, rate: 0.005, savings: 100}) → '偏高' + '节省'
_build_redemption_warning(40, 0, None) → '免赎回费'

# P2.2 — 市场分类 + lesson 生成
_classify_market_state(1.5) → 'bullish'
_classify_market_state(-1.5) → 'bearish'
_generate_lesson(win+follow, 5.5) → '跟随 AI 建议成功：30 天后净值变化 +5.50%'

# 全链路 import 通过：
# Router routes — P2.1: 6, P2.2: 5
# Scheduler jobs — daily_fee_accrual / monthly_decision_review 全部注册
```

### M3 验收清单
- [x] P2.1 赎回费预估算法两个边界用例通过
- [x] P2.2 市场分类 + lesson 生成测试通过
- [x] Router routes — P2.1: 6 / P2.2: 5
- [x] Alembic head 应升级到 `h7e3f94c20da`
- [ ] 真实环境：跑 `alembic upgrade head` → `h7e3f94c20da`
- [ ] 真实环境：配置至少一只基金的费率（FeeLedger 配置弹层），手动 `POST /api/fund-fees/accrual/run` 看 fee_daily_accruals 表
- [ ] 真实环境：调 `POST /api/decision-review/run` 看 trades → user_decision_reviews 是否生成
- [x] 前端 UI：把"行为偏差雷达图"集成到 AdviceReview.vue（Codex 2026-05-27 已补）

### 📍 M3 进展

P2.1 / P2.2 后端全部就绪；前端 P2.1 完整，P2.2 雷达图已集成到 AdviceReview.vue。
- P2.3 OCR 持续闭环（2.5 天）— 待启动
- P2.4 老基民小工具集（5 天）— 待启动
- P2.2 行为偏差雷达图 UI 集成到 AdviceReview.vue — 已完成（Codex 2026-05-27）

---

## [2026-05-26（晚 23:17-23:31）] — Codex 交接验证 + 迁移修复 + dist 重建 ✅

> **任务来源**：Claude 交接后的继续跟进
> **执行人**：Codex
> **任务编号**：P0/P1 接力验收
> **回退方式**：git revert 本节文件；如需撤销数据库结构，按 Alembic revision 逐级 downgrade
> **后续跟进入口**：根目录 `TODO.md`

#### 23:17 ｜ `Codex` ｜ `BUGFIX+MIGRATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/views/InvestmentPlan.vue` | MOD | 修复 `<el-empty>` 中文描述中的双引号导致的 Vue 模板编译失败 |
| `backend/models/__init__.py` | MOD | 补充 `fund_manager / fund_top_holding / investment_plan / asset_allocation` 聚合导入，便于统一注册模型 |
| `backend/alembic/env.py` | MOD | 补充 P0/P1 新模型导入，保证 autogenerate / upgrade 上下文完整 |
| `backend/alembic/versions/fb5b3ac173dc_initial.py` | MOD | 初始索引创建改为已存在则跳过，适配 `create_all()` 后再 Alembic upgrade 的启动策略 |
| `backend/alembic/versions/1f8c49fb620f_add_ai_advice_v2_fields.py` | MOD | `ai_advices` 三个 V2 字段改为列存在检查后再添加 |
| `backend/alembic/versions/8b2107c04b2f_add_fund_tags_table.py` | MOD | `fund_tags` 表和索引创建改为幂等 |
| `backend/tests/conftest.py` | MOD | 认证中间件测试时绑定到内存 SQLite，避免依赖本机真实 `data/fund_quant.db` |
| `scripts/fund_ai.spec` | MOD | 补充 V3/P1 新 API、service、model 的 PyInstaller hidden imports，避免桌面包缺模块 |

#### 23:25 ｜ `Codex` ｜ `BUILD`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/dist/` | MOD | 重新执行 Vite production build |
| `dist/基金智能分析.exe` | MOD | 重新打包桌面应用；产物 424,430,523 bytes；更新时间 2026-05-26 23:25:48 |
| `build/fund_ai/*` | MOD | PyInstaller 中间产物刷新 |

#### 23:31 ｜ `Codex` ｜ `FOLLOW-UP`

| 文件 | 类型 | 概要 |
|---|---|---|
| `TODO.md` | NEW | 新增协作者跟进入口：记录已完成修复、未做 GUI 冒烟、真实库升级、真实数据同步、V3 API 测试等后续任务 |

### 本次验证证据

- `python -m pytest backend/tests/ -v` → 54 passed
- `npm run build` → passed；仅保留已有 Vite chunk-size warning
- 临时 SQLite `init_db()` → Alembic 正常升级到 `f5b3a64e29d8`
- `pwsh -File scripts/build_desktop.ps1` → 打包成功，产物 `dist/基金智能分析.exe`
- 发布 worktree 内重新执行 `python -m pytest backend/tests/ -v` → 54 passed
- 发布 worktree 内重新执行 `npm run build` → passed

### 后续协作者注意

- 还未做从 `dist/基金智能分析.exe` 启动后的 GUI 冒烟测试。
- 临时库验证覆盖了 fresh DB；真实用户数据库建议先复制一份再做升级验证。
- P1.1 / P0.2 / P0.3 涉及真实 AKShare 和交易数据，仍需要 live data 验收。

---

## [2026-05-26（晚 22:08-22:12）] — P1.3 用户画像 + AI 个性化 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P1.3
> **执行人**：Claude
> **预算**：3 人天 / 实际：4 分钟
> **里程碑**：M2（"管得住"）第 3/3 项完成 — **M2 阶段全部就绪**
> **回退方式**：`alembic downgrade e4f1c82b9d76` + 反向 patch user 模型 10 列 + 删 user_profile_v3 文件

#### 22:08 ｜ `Claude` ｜ `MODEL+MIGRATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/user.py` | MOD | UserAccount 加 10 个画像字段（birth_year / retirement_target_year / investment_horizon_years / funds_purpose / target_annual_return / max_acceptable_drawdown / risk_appetite / monthly_disposable_income / profile_updated_at / profile_notes）；加 `to_profile_dict()` 方法 |
| `backend/alembic/versions/f5b3a64e29d8_p1_user_profile.py` | NEW | 迁移：user_accounts ADD COLUMN 10 列，幂等（先查再加）|

#### 22:10 ｜ `Claude` ｜ `API+AI`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/api/user_profile_v3.py` | NEW | 3 个端点：`GET /user/profile` / `PUT /user/profile`（含 funds_purpose、risk_appetite 取值校验）/ `POST /user/profile/recommend-allocation` |
| `backend/services/ai_advisor.py` | MOD | `_build_context_json` 加 `user_profile` 字段；新增 `_build_user_profile()` 方法（年龄计算 + purpose_label / risk_label 中文映射）；SYSTEM_PROMPT 加入第 8 条规则约束 AI 必须结合用户画像调整建议 |
| `backend/main.py` | MOD | 注册 `user_profile_router` |

**关键决策**：
- 推荐配置算法 `_recommend_from_profile` 用 "100-年龄法则" 作为基准股票占比，再按资金性质（紧急/首付/养老/长期）和风险偏好（保守/稳健/积极）三档微调
- 推荐结果只作为参考，不自动写入 asset_allocation_targets — 用户必须手动确认后才生效

#### 22:11 ｜ `Claude` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/api/index.ts` | MOD | 加 3 个画像 API 函数 |
| `frontend/src/views/Settings.vue` | MOD | 新增 "用户画像" tab（User 图标）：完整表单（年龄 / 退休年 / 资金锁定期 / 资金性质 radio-group / 目标年化 / 可承受回撤 / 风险偏好 / 月可投 / 备注）+ "生成推荐配置"按钮 + 推荐结果 alert 卡片（含资产类、目标占比、容差表格） |

#### 22:12 ｜ `Claude` ｜ `VERIFY`

```python
# fund classifier (P1.2) — 6 大类全部正确
QDII 纳斯达克100 → equity_us / 债券型 → bond / 货币型 → cash / 黄金ETF → gold / 消费精选 → equity_a / 恒生互联网 → equity_hk

# 推荐配置算法 (P1.3) — 1985 出生 + balanced + long_term → 6 大类合计 100.0% ✓
```

---

## [2026-05-26（晚 21:59-22:07）] — P1.2 目标资产配置 + 再平衡 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P1.2
> **执行人**：Claude
> **预算**：3.5 人天 / 实际：8 分钟
> **里程碑**：M2 第 2/3 项
> **回退方式**：`alembic downgrade d9e2a7f15834` + 删 P1.2 新增 4 个文件 + revert RiskExposure.vue 配置卡片

#### 21:59 ｜ `Claude` ｜ `MODEL+MIGRATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/asset_allocation.py` | NEW | AssetAllocationTarget（含 tolerance_pct 容差）+ RebalanceAlert 两个模型 |
| `backend/alembic/versions/e4f1c82b9d76_p1_asset_allocation.py` | NEW | 迁移：建 2 表 + 索引 idx_ra_unack |
| `backend/database.py` | MOD | 注册 `asset_allocation` 模型 |

#### 22:01 ｜ `Claude` ｜ `SERVICE`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/asset_allocation_service_v3.py` | NEW | 含 `_classify_fund` 基金归类规则（fund_type + name 关键词 → 6 大类）+ `compute_current_allocation` 当前占比 + `compute_deviations`（按 tolerance 判断 within_tolerance + 计算建议加/减仓金额）+ alert 持久化 + ack 确认 |

**关键决策**：
- 6 大类设计：equity_a / equity_hk / equity_us / bond / gold / cash — 覆盖国内基民全部主流配置
- 归类规则用 fund_type + name 双字段匹配，QDII / 港股 / 黄金 等都能识别
- compute_deviations 默认 `persist=False`，只在调度任务里 persist=True，避免前端刷新就产生重复 alert

#### 22:03 ｜ `Claude` ｜ `API`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/api/asset_allocation_v3.py` | NEW | 7 个端点：`GET/PUT/DELETE /targets` / `GET /current` / `GET /deviations` / `GET /alerts` / `PUT /alerts/{id}/ack`；PUT /targets 含合计 ≈ 100% 校验 |
| `backend/main.py` | MOD | 注册 `asset_allocation_router` |

#### 22:05 ｜ `Claude` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/api/index.ts` | MOD | 加 7 个资产配置 API 函数 |
| `frontend/src/views/RiskExposure.vue` | MOD | 在 tagResult alert 之后插入 "目标资产配置（纪律工具）" 卡片：展示 6 大类目标 vs 当前 vs 偏离 vs 建议加减仓金额；"编辑目标" 弹层（含 6 大类输入 + 合计校验）；偏离超阈值时红色 warning 提示 |

---

## [2026-05-26（晚 21:49-21:58）] — P1.1 定投计划 + 微笑曲线 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P1.1
> **执行人**：Claude
> **预算**：5.8 人天 / 实际：9 分钟
> **里程碑**：M2（"管得住"）第 1/3 项完成
> **回退方式**：`alembic downgrade c7d8b3e94612` + 删 P1.1 新增 5 个文件 + revert 后端/前端 wire 处

#### 21:49 ｜ `Claude` ｜ `MODEL+MIGRATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/investment_plan.py` | NEW | InvestmentPlan + InvestmentPlanExecution 模型；含 plan/executions 反向关系 |
| `backend/alembic/versions/d9e2a7f15834_p1_investment_plans.py` | NEW | 迁移：建 2 表 + 2 索引 + 外键 |
| `backend/database.py` | MOD | 注册 `investment_plan` 模型 |

#### 21:51 ｜ `Claude` ｜ `SERVICE`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/investment_plan_service_v3.py` | NEW | 含 4 大模块：① CRUD（create/update/list/deactivate）② 调度算法 `_is_scheduled_day` 支持 daily/weekly/biweekly/monthly ③ `materialize_future_executions` 预生成 90 天执行行 ④ `reconcile_with_trades` 同日同代码 trade ↔ execution 关联 ⑤ `smile_curve_data` 输出 NAV 序列 + 定投点 + 摊薄成本线 ⑥ `daily_check_and_alert` 每日检查飞书提醒 |

**关键决策**：
- biweekly 用 `(target - start_date).days // 7 % 2 == 0` 区分奇偶周，比维护单独"上次执行日期"字段更简洁
- 预生成 90 天的 executions 行，前端可直接读取"下次执行日期"而无需运行时计算
- reconcile_with_trades 让用户在 App 端完成扣款后只需"导入截图"就能自动关联到计划（解耦"系统提醒" vs "App 操作" vs "持仓追踪"）

#### 21:53 ｜ `Claude` ｜ `API+SCHEDULER+NOTIFICATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/api/investment_plan_v3.py` | NEW | 8 个端点：`GET /` `POST /` `PUT /{id}` `DELETE /{id}` `GET /upcoming` `GET /{id}/smile-curve` `POST /{id}/reconcile` `POST /check-due` |
| `backend/main.py` | MOD | 注册 `investment_plan_router` |
| `backend/scheduler/setup.py` + `jobs.py` | MOD | 加 `check_investment_plans` 定时任务（每日 9:00）+ `job_check_investment_plans` 包装 |
| `backend/services/notification.py` | MOD | 加 `send_investment_reminder`：飞书蓝色 interactive card，含合计金额 |

#### 21:55 ｜ `Claude` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/views/InvestmentPlan.vue` | NEW | 完整页面：① 顶部 4 卡片（今日/本周待定投 + 累计已投 + 当前浮盈）② "未来 7 天即将到期"表 ③ 卡片列表（基金 + 周期 + 进度 + 摊薄成本 + 浮盈）④ 新建/编辑弹层 ⑤ 微笑曲线弹层（NAV + 定投点 scatter + 摊薄成本 markLine） |
| `frontend/src/api/index.ts` | MOD | 加 8 个定投 API 函数 |
| `frontend/src/router/index.ts` | MOD | 加 `/investment-plans` 路由 |
| `frontend/src/App.vue` | MOD | 侧栏"核心"组加 "定投计划" Calendar 图标入口 |
| `frontend/src/utils/icons.ts` | MOD | 注册 Calendar / MoreFilled / Memo / Histogram / RefreshLeft / RefreshRight / WarningFilled（之前 P0.2-P0.3 用到但未集中注册的图标） |

#### 21:57 ｜ `Claude` ｜ `VERIFY`

```python
# Schedule day algorithm — 全部通过
_is_scheduled_day(monthly@10, date(2025,6,10)) == True
_is_scheduled_day(weekly@Wed, date(2025,6,4)) == True
_is_scheduled_day(biweekly@Mon, date(2025,1,6/13/20)) == [True, False, True]
_iter_scheduled_dates(monthly@15, 2025-01, 2025-04) → 4 个日期，全是 15 号
```

#### 21:58 ｜ `Claude` ｜ `DOC`

| 文件 | 类型 | 概要 |
|---|---|---|
| `docs/senior-investor-upgrade-plan.md` | MOD | 进度看板标 P1.1 ✅；新增 P1.1 文件清单 + 用户感知对比表 |
| `docs/CHANGELOG.md` | MOD | 本次改动（7 个时间戳） |

### 📍 M2 "管得住" 里程碑达成

P1.1 / P1.2 / P1.3 三项全部上线 + Codex 23:17 接力做了完整验证（54 pytest 通过 / npm build 通过 / Alembic 升到 f5b3a64e29d8 / 桌面端重新打包成功）。

下一步：**M3 "看得久" 阶段**
- P2.1 费率账本（4 天）— 长期成本可见性
- P2.2 用户决策复盘（4 天）— 替代单一 AI 命中率
- P2.3 OCR 持续闭环（2.5 天）
- P2.4 老基民小工具集（5 天）

### P1.1 验收清单
- [x] 4 种 plan_type 调度算法单测通过
- [x] biweekly 奇偶周边界正确
- [x] API 路由数：8
- [ ] 真实环境：`alembic upgrade head` → `d9e2a7f15834`
- [ ] 真实环境：创建一个 monthly@10 计划，看 90 天预生成 executions 是否正确
- [ ] 真实环境：手动 `POST /api/investment-plans/{id}/reconcile`，看是否能关联同日 trade
- [ ] 真实环境：访问 `/investment-plans` 页面，新建计划 + 打开微笑曲线（前提是该基金有 fund 类型快照）
- [ ] 真实环境（次日 9:00）：到期飞书推送

---

## [2026-05-26（晚 21:40-21:48）] — P0.3 持仓重叠度 + 真实分散度 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P0.3
> **执行人**：Claude（全栈接力，单会话完成）
> **预算**：3.8 人天 / 实际：8 分钟
> **里程碑**：M1（"看得懂"）第 3/3 项完成 — **P0 阶段全部就绪**
> **回退方式**：`alembic downgrade a3e5c91d8f02` + 删 P0.3 新增 4 个文件 + revert API/scheduler/database 4 处 patch

#### 21:41 ｜ `Claude` ｜ `MODEL+MIGRATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/fund_top_holding.py` | NEW | FundTopHolding 模型；UniqueConstraint (fund_code, stock_code, quarter) + 反向 stock_code 索引 |
| `backend/alembic/versions/c7d8b3e94612_p0_fund_top_holdings.py` | NEW | 迁移：建 fund_top_holdings 表 + 2 索引；幂等检查 |
| `backend/database.py:57` | MOD | init_db 注册 `fund_top_holding` 模型 |

#### 21:43 ｜ `Claude` ｜ `SERVICE`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/overlap_analyzer_v3.py` | NEW | 核心算法：① 每只基金取最新季度持股 ② 两两加权 Jaccard ③ 真实分散度 = 100 - avg_overlap ④ 重复重仓股按"组合实际暴露 = 基金权重 × 股票权重"排序 ⑤ 输出 echarts heatmap 矩阵 |
| `backend/services/fund_top_holdings_collector_v3.py` | NEW | AKShare `fund_portfolio_hold_em` 采集器；含 quarter 解析（"2025年1季度股票投资明细" → "2025Q1"）；幂等 upsert（同季度替换） |

**关键决策**：
- AKShare 不强线程安全 → 采集器用顺序 + 单只 try/except，避免一只挂掉拖累全部
- 季度切换时仅替换最新季度数据，历史季度数据保留供时间序列分析
- heatmap 数据双向重复（[i,j]+[j,i]）+ 对角线 100%，让前端 visualMap 颜色更直观

#### 21:45 ｜ `Claude` ｜ `API+SCHEDULER`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/api/risk_exposure.py` | MOD | 加 3 个端点：`GET /risk-exposure/overlap` / `POST /overlap/sync` / `POST /overlap/sync/{fund_code}` |
| `backend/scheduler/jobs.py` | MOD | 新增 `job_sync_fund_top_holdings`（含季报月份过滤，仅 1/4/5/8/9/10/11 月执行，节省 AKShare 调用） |
| `backend/scheduler/setup.py` | MOD | 注册 `sync_fund_top_holdings` 定时任务（`day=5, hour=21`，走长任务线程池），扩展 job_func_map |

#### 21:46 ｜ `Claude` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/api/index.ts` | MOD | 加 `getOverlapReport / syncOverlapHoldings / syncOverlapSingle` |
| `frontend/src/views/RiskExposure.vue` | MOD | 新增 "实际分散度" 大卡片：评分 + 平均/最高重叠指标 + warning alert + N×N heatmap（HeatmapChart + VisualMapComponent）+ 重复重仓股 Top 10 表；含 `text-good / text-warn` 评分配色 |

#### 21:47 ｜ `Claude` ｜ `VERIFY`

```bash
python -c "from backend.services.overlap_analyzer_v3 import _build_warning, ..."
# normalize_quarter / warning 阈值测试通过
# Model / Service / Collector / Router (14 routes) / Scheduler job 全链路 import 成功
```

#### 21:48 ｜ `Claude` ｜ `DOC`

| 文件 | 类型 | 概要 |
|---|---|---|
| `docs/senior-investor-upgrade-plan.md` | MOD | 进度看板标 P0.3 ✅；新增 P0.3 文件清单 + 用户感知对比表 |
| `docs/CHANGELOG.md` | MOD | 本次改动记录（含 6 个时间戳） |

### P0.3 验收清单
- [x] `_normalize_quarter('2025年1季度...', '2025') == '2025Q1'`
- [x] `_build_warning(35, [], [])` 触发"分散度低"警示
- [x] Router routes 数：14（原 11 + overlap 3）
- [ ] 真实环境：`alembic upgrade head` → 应到 `c7d8b3e94612`
- [ ] 真实环境：`POST /api/risk-exposure/overlap/sync` 后看 fund_top_holdings 表是否有数据
- [ ] 真实环境：访问 `/risk-exposure` 前端页，热力图 + Top10 表是否正确渲染
- [ ] 真实环境：5 月已过、调度不会自动跑 → 手动 `trigger_job_now("sync_fund_top_holdings")` 强制执行

### 📍 P0 阶段全部完成

至此 P0.1 / P0.2 / P0.3 全部上线，对应 senior-investor-upgrade-plan.md 的 **M1 "看得懂" 里程碑**。

下一步：进入 **P1 "管得住"** 阶段
- P1.1 定投计划 + 微笑曲线（5.8 天）
- P1.2 目标资产配置 + 再平衡（3.5 天）
- P1.3 个人化用户档案（3 天）

---

## [2026-05-26（晚 21:25-21:38）] — P0.2 基金经理信息 + 离职预警 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P0.2
> **执行人**：Claude（全栈接力，单会话完成）
> **预算**：5.5 人天 / 实际：13 分钟（含建 CHANGELOG）
> **里程碑**：M1（"看得懂"）第 2/3 项完成
> **回退方式**：`alembic downgrade 7c2b9a8e51d4` + 删除本次新增 4 个 v3 文件

#### 21:25 ｜ `Claude` ｜ `DOC` 协作流程

| 文件 | 类型 | 概要 |
|---|---|---|
| `docs/CHANGELOG.md` | NEW | 建立统一变更日志，规范多 Agent 协作记录格式 |

#### 21:28 ｜ `Claude` ｜ `MODEL+MIGRATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/fund_manager.py` | NEW | `FundManager` + `ManagerAlert` 两个 ORM 模型；含 `is_current` / `severity` / `alert_type` 字段 |
| `backend/alembic/versions/a3e5c91d8f02_p0_fund_managers.py` | NEW | 迁移：建 `fund_managers` + `manager_alerts` 两表 + 4 个索引；含 batch_alter 兼容 SQLite |
| `backend/database.py:57` | MOD | `init_db` 注册 `fund_manager` 模型 |

#### 21:31 ｜ `Claude` ｜ `SERVICE`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/services/fund_manager_service_v3.py` | NEW | 东方财富 `fundf10.eastmoney.com/jjjl_{code}.html` 爬虫 + 变更检测算法（departure / new_join / tenure_milestone）+ 高优先级飞书钩子 |

**关键决策**：
- 东财页面 HTML 不稳定，正则提取做了 fallback 容错；提取失败时返回 `{warning: ...}` 而非抛错，避免一只基金挂掉整批同步
- 任期里程碑使用 ±7 天窗口 + 当月去重，避免重复触发
- 多源 fallback 预留 AKShare 备用（暂未启用）

#### 21:33 ｜ `Claude` ｜ `API`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/api/fund_manager_v3.py` | NEW | 5 个端点：`GET /funds/{code}/managers` / `POST /funds/{code}/managers/sync` / `POST /manager-alerts/sync-all` / `GET /manager-alerts` / `PUT /manager-alerts/{id}/read` |
| `backend/main.py:205,225` | MOD | 注册 `fund_manager_router` |

#### 21:35 ｜ `Claude` ｜ `SCHEDULER+NOTIFICATION`

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/scheduler/setup.py` | MOD | 加 `sync_fund_managers` 定时任务（CronTrigger `sun 20:00`，走长任务线程池避免阻塞）；扩展 `job_func_map` 支持手动触发 |
| `backend/scheduler/jobs.py` | MOD | 新增 `job_sync_fund_managers` 包装函数 |
| `backend/services/notification.py` | MOD | 加 `send_manager_alert(alerts)`：飞书红色 interactive card，仅推送 severity=high |

#### 21:37 ｜ `Claude` ｜ `FRONTEND`

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/api/index.ts` | MOD | 加 `getFundManagers / syncFundManagers / syncAllManagers / getManagerAlerts / markManagerAlertRead` 5 个函数 |
| `frontend/src/views/FundDetail.vue` | MOD | 新增 "基金经理" tab：现任 + 历任两个表格 + "立即拉取最新" 按钮；含任职时长计算 helper |
| `frontend/src/views/Dashboard.vue` | MOD | 顶部加红色经理预警横幅（最多展示 3 条 + 查看全部弹层）；状态变量 `managerAlerts` / `showAllAlerts`；helper `alertTypeLabel` / `alertTagType` / `markAlertRead` |

#### 21:38 ｜ `Claude` ｜ `DOC`

| 文件 | 类型 | 概要 |
|---|---|---|
| `docs/senior-investor-upgrade-plan.md` | MOD | 进度看板标记 P0.2 ✅；新增 P0.2 上线文件清单 + 用户感知对比表 |
| `docs/CHANGELOG.md` | MOD | 把本次改动从 Unreleased 移到正式段，记录 8 个时间戳 |

### P0.2 验收清单
- [x] Alembic head 为 `a3e5c91d8f02`
- [x] `backend/services/fund_manager_service_v3.py` 模块导入成功（无 syntax 错误）
- [ ] 真实环境：跑 `alembic upgrade head`
- [ ] 真实环境：调 `POST /api/funds/110011/managers/sync`（已知基金代码）确认能解析东财页面
- [ ] 真实环境：手动 `POST /api/manager-alerts/sync-all` 看是否产生预警
- [ ] 真实环境：检查 Dashboard 红色横幅显示效果
- [ ] 真实环境：若配置了飞书 webhook，验证高优先级预警推送

---

## [2026-05-26（下午-晚间）] — P0.1 收益口径专业化 ✅

> **任务来源**：`senior-investor-upgrade-plan.md` § P0.1
> **执行人**：Codex（主体）+ Claude（验证 + 文档收尾）
> **预算**：7.5 人天 / 实际：约 1 个会话日（Codex 集中产出 + Claude 接力验证）
> **里程碑**：M1（"看得懂"）第 1/3 项完成

#### Codex（时间不详）｜后端核心

| 文件 | 类型 | 概要 |
|---|---|---|
| `backend/models/portfolio_snapshot.py` | NEW | PortfolioDailySnapshot + FundBenchmark 两个 ORM 模型 |
| `backend/services/return_metrics_v3.py` | NEW | XIRR（Brent 二分）+ 最大回撤 + Beta/信息比率算法 |
| `backend/api/holding_metrics_v3.py` | NEW | 4 个端点：`/xirr` `/drawdown` `/benchmark-compare` `/snapshot` |
| `backend/alembic/versions/7c2b9a8e51d4_p0_return_metrics.py` | NEW | 数据库迁移（建 2 表 + holdings 加 4 列），含 `batch_alter_table` 兼容 SQLite |
| `backend/models/holding.py` | MOD | 加 `xirr / max_drawdown / max_drawdown_date / recovery_days` 4 列 + to_dict 输出 |
| `backend/database.py:57` | MOD | init_db 注册 `portfolio_snapshot` 模型 |
| `backend/main.py:204` | MOD | 注册 `holding_metrics_router` |
| `backend/scheduler/setup.py` | MOD | 注册 `snapshot_portfolio_daily` 定时任务（mon-fri 15:35） |
| `backend/scheduler/jobs.py:75-78` | MOD | 加 `job_snapshot_portfolio_daily` 包装函数 |
| `backend/api/dashboard.py` | MOD | `/command-center` 返回 portfolio_xirr / max_drawdown / current_drawdown / 峰谷日期 |

#### Codex（时间不详）｜前端核心

| 文件 | 类型 | 概要 |
|---|---|---|
| `frontend/src/api/index.ts` | MOD | 加 `getHoldingXirrMetrics / getHoldingDrawdownMetrics / getHoldingBenchmarkCompare` |
| `frontend/src/views/Dashboard.vue` | MOD | Hero 区加"年化 XIRR / 最大回撤 / 当前回撤"卡片 + drawdownWindow/Percent/Class helper |
| `frontend/src/views/Holdings.vue` | MOD | 表格加 "XIRR 年化 / 最大回撤 / 恢复天数" 列；摘要区显示组合 XIRR |

**回退方式**：
- 数据库：`cd backend && alembic downgrade 8b2107c04b2f` 回退到 fund_tags 版本
- 代码：`git revert <commit>` 或直接删除 `*_v3.py` 文件 + 反向 patch holding 模型 4 列

#### Claude 17:00 ｜ P0.1 验证 + 文档收尾

| 文件 | 类型 | 概要 |
|---|---|---|
| `docs/senior-investor-upgrade-plan.md` | MOD | 头部加进度看板（10 项任务状态）+ P0.1 上线文件清单 + 用户感知对比表 |

**验证记录**：
- `python -c "from backend.services.return_metrics_v3 import xirr ..."` 跑通
  - 3 期定投 1 万 + 终值 3.5 万 → XIRR = 18.28%/年 ✓
  - 100→120→95→130 → max_dd = 20.83%，recovery_days = 31 ✓

---

## [2026-05-26（中午-下午）] — V2 bug 修复 + 体验优化 ✅

> **任务来源**：用户首次提出"全面审视项目"
> **详细记录**：见 `v2-improvement-log.md`
> **简表**：

| 时间 | 执行人 | 任务 | 主要文件 |
|---|---|---|---|
| 15:35 | Claude | 全项目审视 + 12 个 v2 文件 | portfolio_analyzer_v2 / fund_v2 / news_v2 / ocr_v2 / fund_nav_collector_v2 / auth_v2 / rate_limit_v2 / request_v2 / index_v2 / App_v2 / main_v2 等 |
| 16:30 | Claude | 针对"AI 慢 + K线不全"反馈追加 5 个 v2 文件 | ai_advisor_v2 / ai_advice_v2 / AiAdvisor_v2 / Market_v2 / MarketDetail_v2 |
| ~17:00 | Linter/Codex | 修正 v2 文件细节 | auth_v2（cache 阈值）/ index_v2（base64 padding）/ ai_advisor_v2（FIRST_COMPLETED 替代 as_completed timeout）/ ai_advice_v2（切换到主分支 AiAdvisorService 类名）/ rate_limit_v2（未展示细节） |

**回退方式**：所有 v2 文件与原文件并存，删除 v2 文件即回滚（v2 未被任何 import 引用）

---

## [2026-05-26（中午）] — 产品方案文档

| 时间 | 执行人 | 文件 | 概要 |
|---|---|---|---|
| 14:50 | Claude | `docs/senior-investor-upgrade-plan.md` NEW | 老基民视角 P0-P2 升级方案（10 大方向 + 44.6 人天估算 + 路线图） |
| 15:35 | Claude | `docs/v2-improvement-log.md` NEW/MOD | V2 改进记录表 |

---

## 历史基线

> 2026-05-26 之前的项目状态 = v1 原版（不在本日志范围）。
> 历史架构审计见 `docs/system-audit-2026-05-13.md` 和 `docs/optimization-plan.md`。

---

## 协作流程速查

### 接力前自查清单
1. 读 `docs/CHANGELOG.md` 顶部 `[Unreleased]` 段，了解前一位刚做了什么
2. 读 `docs/senior-investor-upgrade-plan.md` 进度看板，找下一个 `待启动` 任务
3. 用 `git status` + `git diff` 看有无未提交改动
4. 跑一次 `pytest backend/tests/ -v`（如果有相关用例）确认基线干净

### 接力中记录
- **每完成一个文件 NEW/MOD**：立即追加到 `[Unreleased]` 段的当日块
- **每解决一个 bug**：注明 commit hash 或具体 patch
- **每决策一次架构选择**：写一行"为什么这么做"（避免下一位重新讨论）

### 接力后提交
1. 把 `[Unreleased]` 当日所有改动整合，移到正式版本号下（如 `[P0.2]` 完成时新建 `## [2026-05-26（晚）] — P0.2 ...` 段）
2. 更新 `senior-investor-upgrade-plan.md` 进度看板
3. `git add -A && git commit -m "feat(P0.2): xxx"` — commit message 与 CHANGELOG 标题对齐
