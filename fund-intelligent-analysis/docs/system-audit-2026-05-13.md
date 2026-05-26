# 基金智能分析系统 — 产品团队全景审计报告

**日期**: 2026-05-13 | **审计方式**: 3 Agent 并行扫描 (后端/前端/数据库)

---

## 1. 产品经理视角 — 功能完成度 & 体验风险

| 模块 | 完成度 | 关键缺口 |
|------|--------|---------|
| 仪表盘 | 85% | Hero叙事已上线，但大盘指数对比缺失 |
| 持仓管理 | 80% | 收益日历在巨型组件内，难独立迭代 |
| 交易记录 | 75% | 手续费计算、卖出比例已修，但筛选维度少 |
| AI 顾问 | 80% | DeepSeek调用无重试，生成失败静默丢数据 |
| 资金流向 | 70% | 行业板块API被拦截无法使用 |
| OCR 导入 | 75% | 三步曲已上线，但支付宝/天天基金解析差异大 |
| 新闻 | 80% | 分类/情感分析到位，缺推送订阅差异化 |
| 行情 | 75% | 布林带计算前端重复，后端无缓存加速 |
| 设置 | 60% | 端点已砍死路由，功能极度简化 |

**产品风险 Top 3:**
1. AI 建议生成失败无用户提示 → 用户看到空白以为功能坏了
2. 大盘指数（沪深300/创业板）不能独立查看走势
3. 资金流行业板块不可用 → 用户在仪表盘看到空白块

---

## 2. 架构师视角 — 系统设计质量

### 整体架构 (Excellent)
```
FastAPI (app factory + lifespan)
  ├── middleware (auth / rate-limit / correlation-id)
  ├── api/ (13 modules)  ← 路由 + 部分业务逻辑混在一起
  ├── services/ (14 modules) ← 核心业务，但AI调用无重试
  ├── models/ (10 models) ← SQLAlchemy ORM，索引单独维护
  ├── schemas/ (6 pydantic) ← 类型覆盖但缺validator
  ├── scheduler/ (APScheduler) ← 10个定时任务，cron缺口存在
  └── tests/ (4 files, 263行) ← <5%覆盖率
```

### 核心架构债

| 问题 | 影响 | 严重度 |
|------|------|--------|
| API层内联业务逻辑 (fund.py, dashboard.py) | Service 层未完全抽象，难以测试 | P1 |
| 无正式迁移机制 (ALTER TABLE 手写) | Schema 变更不可追溯，回滚不可能 | P1 |
| scheduler无幂等保护 | 重启可能重复插入数据 | P2 |
| cache 是内存字典 | 多进程不共享，重启即丢失 | P3 |

---

## 3. 前端组长视角 — 组件 & 类型质量

### 组件健康度

| 组件 | 行数 | 状态 | 主要问题 |
|------|------|------|---------|
| Holdings.vue | 887 | 🔴 需拆分 | 收益日历+基金组管理+持仓表+隐私模式混在一起 |
| Dashboard.vue | 678 | 🔴 需拆分 | 5个数据区块全在一个组件 |
| Market.vue | 545 | 🟡 可优化 | 行情列表+筛选在一个文件 |
| AiAdvisor.vue | 508 | 🟡 可优化 | 对话界面+建议卡片混排 |
| OcrImport.vue | 469 | 🟢 可接受 | 三步曲流程完整 |
| 其余8个组件 | <350 | 🟢 正常 | - |

### 类型安全现状 (Critical)

- **类型定义** (`types/index.ts`): 完整，覆盖 Fund/Holding/Trade/AiAdvice/News
- **视图实际使用**: 几乎全部 `ref<any>()` — 类型定义形同虚设
- **API 返回值**: 全部隐式 any，零类型推导

```typescript
// 现状 (所有视图都是这样)
const holdings = ref<any[]>([]);
const command = ref<any>({});

// 应该是
const holdings = ref<Holding[]>([]);
const command = ref<DashboardOverview | null>(null);
```

### API 层硬伤 (Critical)

`request.ts:61` — 401 拦截器直接用 `window.location.href` 跳转，绕过 Vue Router + Pinia：
- Store 状态不重置
- 跳转后残留数据
- 完全无法做 SSR

---

## 4. 后端组长视角 — 代码质量 & 性能

### 安全 ✅

PBKDF2-HMAC-SHA256 (26万次迭代) + HMAC-SHA256 Token 含 v1 版本号，商用级安全。

