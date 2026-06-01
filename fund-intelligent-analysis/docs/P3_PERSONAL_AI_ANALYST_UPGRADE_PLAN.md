# P3 专属 AI 分析师升级方案

> 日期：2026-06-01
> 执行对象：OpenClaw / 后续协作者
> 目标版本：P3
> 范围：AI 建议记忆、复盘学习、用户画像校准、相似案例检索、前端入口收敛和页面重构

## 1. 核心目标

把现有“AI 尾盘建议 / AI 复盘 / 用户画像 / 风险暴露 / 行为偏差”升级为一个长期学习闭环：

```text
用户画像 + 市场状态 + 持仓组合
  -> AI 建议
  -> 用户采纳/忽略/反馈
  -> 未来 1/7/30/90 天表现复盘
  -> 更新 AI 推断画像和历史经验
  -> 下一次建议更贴合该用户
```

第一版不训练大模型，不自动交易，不让 AI 自行修改系统规则。重点是把历史建议、用户反馈、事后结果、相似场景结构化保存，并在下一次建议中检索使用。

## 2. 产品边界

必须保留以下边界：

- AI 只提供分析和建议，不自动下单。
- 每条建议必须可追溯到当时的持仓、行情、新闻、风险和用户画像快照。
- 每条建议必须有建议周期、置信度、关键理由和数据缺口。
- 用户画像分为“用户手填画像”和“AI 推断画像”，AI 不直接覆盖用户手填内容。
- 所有自动复盘都必须可重复运行且幂等。
- 输出文案禁止承诺收益，必须保留“仅供个人复盘和辅助决策”的提示。

## 3. 当前前端回顾结论

现有前端已经具备 P3 的基础，但入口和页面职责需要整理：

- `App.vue` 侧栏中 `AI 尾盘建议` 与 `AI 复盘` 分散在不同分组，用户感知上是两个功能，不像一个长期分析师。
- `Settings.vue` 中的 `用户画像` 更偏 AI 个性化，应迁移到 AI 分析师页面，不应埋在系统设置里。
- `frontend/src/components/` 基本为空，多个视图文件超过 2 万字符，后续继续堆功能会显著降低可维护性。
- `Dashboard.vue` 已经聚合资产、AI、风险、行情、机会、数据状态，后续应做摘要和跳转，不再承载复杂明细。
- 页面中同时存在 `page-head`、`page-header`、`summary-card`、`metric-card`、多处 inline style，建议统一为共享组件和全局样式。

## 4. 总体信息架构

### 4.1 侧栏重组

把侧栏改为以下分组：

```text
核心
- 工作台
- 持仓管理
- AI 分析师
- 定投计划

组合
- 风险暴露
- 费率账本
- 老基民工具箱

市场
- 行情监控
- 资金流向
- 新闻资讯

数据
- 截图导入
- 交易记录

系统
- 系统设置
```

要求：

- 侧栏只保留一个 AI 入口：`AI 分析师`。
- `AI 尾盘建议` 和 `AI 复盘` 不再作为独立侧栏入口。
- 旧路由必须保留 redirect，避免旧链接失效。

### 4.2 AI 分析师页面

新增或改造为统一页面：

```text
/ai-analyst
```

Tabs：

```text
AI 分析师
├─ 今日建议
├─ 建议复盘
├─ 专属画像
├─ 相似案例
└─ 成长报告
```

旧路由兼容：

```text
/ai-advisor        -> /ai-analyst?tab=advice
/ai-advisor/review -> /ai-analyst?tab=review
```

## 5. 后端功能规划

### 5.1 P3.1 AI 建议记忆库

新增表：`ai_advice_memories`

建议字段：

```text
id
created_at
advice_type
model_name
prompt_version
user_profile_snapshot
ai_profile_snapshot
portfolio_snapshot
market_context_snapshot
risk_context_snapshot
news_context_snapshot
similar_cases_snapshot
advice_json
confidence
horizon_days
action_type
target_funds
reason_tags
is_user_accepted
user_feedback
feedback_tags
```

