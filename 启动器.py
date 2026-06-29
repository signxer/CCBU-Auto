#!/usr/bin/env python3
"""润物细无声 CCBU-Auto 启动器
检查并安装依赖，然后启动 GUI。
"""
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQ_FILE = os.path.join(SCRIPT_DIR, "requirements.txt")
GUI_FILE = os.path.join(SCRIPT_DIR, "gui.py")


def check_and_install():
    """检查依赖，缺少则自动安装"""
    missing = []
    with open(REQ_FILE, "r") as f:
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
        print(f"正在安装 {len(missing)} 个依赖...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", REQ_FILE, "--quiet"
        ])

    # 检查 Playwright 浏览器
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
    except Exception:
        print("正在安装 Chromium 浏览器...")
        subprocess.check_call([
            sys.executable, "-m", "playwright", "install", "chromium"
        ])


def main():
    os.chdir(SCRIPT_DIR)
    check_and_install()
    # 启动 GUI
    subprocess.call([sys.executable, GUI_FILE])


if __name__ == "__main__":
    main()
