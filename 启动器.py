#!/usr/bin/env python3
"""润物 Moisten 启动器"""
import os
import sys
import subprocess
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "launcher.log")


def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def show_error(msg):
    """macOS 弹窗显示错误"""
    try:
        subprocess.run(["osascript", "-e", f'display dialog "{msg}" with title "Moisten" buttons {{"OK"}}'])
    except:
        pass


def check_and_install():
    req_file = os.path.join(SCRIPT_DIR, "requirements.txt")
    missing = []
    with open(req_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pkg = line.split(">=")[0].split("==")[0].split("<")[0].strip()
            try:
                __import__(pkg.replace("-", "_").split("[")[0])
            except ImportError:
                missing.append(line)

    if missing:
        log(f"安装依赖: {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"])

    # 检查 Playwright 浏览器
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
    except Exception:
        log("安装 Chromium...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def main():
    # 清空日志
    with open(LOG_FILE, "w") as f:
        f.write("")
    log(f"启动器开始, Python: {sys.executable}")
    log(f"工作目录: {SCRIPT_DIR}")

    try:
        os.chdir(SCRIPT_DIR)
        check_and_install()
        gui_file = os.path.join(SCRIPT_DIR, "gui.py")
        log(f"启动 GUI: {gui_file}")
        os.execv(sys.executable, [sys.executable, gui_file])
    except Exception as e:
        err = f"启动失败: {e}\n{traceback.format_exc()}"
        log(err)
        show_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