实现要求：

- 每次 AI 生成建议时保存一条 memory。
- 保存结构化 JSON，不能只保存自然语言。
- 快照字段必须能支持未来复盘，不依赖实时重新查询。
- 离线规则引擎生成的降级建议也要记录，`model_name` 标识为 offline。

验收：

- 生成建议后数据库出现完整 memory。
- API 能查询历史 memory。
- 单元测试覆盖正常 AI 建议、离线建议、缺少部分上下文时的保存。

### 5.2 P3.2 建议结果追踪器

新增表：`ai_advice_outcomes`

建议字段：

```text
id
memory_id
review_horizon
review_date
portfolio_return
benchmark_return
target_fund_return
max_drawdown
volatility
would_have_helped
score
outcome_summary
error_reason
created_at
```

复盘窗口：

```text
1d / 7d / 30d / 90d
```

评分维度：

- 方向判断是否正确。
- 是否降低回撤。
- 是否优于持有不动。
- 是否优于基准。
- 是否符合用户风险偏好。
- 是否造成过度交易倾向。

验收：

- 到达复盘窗口后自动生成 outcome。
- 同一个 `memory_id + review_horizon` 不重复生成。
- 可手动触发复盘任务。
- 缺少行情或净值数据时记录 `error_reason`，不抛出未处理异常。

### 5.3 P3.3 动态 AI 用户画像

新增表：`user_ai_profile`

建议字段：

```text
id
risk_tolerance_score
drawdown_sensitivity
trade_frequency_preference
preferred_holding_period
style_preference
loss_reaction_pattern
chasing_risk_score
panic_sell_risk_score
confidence_adjustment
evidence_summary
updated_at
```

规则示例：

- 大跌后频繁卖出：提高 `panic_sell_risk_score`。
- 高频调整但收益不佳：降低后续建议中的交易频率。
- 长期不采纳激进建议：降低建议激进度。
- 用户能承受波动且长期表现更好：允许提高权益仓位建议上限。

验收：

- 可以从历史交易、用户反馈、advice outcome 生成 AI 推断画像。
- 每次画像更新记录证据摘要。
- 前端能展示“用户手填画像”和“AI 推断画像”的差异。

### 5.4 P3.4 相似历史场景检索

第一版先用 SQLite 结构化相似度，不引入向量数据库。

相似维度：

- 市场趋势：上涨 / 下跌 / 震荡。
- 指数估值或技术位置。
- 资金流方向。
- 新闻情绪。
- 持仓基金类型。
- 当前回撤。
- 行业集中度。
- 基金经理变化。
- 用户当时风险状态。
- advice action 类型。

新增服务：`SimilarCaseService`

输出：

```text
最近 3-5 个相似案例
- 当时情况
- AI 当时建议
- 用户是否采纳
- 后续结果
- 对当前决策的启示
```

验收：

- AI 建议接口返回 `similar_cases`。
- 生成新建议时把相似案例压缩后注入 prompt。
- 没有历史案例时正常降级为空数组。

### 5.5 P3.5 AI 建议输出协议升级

AI 返回必须统一为 JSON。

目标结构：

```json
{
  "decision": "hold",
  "confidence": 0.72,
  "horizon_days": 30,
  "summary": "组合当前适合观望，优先等待风险暴露回落。",
  "actions": [
    {
      "type": "rebalance",
      "fund_code": "000001",
      "suggested_change_percent": -5,
      "reason": "行业集中度偏高，且短期资金流转弱。"
    }
  ],
  "risk_warnings": [],
  "data_gaps": [],
  "similar_case_refs": [],
  "review_plan": {
    "review_after_days": [7, 30, 90],
    "key_metrics": ["return", "drawdown", "benchmark_excess"]
  }
}
```

要求：

- JSON schema 校验失败时自动重试一次。
- 二次失败时保存失败原因，并降级为可读错误状态。
- 前端不再依赖自然语言推断动作。
- 旧建议数据要兼容显示。

