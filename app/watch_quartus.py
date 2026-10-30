# -*- coding: utf-8 -*-
"""后台监控：检测到 Quartus II 启动，就自动打开批量放置页面；Quartus 关闭后自动收摊。

放到「启动」文件夹即可开机自启（见 install_autostart.bat）。
运行日志写在同目录 watcher.log，方便排查没弹窗的问题。
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(BASE_DIR, "server.py")
LOG_FILE = os.path.join(BASE_DIR, "watcher.log")
try:                                  # 端口跟随 config.json
    import config
    PORT = int(config.load()["port"])
except Exception:
    PORT = 8765
POLL_SECONDS = 3

BROWSER_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def single_instance():
    """同一个监控脚本只允许跑一个，返回 (是否首次, 句柄)。"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, "Local\\QuartusBatchPlacerWatcher")
    return kernel32.GetLastError() != 183, handle


def quartus_running():
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq quartus.exe", "/NH"],
            capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
        ).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False
    return "quartus.exe" in out


def service_alive():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/config" % PORT, timeout=1) as resp:
            return resp.status == 200
    except OSError:
        return False


def start_server():
    proc = subprocess.Popen(
        [sys.executable, SERVER, "--no-browser", str(PORT)],
        cwd=BASE_DIR, creationflags=NO_WINDOW,
    )
    for _ in range(40):
        time.sleep(0.25)
        if service_alive():
            return proc
    return proc


def browser_exe():
    for path in BROWSER_PATHS:
        if os.path.isfile(path):
            return path
    for name in ("msedge.exe", "chrome.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def page_window_exists(title="Quartus 原理图生成器"):
    """已经弹过页面就不再弹第二个，避免窗口越堆越多。"""
    titles = {title, "Quartus 批量放置元件"}
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value in titles and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return bool(found)


def open_page():
    if page_window_exists():
        return
    url = "http://127.0.0.1:%d/" % PORT
    exe = browser_exe()
    if exe:
        try:
            subprocess.Popen([exe, "--app=" + url], creationflags=NO_WINDOW)
            return
        except OSError:
            pass
    try:
        os.startfile(url)  # noqa: S606
    except OSError as exc:
        log("打开页面失败: %s" % exc)


def main():
    first, _handle = single_instance()
    if not first:
        return
    log("监控启动，等待 Quartus")
    proc = None
    page_open = False
    while True:
        running = quartus_running()
        if running:
            if not service_alive():
                proc = start_server()
                page_open = False
                log("Quartus 已启动，服务拉起: %s" % ("成功" if service_alive() else "失败"))
            if not page_open:
                open_page()
                page_open = True
                log("已弹出页面")
        else:
            # Quartus 关掉后页面会变成无主窗口，这里把服务留着，页面继续可用；
            # 下次启动 Quartus 会重新弹一个新页面。
            page_open = False
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
