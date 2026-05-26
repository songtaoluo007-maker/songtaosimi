# 基金智能分析

本地私人基金智能分析桌面应用。支持持仓管理、截图导入、行情监控、北向/主力资金流向追踪、AI 投资建议、新闻资讯、交易记录。

## 用户安装与使用

### 方式一：下载安装包（推荐）

1. 从发布页下载 `基金智能分析-Setup.exe`
2. 双击安装，选择安装目录
3. 桌面自动生成快捷方式
4. 双击快捷方式启动

> 无需安装 Python、Node.js 或其他环境，所有依赖已内置。

### 方式二：开发者运行

**环境要求：** Python 3.11+、Node.js 20+

```powershell
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 构建前端
cd frontend
npm install
npm run build
cd ..

# 3. 配置 AI Key（可选）
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 4. 启动
python scripts/desktop_app.py
```

首次启动访问 `http://127.0.0.1:8000/`

## 打包为独立 EXE

```powershell
# 一键打包（约 3-8 分钟）
powershell -File scripts/build_desktop.ps1

# 产物在 dist/基金智能分析.exe
```

打包后用户无需安装 Python，双击 EXE 即可使用。

## 配置说明

编辑项目根目录的 `.env` 文件（首次启动自动从 `.env.example` 复制）：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | AI 建议的 API Key | 留空则不启用 AI |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-v4-pro` |
| `BACKEND_PORT` | 后端端口 | `8000` |
| `MARKET_COLLECT_INTERVAL_MINUTES` | 行情采集间隔 | `5` |
| `AI_ADVICE_HOUR` / `AI_ADVICE_MINUTE` | AI 建议时间 | `14:30` |

## 数据存储

- 数据库和配置文件：`data/` 目录
- 日志：`data/logs/`
- 恢复密钥：`data/recovery_key.txt`（忘记密码时使用）
- OCR 截图归档：`data/ocr_temp/archive/`

## 功能模块

| 模块 | 说明 |
|------|------|
| **工作台** | 资产概览、收益曲线、AI 建议摘要 |
| **持仓管理** | 基金持仓 CRUD、分组、盈亏分析 |
| **行情监控** | A 股指数、行业/概念板块、全球指数 |
| **资金流向** | 北向资金、主力/超大单/大单、融资融券、龙虎榜 |
| **新闻资讯** | 7x24 快讯、分类筛选、情绪标注 |
| **AI 顾问** | 基于持仓+行情+资金流向的加减仓建议 |
| **截图导入** | 支付宝/同花顺持仓截图 OCR 识别导入 |
| **交易记录** | 买入卖出记录、盈亏统计 |

## 常见问题

**Q: 启动后显示"服务启动超时"？**
A: 检查 `data/logs/backend_stderr.log`，通常是端口被占用。关闭其他 Python 进程后重试。

**Q: AI 建议无法生成？**
A: 检查 `.env` 中的 `DEEPSEEK_API_KEY` 是否配置正确。

**Q: 忘记登录密码？**
A: 在登录页点击"忘记密码"，输入首次设置时生成的恢复密钥。或运行 `python scripts/reset_password.py` 命令行重置。

**Q: 行情数据显示为空？**
A: 非交易日（周末/节假日）数据来自最近交易日。等待下一个交易日或手动点击"刷新"。

**Q: 如何备份数据？**
A: 复制整个 `data/` 目录即可。数据库文件为 `data/fund_quant.db`。

**Q: 桌面版和浏览器版有什么区别？**
A: 功能完全相同。桌面版自动管理后端启停，浏览器版需手动运行 `python scripts/run_backend.py`。