### 性能问题

| 问题 | 位置 | 影响 |
|------|------|------|
| N+1 查询 | `api/holding.py` 4个端点无 `joinedload` | 每个持仓单独查基金信息 |
| NAV 采集串行 | `fund_nav_collector.py` | N只基金逐个调 AKShare，耗时分级 |
| AI 调用无重试 | `ai_advisor.py:_call_ai()` | 单次网络抖动直接丢生成 |

### 测试债 (最严重)

后端 9000+ 行代码，仅 263 行测试。`services/` 零覆盖、`scheduler/` 零覆盖、`middleware/` 仅 auth 有间接覆盖。

---

## 5. QA 测试视角 — 质量保障现状

| 测试类型 | 覆盖率 | 状态 |
|----------|--------|------|
| 单元测试 | ~3% (3/50文件) | 🔴 严重不足 |
| 集成测试 | 0% | 🔴 无 |
| E2E 测试 | 0% | 🔴 无 |
| API 测试 | ~5% (部分端点) | 🔴 仅 auth + fund CRUD |
| 边界测试 | 0% | 🔴 无 |
| 性能测试 | 0% | 🔴 无 |

**唯有的测试保护：** auth (5场景) + fund CRUD (7场景) + notification (5场景)

---

## 6. DevOps 视角 — 部署 & 运维

| 维度 | 状态 |
|------|------|
| 构建 | PyInstaller + Vite，一键打包 ✅ |
| 配置 | pydantic_settings + .env ✅ |
| 日志 | loguru，文件按天轮转 ✅ |
| 监控 | 无 (`system_diagnostics.py` 有诊断工具但无采集) 🟡 |
| 备份 | 无自动化备份 🔴 |
| 迁移 | 无 Alembic，纯手写 SQL 🔴 |
| Docker | Dockerfile + docker-compose.yml 存在但未测试 🟡 |
| CI/CD | 无 🔴 |

---

## 问题优先级矩阵

| 优先级 | 类别 | 问题 | 影响范围 | 预估时间 |
|--------|------|------|---------|---------|
| **P0** | 前端 | 401 拦截器用 router 替代 window.location | 全站状态一致性 | 0.5h |
| **P0** | 前端 | 视图层 `any` → 类型定义 | 全站类型安全 | 2h |
| **P0** | 后端 | holding API 加 joinedload (防N+1) | 持仓页性能 | 1h |
| **P1** | 后端 | AI 调用加重试机制 | AI 生成可靠性 | 1h |
| **P1** | 前端 | 拆分 Holdings.vue (887行→子组件) | 可维护性 | 3h |
| **P1** | 前端 | 拆分 Dashboard.vue (678行→子组件) | 可维护性 | 2h |
| **P1** | 后端 | API 层业务逻辑下沉到 service | 可测试性 | 3h |
| **P1** | 测试 | 核心 service 加单元测试 | 回归保护 | 3h |
| **P1** | DevOps | 引入 Alembic 数据库迁移 | Schema 版本管理 | 1h |
| **P2** | 后端 | capital_flows 加 (flow_date, flow_type) 复合索引 | 资金流查询 | 0.5h |
| **P2** | 后端 | NAV 采集改 ThreadPoolExecutor 并行 | 采集速度 | 1h |
| **P2** | 后端 | scheduler 采集加幂等保护 | 数据一致性 | 1h |
| **P2** | 前端 | 消除工具函数重复定义 | 代码一致性 | 1h |
| **P3** | 前端 | 按需注册 Element Plus 图标 | 首屏体积 | 0.5h |
| **P3** | DevOps | 自动化数据库备份 | 数据安全 | 1h |
| **P3** | DevOps | CI/CD pipeline | 自动化 | 2h |

---

**总预估**: P0(3.5h) + P1(10h) + P2(3.5h) + P3(3.5h) = **约 20.5 小时**

---

## 现实团队分工 (按职能拆任务)

```
📋 PM → 确认优先级、验收标准
🏗️ 架构 → database迁移 + api→service下沉 + 索引优化
🎨 前端 → 类型化 + 组件拆分 + request修复 + 去重工具函数
⚙️ 后端 → N+1修复 + AI重试 + scheduler幂等 + NAV并行
🧪 测试 → service单测 + API集成测试 + 边界用例
🚀 DevOps → Alembic + 备份脚本 + CI模板
```

---

*报告完毕，等待团队评审进入实现阶段*