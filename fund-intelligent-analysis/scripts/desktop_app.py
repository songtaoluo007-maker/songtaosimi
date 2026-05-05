from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8000"
LOG_DIR = ROOT / "data" / "logs"
ICON = ROOT / "assets" / "fund-ai.ico"
PNG_ICON = ROOT / "assets" / "fund-ai-128.png"
DESKTOP_LOG = LOG_DIR / "desktop_app.log"


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DESKTOP_LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def is_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=2) as resp:
            return b'"ok"' in resp.read()
    except Exception:
        return False


def start_backend() -> subprocess.Popen | None:
    if is_healthy():
        log("backend already healthy")
        return None
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout = open(LOG_DIR / "desktop_backend_stdout.log", "ab", buffering=0)
    stderr = open(LOG_DIR / "desktop_backend_stderr.log", "ab", buffering=0)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log("starting backend")
    return subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "run_backend.py")],
        cwd=str(ROOT),
        stdout=stdout,
        stderr=stderr,
        creationflags=creationflags,
    )


def wait_backend(update_status) -> bool:
    for idx in range(45):
        if is_healthy():
            update_status("服务已就绪，正在打开桌面工作台...")
            return True
        update_status(f"正在启动本地分析服务... {idx + 1}/45")
        time.sleep(1)
    return False


def show_splash_and_start() -> bool:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("基金智能分析")
    root.geometry("520x320")
    root.resizable(False, False)
    root.configure(bg="#0f172a")
    if ICON.exists():
        root.iconbitmap(str(ICON))
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 520) // 2
    y = (root.winfo_screenheight() - 320) // 2
    root.geometry(f"520x320+{x}+{y}")

    frame = tk.Frame(root, bg="#0f172a")
    frame.pack(fill="both", expand=True, padx=34, pady=28)

    if PNG_ICON.exists():
        icon_img = tk.PhotoImage(file=str(PNG_ICON))
        tk.Label(frame, image=icon_img, bg="#0f172a").pack()
        frame.icon_img = icon_img

    tk.Label(
        frame,
        text="基金智能分析",
        font=("Microsoft YaHei UI", 22, "bold"),
        fg="#f8fafc",
        bg="#0f172a",
    ).pack(pady=(12, 4))
    tk.Label(
        frame,
        text="本地私人基金量化系统",
        font=("Microsoft YaHei UI", 11),
        fg="#93c5fd",
        bg="#0f172a",
    ).pack()
    status = tk.StringVar(value="正在准备启动...")
    tk.Label(
        frame,
        textvariable=status,
        font=("Microsoft YaHei UI", 10),
        fg="#cbd5e1",
        bg="#0f172a",
    ).pack(pady=(30, 10))
    progress = ttk.Progressbar(frame, mode="indeterminate", length=340)
    progress.pack()
    progress.start(12)

    def update_status(text: str) -> None:
        status.set(text)
        root.update()

    log("show splash")
    start_backend()
    ready = wait_backend(update_status)
    progress.stop()
    root.destroy()
    if not ready:
        log("backend startup timeout")
        ctypes.windll.user32.MessageBoxW(
            None,
            f"本地服务启动超时，请查看日志：{LOG_DIR}",
            "基金智能分析",
            0x10,
        )
    return ready


def open_desktop_window() -> None:
    try:
        import webview

        log("opening pywebview window")
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True
        except Exception:
            pass
        window = webview.create_window(
            "基金智能分析",
            URL,
            width=1360,
            height=900,
            min_size=(1100, 720),
            text_select=True,
        )
        webview.start(private_mode=False, debug=False)
        log("pywebview closed")
        return
    except Exception as exc:
        log(f"pywebview failed: {type(exc).__name__}: {exc}")

    edge_candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for edge in edge_candidates:
        if edge and os.path.exists(edge):
            log(f"opening edge app: {edge}")
            user_data = ROOT / "data" / "edge_app_profile"
            user_data.mkdir(parents=True, exist_ok=True)
            subprocess.Popen([
                edge,
                f"--app={URL}",
                "--new-window",
                f"--user-data-dir={user_data}",
                "--no-first-run",
            ], cwd=str(ROOT))
            return
    log("opening default browser fallback")
    os.startfile(URL)


def main() -> int:
    if show_splash_and_start():
        open_desktop_window()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
