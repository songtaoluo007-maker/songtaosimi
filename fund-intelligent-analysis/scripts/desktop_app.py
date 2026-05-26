"""
基金智能分析 — Windows 桌面应用
基于 pywebview 的原生窗口 + FastAPI 后端自动管理
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8000"
PORT = 8000
LOG_DIR = ROOT / "data" / "logs"
ICON = ROOT / "assets" / "fund-ai.ico"
PNG_ICON = ROOT / "assets" / "fund-ai-128.png"
DESKTOP_LOG = LOG_DIR / "desktop_app.log"
APP_TITLE = "基金智能分析"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(DESKTOP_LOG, "a", encoding="utf-8") as f:
        f.write(f"{ts} {msg}\n")


def is_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=3) as resp:
            return b'"ok"' in resp.read()
    except Exception:
        return False


def start_backend():
    if is_healthy():
        log("后端已运行，跳过启动")
        return

    sys.path.insert(0, str(ROOT))
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from backend.config import settings

    def _run():
        try:
            # PyInstaller console=False 时 sys.std{out,err} 为 None
            if sys.stdout is None:
                sys.stdout = open(os.devnull, 'w')
            if sys.stderr is None:
                sys.stderr = open(os.devnull, 'w')
            uvicorn.run(
                "backend.main:app",
                host=settings.BACKEND_HOST,
                port=settings.BACKEND_PORT,
                log_level="warning",
            )
        except Exception as e:
            log(f"后端线程异常退出: {type(e).__name__}: {e}")
            import traceback
            log(traceback.format_exc())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log(f"后端线程已启动 {settings.BACKEND_HOST}:{settings.BACKEND_PORT}")


def wait_backend(timeout: int = 60, callback=None) -> bool:
    for i in range(timeout):
        if is_healthy():
            if callback:
                callback(f"服务就绪 ({i + 1}s)")
            return True
        if callback and i % 3 == 0:
            callback(f"启动中... {i + 1}/{timeout}s")
        time.sleep(1)
    return False


def show_splash():
    """显示启动画面，返回后端是否就绪"""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("480x300")
    root.resizable(False, False)
    root.configure(bg="#0f172a")
    root.overrideredirect(True)

    if ICON.exists():
        try:
            root.iconbitmap(str(ICON))
        except Exception:
            pass

    # 居中
    root.update_idletasks()
    w, h = 480, 300
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(root, bg="#0f172a")
    frame.pack(fill="both", expand=True, padx=30, pady=24)

    if PNG_ICON.exists():
        try:
            img = tk.PhotoImage(file=str(PNG_ICON))
            tk.Label(frame, image=img, bg="#0f172a").pack()
            frame._icon = img
        except Exception:
            pass

    tk.Label(frame, text=APP_TITLE, font=("Microsoft YaHei UI", 20, "bold"),
             fg="#f8fafc", bg="#0f172a").pack(pady=(10, 4))
    tk.Label(frame, text="本地私人基金量化系统", font=("Microsoft YaHei UI", 10),
             fg="#93c5fd", bg="#0f172a").pack()

    status_var = tk.StringVar(value="正在准备...")
    tk.Label(frame, textvariable=status_var, font=("Microsoft YaHei UI", 9),
             fg="#cbd5e1", bg="#0f172a").pack(pady=(24, 8))

    bar = ttk.Progressbar(frame, mode="indeterminate", length=340)
    bar.pack()
    bar.start(12)

    def update(msg: str):
        status_var.set(msg)
        root.update()

    log("启动画面显示")
    start_backend()
    ready = wait_backend(callback=update)
    bar.stop()
    root.destroy()

    if not ready:
        ctypes.windll.user32.MessageBoxW(
            None, f"本地服务启动超时。\n请查看日志: {LOG_DIR}", APP_TITLE, 0x10)
    return ready


def open_window():
    """打开 pywebview 原生窗口"""
    target_url = f"{URL}/?ts={int(time.time())}"

    try:
        import webview
    except ImportError:
        log("pywebview 未安装，用浏览器打开")
        os.startfile(URL)
        return

    log(f"打开窗口: {target_url}")
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass

    webview.create_window(
        APP_TITLE,
        target_url,
        width=1360,
        height=900,
        min_size=(1024, 640),
        text_select=True,
    )
    webview.start(private_mode=False, debug=False)
    log("窗口已关闭")


def main():
    os.chdir(str(ROOT))

    # 单实例检查
    k32 = ctypes.windll.kernel32
    mutex = k32.CreateMutexW(None, False, "FundAI_Desktop_Mutex")
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            None, "基金智能分析已在运行中。\n请检查系统托盘或任务栏。", APP_TITLE, 0x40)
        return

    log("========== 桌面应用启动 ==========")

    if not show_splash():
        return

    open_window()

    # 关闭后端
    log("正在关闭后端...")
    for _ in range(5):
        try:
            urllib.request.urlopen(f"{URL}/api/health", timeout=1)
        except Exception:
            break
        time.sleep(0.5)
    log("========== 桌面应用退出 ==========")


if __name__ == "__main__":
    main()