## 6. API 规划

新增接口：

```text
GET  /api/personal-analyst/profile
POST /api/personal-analyst/profile/recalculate

GET  /api/personal-analyst/memories
GET  /api/personal-analyst/memories/{id}
POST /api/personal-analyst/memories/{id}/feedback

GET  /api/personal-analyst/outcomes
POST /api/personal-analyst/outcomes/run

GET  /api/personal-analyst/similar-cases
GET  /api/personal-analyst/report
```

要求：

- 全部接口需要本地 JWT auth。
- endpoint tests 覆盖正常、空数据、无权限、重复复盘、缺失行情数据。
- 返回结构必须稳定，前端空状态不靠异常判断。

## 7. 调度任务

每日 15:30 或 21:00：

- 更新 advice outcomes。
- 更新 AI 推断画像。
- 生成每日学习摘要。

每周日 20:30：

- 生成 AI 分析师成长报告。
- 总结本周建议准确率、有效建议、失误判断、用户行为变化、下周建议校准方向。

要求：

- job 可手动触发。
- job 幂等。
- job 失败写日志，不影响主应用启动。
- PyInstaller hidden imports 需要同步新增模块。

## 8. 前端实施方案

### 8.1 新页面与组件结构

新增：

```text
frontend/src/views/AiAnalyst.vue
frontend/src/components/ai-analyst/AdvicePanel.vue
frontend/src/components/ai-analyst/ReviewPanel.vue
frontend/src/components/ai-analyst/ProfilePanel.vue
frontend/src/components/ai-analyst/SimilarCasesPanel.vue
frontend/src/components/ai-analyst/GrowthReportPanel.vue
```

迁移来源：

- `AdvicePanel.vue`：从现有 `AiAdvisor.vue` 迁移今日建议逻辑。
- `ReviewPanel.vue`：从现有 `AdviceReview.vue` 迁移建议复盘和行为偏差雷达图。
- `ProfilePanel.vue`：从 `Settings.vue` 迁移用户画像，并接入未来 `user_ai_profile`。
- `SimilarCasesPanel.vue`：接入未来 `/api/personal-analyst/similar-cases`。
- `GrowthReportPanel.vue`：接入未来 `/api/personal-analyst/report`。

### 8.2 Settings 页面调整

`Settings.vue` 保留：

- 系统体检。
- 系统配置。
- 定时任务。
- 账号安全。
- 关于。

从 `Settings.vue` 移出：

- 用户画像表单。
- 推荐资产配置生成器。

迁移到：

```text
AI 分析师 -> 专属画像
```

### 8.3 Dashboard 页面调整

`Dashboard.vue` 作为总控台，只展示摘要和跳转：

- 今日盈亏。
- 今日重点。
- AI 今日一句话结论。
- 风险红灯。
- 数据新鲜度。
- 快捷操作。

不要继续往 Dashboard 加复杂明细表。详细数据进入对应页面：

- AI 详情：`/ai-analyst`
- 风险详情：`/risk-exposure`
- 行情详情：`/market`
- 持仓详情：`/holdings`

### 8.4 共享组件

优先新增：

```text
frontend/src/components/common/PageHeader.vue
frontend/src/components/common/MetricCard.vue
frontend/src/components/common/EmptyState.vue
frontend/src/components/common/SectionPanel.vue
frontend/src/components/common/DataFreshnessBadge.vue
```

目标：

- 统一标题区。
- 统一指标卡。
- 统一空状态。
- 统一卡片间距。
- 减少 inline style。
- 降低单文件 Vue 体积。

### 8.5 路由要求

新增路由：

```text
{ path: '/ai-analyst', name: 'AiAnalyst', component: () => import('../views/AiAnalyst.vue'), meta: { title: 'AI 分析师' } }
```

旧路由重定向：

```text
{ path: '/ai-advisor', redirect: { path: '/ai-analyst', query: { tab: 'advice' } } }
{ path: '/ai-advisor/review', redirect: { path: '/ai-analyst', query: { tab: 'review' } } }
```

