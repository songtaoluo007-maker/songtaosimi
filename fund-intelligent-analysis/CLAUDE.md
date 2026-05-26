# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本地私人基金智能分析桌面应用 — FastAPI + Vue3 + Element Plus + SQLite + DeepSeek AI + PaddleOCR。

## 常用命令

```bash
# 后端 — 安装依赖
pip install -r requirements.txt

# 后端 — 直接启动（带热重载）
python backend/main.py

# 后端 — 生产启动
python scripts/run_backend.py

# 前端 — 安装依赖
cd frontend && npm install

# 前端 — 开发服务器（:3000，自动代理 /api → :8000）
npm run dev

# 前端 — 构建到 frontend/dist/
npm run build

# 桌面应用 — 一键启动（自动管理后端+窗口）
python scripts/desktop_app.py

# 测试
pytest backend/tests/ -v
pytest backend/tests/test_auth.py -v          # 单个测试文件

# 数据库迁移
cd backend && alembic upgrade head             # 应用迁移
cd backend && alembic revision --autogenerate -m "描述"  # 生成迁移

# 打包 EXE
powershell -File scripts/build_desktop.ps1

# 备份数据
bash scripts/backup.sh          # Git Bash
scripts/backup.bat              # CMD/PowerShell
```

## 架构

```
项目根/
├── backend/
│   ├── main.py              # FastAPI 入口，lifespan 管理启动/关闭
│   ├── config.py            # pydantic-settings，读 .env
│   ├── database.py          # engine + SessionLocal + Base + init_db()
│   ├── api/                 # 路由层 — 12个模块（auth/fund/holding/trade/market/news/ai_advice/ocr/dashboard/settings/fund_group/capital_flow）
│   ├── models/              # SQLAlchemy ORM 模型（9个实体）
│   ├── schemas/             # Pydantic 请求/响应 schema
│   ├── services/            # 业务逻辑 + 数据采集（14个服务）
│   ├── middleware/           # auth(本地JWT) / correlation(request-id) / rate_limit
│   ├── scheduler/           # APScheduler 定时任务（行情/净值/新闻/AI建议/盈亏计算/资金流向）
│   ├── tests/               # pytest + 内存 SQLite
│   └── alembic/             # 数据库迁移
├── frontend/
│   ├── src/
│   │   ├── views/           # 13个页面组件
│   │   ├── api/             # request.ts(axios+拦截器) + index.ts(API函数)
│   │   ├── stores/          # Pinia — auth(登录状态) / app(全局UI)
│   │   ├── router/          # Vue Router 配置
│   │   ├── components/      # 可复用组件
│   │   └── utils/           # icons.ts(按需图标注册)
│   └── vite.config.ts       # 分包(echarts/element-plus/vue-vendor) + dev代理
├── scripts/                 # 启动/构建/打包/备份/修复脚本
├── docs/                    # 优化计划、审计报告等
├── data/                    # SQLite数据库 + 日志 + OCR临时文件
├── assets/                  # 品牌资源（图标等）
└── .github/workflows/ci.yml
```

## 关键设计决策

### 认证
- 本地 JWT 认证（非 OAuth），`LocalAuthMiddleware` 拦截所有 `/api/*`（白名单除外）
- 首次启动无用户时返回 `SETUP_REQUIRED`，前端引导设置密码
- Token 过期 720 分钟，存储在 `localStorage`
- 密码重置用恢复密钥（`data/recovery_key.txt`）

### 数据库
- SQLite WAL 模式 + `busy_timeout=15000`
- `init_db()` 先 `create_all`（新部署）再 `alembic upgrade head`（增量迁移）
- 启动时自动清洗编码损坏数据（surrogate 字符）
- 所有模型通过 `Base` 注册，`get_db()` 是 FastAPI 依赖注入

### 数据采集
- AKShare + httpx + BeautifulSoup
- 定时调度：交易时间每5分钟采集A股指数，每30分钟采集资金流向/基金净值
- AI 建议每日 14:30 触发（收盘前半小时）
- 启动时后台线程刷新数据（新闻/全球指数/净值/资金流向）
- NAV 采集用 `ThreadPoolExecutor(max_workers=5)` 并行

### AI 集成
- DeepSeek API（openai 兼容 SDK），`deepseek-v4-pro`
- 3 次指数退避重试（1s/2s/4s），分类处理可重试异常
- 分析上下文：持仓 + 行情快照 + 近期新闻 + 全球指数

### 前端
- `request.ts` 统一处理 401 → `authStore.logoutAndRedirect()`
- 存储 key 集中在 `STORAGE_KEYS` 常量
- ECharts 按需导入，Element Plus 图标 tree-shaking（22个注册）
- Vite 手工分包：element-plus / echarts / vue-vendor

### 桌面打包
- PyInstaller + pywebview，产物 `dist/基金智能分析.exe`
- 单实例互斥锁（Windows Mutex）
- 启动画面 + 健康检查等待循环（最多 60s）

## 注意事项
- `.env` 中的 `DEEPSEEK_API_KEY` 不能是占位值，否则启动校验失败
- 原版和优化版都用 8000 端口，不能同时运行
- 数据库路径在 `.env` 中用绝对路径配置
- 前端 dist 由后端直接托管（`StaticFiles` + SPA fallback），无独立前端服务器
- 非交易日行情数据来自最近交易日，前端需处理数据延迟
