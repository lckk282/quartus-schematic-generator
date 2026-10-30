# -*- coding: utf-8 -*-
"""把后台监控写进 Windows「启动」文件夹，开机后自动生效。"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHER = os.path.join(BASE_DIR, "watch_quartus.py")
STARTUP = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                       "Start Menu", "Programs", "Startup")
TARGET = os.path.join(STARTUP, "QuartusBatchPlacer.bat")


def pythonw():
    exe = sys.executable
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.isfile(cand) else exe


def main():
    content = (
        "@echo off\r\n"
        "start \"\" \"%s\" \"%s\"\r\n" % (pythonw(), WATCHER)
    )
    # 启动项里的 .bat 用系统 ANSI(GBK) 写，避免中文路径变乱码
    with open(TARGET, "w", encoding="gbk", newline="") as f:
        f.write(content)
    print("已安装启动项: %s" % TARGET)
    print("内容:")
    print(content.strip())


if __name__ == "__main__":
    main()
