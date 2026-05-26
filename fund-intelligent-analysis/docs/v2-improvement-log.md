# V2 改进记录表

> 生成日期：2026-05-26（首版）/ 2026-05-26（追加 AI 生成 + K 线图）
> 审视范围：backend/api、backend/services、backend/middleware、frontend/src
> 形式：复制原文件为 `*_v2` 版本，保留原文件不动；本表逐项对应改动

---

## A. 严重 Bug（直接导致运行时报错或功能异常）

| # | 文件 | 行/函数 | 问题 | V2 处理 | V2 文件 |
|---|---|---|---|---|---|
| 1 | `backend/services/portfolio_analyzer.py` | 第 50 行 `get_portfolio_analysis` | 循环里写 `fund.fund_name`，但 `fund` 未在循环作用域定义（应为 `h.fund`），调用即 `NameError` | 修正为 `fund = h.fund`；同时加 `joinedload`、空持仓时返回完整空结构 | `services/portfolio_analyzer_v2.py` |
| 2 | `backend/api/fund.py` | 146/158/171 行 `get_fund_analysis` | 三处 `logger.debug` 但模块顶部无 `from loguru import logger`，进入异常分支即 `NameError` | 顶部 `from loguru import logger`；细分异常作用域避免吞 `HTTPException` | `api/fund_v2.py` |
| 3 | `backend/api/ai_advice.py` | `get_advice_backtest`（205/212 行） | 使用 `MarketSnapshot`、`Holding` 但未 import，访问端点即 `NameError` | 顶部统一 import；额外把 `best_view` 死代码（`max([{...}], key=lambda _: 0)`）删除 | `api/ai_advice_v2.py` |
| 4 | `backend/api/ocr.py` | 46/51/244/249 行 | 异常分支的 `logger.warning/debug` 未 import，原始错误反而被 `NameError` 覆盖 | 顶部 `from loguru import logger`;抽出 `_archive_or_remove` 公共归档逻辑 | `api/ocr_v2.py` |
| 5 | `backend/api/news.py` | 144 / 151 行 | `/impact/{news_id}` 定义在 `/impact/daily` **之前**，FastAPI 按注册顺序匹配，`daily` 被当作 `news_id` 参数，`get_daily_impact` 永远进不到 | 调换顺序，静态路径在前；并加 `Path(..., ge=1)` 限定 news_id 必须为正整数 | `api/news_v2.py` |
| 6 | `backend/services/fund_nav_collector.py` | `fetch_fund_info` 末尾 | 三个方案全失败时未 `return result`，函数返回 `None`；上层 `info.get("fund_name")` 报 `AttributeError` | 函数末尾保证返回 `dict`；同时把 HTTP 请求统一到 `_http_client` 上下文 | `services/fund_nav_collector_v2.py` |

## B. 并发 / 安全 / 鲁棒性

| # | 文件 | 问题 | V2 处理 | V2 文件 |
|---|---|---|---|---|
| 7 | `backend/middleware/auth.py` | `_user_count_cache` 模块级变量无锁；首次启动并发请求会同时打 DB；缓存只检查一次，用户完成 setup 后必须重启进程 | 加 `_cache_lock`，缓存改为 30s TTL；`clear_count_cache` 改为重置缓存而非 flag | `middleware/auth_v2.py` |
| 8 | `backend/middleware/rate_limit.py` | `request.client.host` 在 pywebview / 反向代理下永远是 `127.0.0.1`，所有客户端共用 120/min 限额；内存随时间累积 IP 槽不释放 | 解析 `X-Forwarded-For` / `X-Real-IP`；增加白名单（健康检查）；定期清理空 IP；429 响应增加 `Retry-After` | `middleware/rate_limit_v2.py` |

## C. 前端基础

| # | 文件 | 问题 | V2 处理 | V2 文件 |
|---|---|---|---|---|
| 9 | `frontend/src/main.ts` | `utils/constants.ts` 写了 `migrateStorage()` 但 `main.ts` 从未调用，老用户的 `fund-ai-privacy-mode` 等老键名永不迁移 | 启动时调用 `migrateStorage()` | `main_v2.ts` |
| 10 | `frontend/src/api/request.ts` | 401 重试前未防御 `error.config` 为空；用 `request(error.config)` 重试时 baseURL 已被加一次，存在 URL 重复风险 | 防御性判断；冗余的 `isRefreshing` 布尔删除（已有单飞 Promise） | `api/request_v2.ts` |
| 11 | `frontend/src/router/index.ts` | `tryAutoLogin` 成功后只写了 `localStorage`，Pinia store 仍是空状态；App.vue 第一帧显示用户名为空 | 自动登录成功后 `authStore.setAuth({...})`；多加 JWT 过期粗判 | `router/index_v2.ts` |
| 12 | `frontend/src/App.vue` | `navItems` 缺少 风险暴露 / AI 复盘 / 交易记录 三个已存在的页面入口 | 按「核心 / 分析 / 系统」分组重排导航，补齐缺失入口 | `App_v2.vue` |

