# -*- coding: utf-8 -*-
"""启动器：双击「启动插件.bat」时调用。

- 插件已经在跑 → 直接打开浏览器，不重复起服务
- 没在跑 → 后台无黑框启动服务，就绪后打开浏览器
"""
import os
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")
sys.path.insert(0, APP)


def port_open(port, timeout=0.6):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout):
            return True
    except OSError:
        return False


def main():
    try:
        import config
        cfg = config.load()
        port = int(cfg["port"])
        pyw = config.pythonw()
    except Exception as exc:                        # noqa: BLE001
        print("读取配置失败：%s\n请先运行「安装.bat」。" % exc)
        input("按回车键退出…")
        return 1

    url = "http://127.0.0.1:%d/" % port

    if port_open(port):
        webbrowser.open(url)
        return 0

    log = open(os.path.join(APP, "server.log"), "a", encoding="utf-8")
    subprocess.Popen([pyw, os.path.join(APP, "server.py"), str(port), "--no-browser"],
                     cwd=APP, stdout=log, stderr=log,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    up = False
    for _ in range(48):
        time.sleep(0.25)
        if port_open(port):
            up = True
            break
    if up:                       # 再等 1 秒确认不是「刚绑上就崩」
        time.sleep(1.0)
        up = port_open(port)
    if up:
        webbrowser.open(url)
        return 0

    print("插件启动失败。请把 app\\server.log 的内容发给作者。")
    print("也可以在本窗口手动运行：python app\\server.py 来看报错。")
    input("按回车键退出…")
    return 1


if __name__ == "__main__":
    sys.exit(main())
