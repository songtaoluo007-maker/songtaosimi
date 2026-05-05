# 基金智能分析桌面版

## 推荐启动方式

双击项目根目录的：

- `启动基金智能分析-桌面版.cmd`
- 或桌面快捷方式 `Fund AI`

桌面版会先显示本地启动界面，然后自动启动后端服务，并在独立桌面窗口中打开系统。

## 兼容策略

优先使用 Python `pywebview` 调用系统 WebView2，体验接近桌面软件。

如果当前 Windows 缺少可用 WebView 运行时，会自动退回到 Microsoft Edge App 模式窗口，不打开普通浏览器标签页。

## 日志位置

- `data/logs/desktop_backend_stdout.log`
- `data/logs/desktop_backend_stderr.log`
- `data/logs/launcher.log`

## 停止服务

双击：

- `stop.bat`