---

## D. AI 建议生成体验（用户反馈：反应慢、进度条走完无建议）

### 根因诊断

| # | 位置 | 问题 |
|---|---|---|
| 13 | [ai_advisor.py:411 `_refresh_close_data`](backend/services/ai_advisor.py:411) | 并行采集 7 个外部源，**单步无独立 timeout**。某个 AKShare 接口慢，整体拖到 30-60s |
| 14 | [ai_advisor.py:917 `_call_ai`](backend/services/ai_advisor.py:917) | DeepSeek API 调用 timeout=180s、max_tokens=8192；每次重试都新建 OpenAI 客户端，浪费时间 |
| 15 | [api/ai_advice.py:140 `_start_generation_job`](backend/api/ai_advice.py:140) | 没有 stale timeout：上次任务线程崩了，`status` 永远停在 `running`，新请求都被 "已有AI建议正在生成" 拒绝，**必须重启进程才能解锁** |
| 16 | [ai_advisor.py:_parse_ai_output](backend/services/ai_advisor.py:297) | AI 返回非 JSON 时仍 commit 入库，但 `structured` 空、`actions` 空。前端 `hasStructuredAdvice` 不成立，回退到 V1 字段显示，**用户感觉"没生成"** |
| 17 | [AiAdvisor.vue:536](frontend/src/views/AiAdvisor.vue:536) | 进度条是估算：每 2.5s `+8`，到 82/88 封顶。AI 调用慢时进度条早就贴顶 — "走完了但没出来" 的视觉错觉 |
| 18 | [AiAdvisor.vue:537](frontend/src/views/AiAdvisor.vue:537) | 完成后只调 `loadData()`，没校验"今天是否真的有新 advice_id" — 落库失败时前端仍提示"生成完成" |
| 19 | [api/index.ts:69](frontend/src/api/index.ts:69) | `generateAdvice` axios timeout 设 10s — 这个调用只是任务入队，但后端启动有延迟时 10s 不够，用户以为"点了没反应" |
| 20 | [ai_advisor.py:_normalize_risk_level](backend/services/ai_advisor.py:735) | `medium-high` / `medium-low` 等离线模式自生成值会被 fallback 成 `medium`，离线建议看起来跟正常一样，用户分不清 |

### V2 修复

| 文件 | 关键改动 |
|---|---|
| `services/ai_advisor_v2.py` | **新建**：`_refresh_close_data` 每步独立 `timeout=10s` + 真实步骤进度回调（`step_done/step_total`）；`_call_ai` 复用 OpenAI 客户端，失败原因带回前端；`_normalize_risk_level` 保留 `medium-high/-low`；删除废弃的 V1 文本拼接路径（节省 2-5s 数据库往返）；离线建议明显标注 `offline_mode + failure_reason` |
| `api/ai_advice_v2.py` | **更新**：增加 `STALE_THRESHOLD=300` 自动 reset 卡死任务；`/advice/generate/reset` 端点供前端"强制解锁"；`_run_generation_job` 完成后校验 `advice_date == today.isoformat()` 才标 completed，否则标 failed/`missing_today_advice`；进度透传真实 `step_done/step_total` 给前端 |
| `views/AiAdvisor_v2.vue` | **新建**：进度条用真实 `step_done/step_total` 计算；显示已耗时（"已耗时 47s"）；离线模式由 warning 升级为 **红色 error** 横幅 + 失败原因；自动校验 `latestAdvice.advice_date == today`，不是今天时显示"今日尚未生成"横幅；超过 60s 显示"强制解锁"按钮；`generateAdvice` 调用 timeout 10s → 30s；轮询频率 2.5s → 1.5s |

### 用户能直接感受到的改善

| 场景 | V1 现状 | V2 表现 |
|---|---|---|
| 点击生成后等待 | 进度条 2.5s 跳一格，到顶后一直停 | 进度条按真实步骤推进，旁边显示"刷新数据 3/7" / "调用 DeepSeek AI（耗时 15-40s）" |
| AKShare 某接口卡住 60s | 整个生成跟着卡 60s | 该步骤 10s 后熔断、跳过、继续其余步骤 |
| 上次任务线程崩了 | 永远显示"已有AI建议正在生成"，必须重启进程 | 5 分钟后自动 reset；用户也可手动点"强制解锁" |
| DeepSeek API 失败 | 离线建议混入正常列表，用户分不清 | 红色横幅 + "DeepSeek API 当前不可用（原因…），本条建议来自本地规则引擎" |
| 生成完毕但今天没新记录 | 仍提示"生成完成"，但页面没变化 | 失败提示 + "AI 已调用但今日记录未生成，建议检查数据库可写性" |

