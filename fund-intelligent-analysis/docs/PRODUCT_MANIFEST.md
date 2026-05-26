# 基金智能分析 - 本地安全版产品清单

## 产品定位

基金智能分析是一套面向个人本地使用的私人基金分析系统，核心能力包括持仓管理、基金截图导入、实时估值、行情监控、新闻自动分类、AI尾盘建议、交易记录和系统体检。

## 工程边界

- 客户端形态：Windows 本地桌面启动器 + PyWebView/Edge App 独立窗口。
- 后端形态：本机 FastAPI 服务，仅监听 `127.0.0.1`。
- 数据存储：本地 SQLite 数据库，默认路径 `data/fund_quant.db`。
- 账号体系：首次启动创建本机所有者账号，后续所有业务 API 需要登录 Token。
- 密码存储：PBKDF2-HMAC-SHA256 加盐哈希，不保存明文密码。
- 会话策略：本机 HMAC Token，默认 12 小时有效，可通过 `.env` 调整。
- 日志目录：`data/logs`。

## 交付文件

- `Fund-AI-Desktop.vbs`：正式无控制台桌面启动入口。
- `Fund-AI-Desktop.cmd`：兼容命令行启动入口。
- `基金智能分析.exe`：正式 Windows 应用程序类型启动入口。
- `Fund-AI-Desktop.exe`：英文兼容 Windows 应用程序启动入口。
- `launchers/创建桌面快捷方式.cmd`：创建带正式图标的桌面快捷方式。
- `scripts/desktop_app.py`：启动页、后端健康检查和桌面窗口入口。
- `scripts/desktop.ps1`：运行时检查、前端构建和桌面程序启动。
- `scripts/run_backend.py`：后端服务入口。
- `scripts/generate_brand_assets.py`：图标资产生成脚本。
- `assets/fund-ai.ico`：Windows 快捷方式图标。

## 软件登记材料建议

- 软件名称：基金智能分析系统
- 版本号：V1.0
- 开发语言：Python、TypeScript
- 运行环境：Windows 10/11，Python 3.11+，WebView2 或 Microsoft Edge
- 数据库：SQLite
- 主要功能模块：账号登录、工作台、持仓管理、基金详情、行情监控、新闻资讯、AI投资顾问、截图导入、交易记录、系统设置
- 源代码目录：`backend`、`frontend/src`、`scripts`
- 用户手册基础文件：`docs/DESKTOP_APP.md`

## 发布前自检

1. 执行后端语法检查：`python -m compileall .\backend`
2. 执行前端构建：在 `frontend` 目录运行 `npm run build`
3. 启动桌面版：双击 `Fund-AI-Desktop.vbs`
4. 首次启动创建所有者账号
5. 确认未登录访问业务 API 返回 401
6. 登录后检查工作台、持仓、行情、新闻、AI建议、系统设置