Tab 与 query 同步：

- `?tab=advice`
- `?tab=review`
- `?tab=profile`
- `?tab=similar`
- `?tab=report`

刷新页面后保持当前 tab。

## 9. 前端视觉与交互标准

本项目是本地私人投资工具，界面应保持安静、密集、可扫描：

- 不做营销式 hero。
- 不做大面积装饰渐变。
- 不新增无功能的介绍卡片。
- 表格、指标、风险提示优先。
- 卡片不要嵌套卡片。
- 图表必须有空状态。
- 重要操作要有 loading 和错误提示。
- AI 输出必须区分：真实 AI / 离线规则引擎 / 缺数据降级。

AI 分析师页面的首屏应该直接展示可操作信息：

- 当前建议动作。
- 置信度。
- 关键理由。
- 数据缺口。
- 相似历史案例数量。
- 下一次复盘时间。

## 10. 测试与验收

后端测试：

```bash
python -m pytest backend/tests/test_ai_advice_memory.py -v
python -m pytest backend/tests/test_ai_advice_outcomes.py -v
python -m pytest backend/tests/test_personal_analyst_profile.py -v
python -m pytest backend/tests/test_similar_cases.py -v
python -m pytest backend/tests/test_personal_analyst_endpoints.py -v
```

前端验证：

```bash
cd frontend
npm run build
```

全量验证：

```bash
python -m pytest backend/tests/ -v
cd frontend && npm run build
powershell -File scripts/build_desktop.ps1
```

验收标准：

- `AI 分析师` 成为唯一 AI 侧栏入口。
- 旧 AI 路由重定向正常。
- 用户画像已从设置迁移到 AI 分析师。
- 每次生成建议都会保存 memory。
- 到期复盘能生成 outcome。
- AI 推断画像可重新计算。
- 相似案例为空时页面正常显示空状态。
- Dashboard 不再承载新增 AI 明细，只保留摘要跳转。
- PyInstaller 打包通过。

## 11. 建议执行顺序

### Phase A：前端入口收敛

1. 新增 `AiAnalyst.vue`。
2. 把 `AiAdvisor.vue` 和 `AdviceReview.vue` 的内容迁入 tabs。
3. 旧路由 redirect。
4. 调整侧栏分组。
5. `npm run build`。

### Phase B：画像迁移

1. 从 `Settings.vue` 移出用户画像。
2. 新增 `ProfilePanel.vue`。
3. Settings 只保留系统相关内容。
4. `npm run build`。

### Phase C：后端记忆与复盘

1. 新增 migrations / models / schemas。
2. 新增 memory service。
3. AI 建议生成流程写入 memory。
4. 新增 outcome service 和定时任务。
5. 补测试。

### Phase D：个性化学习

1. 新增 `user_ai_profile`。
2. 新增画像 recalculation。
3. 新增相似案例检索。
4. 把相似案例接入 AI prompt。
5. 补 endpoint tests。

### Phase E：成长报告和桌面打包

1. 新增 report service。
2. 新增 `GrowthReportPanel.vue`。
3. 全量测试。
4. 重建 `dist/基金智能分析.exe`。

## 12. OpenClaw 执行约束

- 不要在一轮里大改所有页面视觉风格。
- 不要删除旧页面文件，先迁移功能并保留 redirect；确认稳定后再清理。
- 不要把 AI 学习做成不可解释黑箱。
- 不要把用户画像写死在 prompt 文本里，必须结构化传入。
- 不要引入新数据库或向量库；第一版用 SQLite 结构化相似度。
- 不要让后端定时任务阻塞应用启动。
- 每完成一个 phase，都要更新 `docs/CHANGELOG.md` 和 `TODO.md`。

## 13. 一句话判断标准

完成 P3 后，用户打开的不是一组分散功能，而是一个能记住历史、会复盘自己、理解用户风格，并且能解释自己为什么变得更适合该用户的本地专属 AI 分析师。