---

## E. 行情 K 线图（用户反馈：显示不完整 + 简陋）

### 根因诊断

**显示不完整**：K 线 ECharts 用了**绝对像素 grid**，但容器高度是 CSS 固定值：

| 文件 | 容器高度 | Grid 总占用 | 响应式 |
|---|---|---|---|
| [Market.vue:519](frontend/src/views/Market.vue:519) | `.market-chart { height: 570px }` | K线(34+270) + 量(88) + MACD(92) + slider(30) ≈ **566px** | 1280px 以下容器被挤压时**MACD 副图被裁掉** |
| [MarketDetail.vue:315](frontend/src/views/MarketDetail.vue:315) | `chart { height: 720px }`，1280px 下变 640px | 36+360+100+128+slider ≈ **716px** | 容器变 640 时副图与 slider 全部叠加溢出 |

**简陋**：
- 没有自定义 `tooltip.formatter`：echarts 默认 K 线 tooltip 是英文 `open/close/lowest/highest`，不带涨跌幅
- MA 线没规范配色：默认轮转色 → MA5 与 MA20 长得几乎一样
- 没有十字光标价格 / 日期 label
- legend 默认顶部且会换行
- 数据加载失败时显示空 echarts 画布而非友好空状态
- 缺快捷区间按钮（30/60/120），用户必须拖 slider

### V2 修复

| 文件 | 关键改动 |
|---|---|
| `views/Market_v2.vue` | **新建**：grid 全部改百分比（`top: '8%', height: '48%'` 等）；`.market-chart { height: 100%; min-height: 580px; flex:1 }` 自适应容器；自定义 `kLineTooltipFormatter` 中文友好；MA 配色规范（MA5=橙、MA10=紫、MA20=蓝、MA60=绿）；十字光标 `label.show=true` 显示价格/日期；legend 默认只勾 MA20 避免拥挤；增加 60/120/240 快捷区间；空状态 |
| `views/MarketDetail_v2.vue` | **新建**：`.chart { height: min(82vh, 860px); min-height: 600px }` 用 vh 自适应；grid 改百分比，副图永远完整；同样的 tooltip / 配色 / 空状态；KDJ 子指标 K/D/J 也用规范配色（橙/蓝/紫） |

### 用户能直接感受到的改善

| 场景 | V1 现状 | V2 表现 |
|---|---|---|
| 笔记本 1366×768 打开行情页 | MACD 子图整个被裁掉 | 主图 + 量 + MACD 三栏完整显示 |
| 1280×800 全屏详情页 | 副指标和 slider 重叠 | 三栏 + slider 全部可见 |
| 鼠标 hover K 线 | 显示英文 "open/close/lowest/highest" | 中文卡片：开盘 / 最高 / 最低 / 收盘 / 涨跌额 / 涨跌幅 / 成交量 / MA20 |
| 切换到 MA 模式 | 4 条 MA 线挤在一起，颜色相近 | MA5=橙、MA20=蓝、MA60=绿，且默认只显示 MA20+MA60，可手动切换 |
| 数据加载失败 | 空白 echarts 画布 | 居中显示图标 + "暂无 K 线数据" |

---

## F. 未做 V2，但建议后续处理

| 优先级 | 位置 | 描述 |
|---|---|---|
| 中 | `backend/api/capital_flow.py:get_holdings_flow_impact` | 查 `holdings` 时未 `joinedload(Holding.fund)`，N+1 查询 |
| 中 | `backend/database.py:_clean_garbled_text` | 每次启动全表扫描 4 张表，数据量增长后启动时间会被拖累 |
| 中 | `backend/api/dashboard.py:get_decision_command_center` | 单端点查 6+ 张表，应加 30s 内存缓存（`backend/cache.py` 已具备能力） |
| 低 | `backend/services/auth_service.py:get_or_create_recovery_key` | 恢复密钥明文写入 `data/recovery_key.txt`，本地单机风险可控但仍可改进 |
| 低 | `backend/api/auth.py:login` | 失败次数计入用户，攻击者改用户名仍可暴力穷举；可加 IP 级失败次数 |
| 低 | `backend/tests/conftest.py` | `setup_db` 是 `autouse=True`，每个 case 建表+丢表，单测规模上来后会变慢 |

---

## G. V2 文件完整清单 + 应用方式

| V2 文件 | 替换原文件 | 用户感知 |
|---|---|---|
| `backend/services/portfolio_analyzer_v2.py` | `backend/services/portfolio_analyzer.py` | 风险暴露等页面不再崩溃 |
| `backend/api/fund_v2.py` | `backend/api/fund.py` | 基金分析接口异常时不再隐藏原始错误 |
| `backend/api/ai_advice_v2.py` | `backend/api/ai_advice.py` | **AI 生成任务可解锁、有真实进度、生成失败有明确提示** |
| `backend/api/news_v2.py` | `backend/api/news.py` | `/api/news/impact/daily` 路由可用 |
| `backend/api/ocr_v2.py` | `backend/api/ocr.py` | OCR 异常时日志清晰，临时文件不会遗留 |
| `backend/services/ai_advisor_v2.py` | `backend/services/ai_advisor.py` | **数据采集 10s 熔断，AI 调用更快、有失败原因；离线模式明确标识** |
| `backend/services/fund_nav_collector_v2.py` | `backend/services/fund_nav_collector.py` | 基金信息查询失败时不会下游崩溃 |
| `backend/middleware/auth_v2.py` | `backend/middleware/auth.py` | 类名变 `LocalAuthMiddlewareV2` |
| `backend/middleware/rate_limit_v2.py` | `backend/middleware/rate_limit.py` | 类名变 `RateLimitMiddlewareV2` |
| `frontend/src/main_v2.ts` | `frontend/src/main.ts` | 老用户偏好得以保留 |
| `frontend/src/api/request_v2.ts` | `frontend/src/api/request.ts` | 401 重试更稳定 |
| `frontend/src/router/index_v2.ts` | `frontend/src/router/index.ts` | 自动登录后首页正确显示用户名 |
| `frontend/src/App_v2.vue` | `frontend/src/App.vue` | 三组导航完整，能进风险暴露/AI复盘/交易记录 |
| `frontend/src/views/AiAdvisor_v2.vue` | `frontend/src/views/AiAdvisor.vue` | **进度条真实推进、有耗时显示、可强制解锁、离线模式醒目** |
| `frontend/src/views/Market_v2.vue` | `frontend/src/views/Market.vue` | **K 线图响应式不裁切、tooltip 中文、MA 配色规范** |
| `frontend/src/views/MarketDetail_v2.vue` | `frontend/src/views/MarketDetail.vue` | **全屏详情页 K 线响应式、可读性提升** |

### 接入方式

1. **谨慎替换**：建议先用 `git diff backend/api/ai_advice.py backend/api/ai_advice_v2.py` 等命令逐项核对
2. **批量替换**（建议分两批做，先核心 bug 修复，再 AI/K线体验）：

   **第一批：bug 修复**
   ```bash
   cp backend/services/portfolio_analyzer_v2.py backend/services/portfolio_analyzer.py
   cp backend/api/fund_v2.py backend/api/fund.py
   cp backend/api/news_v2.py backend/api/news.py
   cp backend/api/ocr_v2.py backend/api/ocr.py
   cp backend/services/fund_nav_collector_v2.py backend/services/fund_nav_collector.py
   cp frontend/src/main_v2.ts frontend/src/main.ts
   cp frontend/src/api/request_v2.ts frontend/src/api/request.ts
   cp frontend/src/router/index_v2.ts frontend/src/router/index.ts
   cp frontend/src/App_v2.vue frontend/src/App.vue
   ```

   **第二批：AI 生成 + K 线体验**
   ```bash
   cp backend/services/ai_advisor_v2.py backend/services/ai_advisor.py
   cp backend/api/ai_advice_v2.py backend/api/ai_advice.py
   cp frontend/src/views/AiAdvisor_v2.vue frontend/src/views/AiAdvisor.vue
   cp frontend/src/views/Market_v2.vue frontend/src/views/Market.vue
   cp frontend/src/views/MarketDetail_v2.vue frontend/src/views/MarketDetail.vue
   ```

   **中间件需要在 main.py 改 import 路径**（类名带 V2 后缀），或直接重命名 v2 文件并去掉类名后缀。

3. **验证**：
   - `pytest backend/tests/ -v` 跑通
   - `cd frontend && npm run build` 编译无错
   - 浏览器手动验证：
     - ① `/api/news/impact/daily` 返回当日影响汇总而非 422
     - ② 点 "刷新数据后生成 AI 建议"，看进度条是否真的按 X/7 推进
     - ③ 故意拔网线后生成，验证红色离线模式横幅是否出现
     - ④ 行情监控页缩放到 1280px，确认 MACD 子图不被裁切
     - ⑤ 鼠标 hover K 线，确认 tooltip 是中文卡片
