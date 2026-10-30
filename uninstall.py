# -*- coding: utf-8 -*-
"""卸载：删除桌面快捷方式、开机启动项，可选清空配置与日志。不动生成的原理图。"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")


def say(m=""):
    print(m, flush=True)


def main():
    say("=" * 56)
    say("  Quartus 原理图批量生成器 - 卸载")
    say("=" * 56)
    say()

    # 1. 桌面快捷方式
    removed = []
    for desk in (os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
                 os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop")):
        lnk = os.path.join(desk, "Quartus原理图生成器.lnk")
        if os.path.isfile(lnk):
            try:
                os.remove(lnk)
                removed.append(os.path.basename(lnk))
            except OSError as exc:
                say("  删除失败 %s：%s" % (lnk, exc))
    say("  [OK] 桌面快捷方式已清理" if removed else "  [--] 没有找到桌面快捷方式")

    # 2. 开机启动项
    startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup",
                           "QuartusBatchPlacer.bat")
    if os.path.isfile(startup):
        try:
            os.remove(startup)
            say("  [OK] 已移除开机启动项")
        except OSError as exc:
            say("  [FAIL] 移除开机启动项失败：%s" % exc)
    else:
        say("  [--] 没有开机启动项")

    # 3. 配置与日志
    ans = ""
    try:
        ans = input("\n是否一并删除配置与日志（config.json / server.log / watcher.log）？[y/N] ")
    except EOFError:
        pass
    if ans.strip().lower() == "y":
        for f in ("config.json", "server.log", "watcher.log"):
            p = os.path.join(APP, f)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    say("  [OK] 已删除 %s" % f)
                except OSError as exc:
                    say("  [FAIL] %s：%s" % (f, exc))
    else:
        say("  保留配置文件（下次安装可直接沿用）")

    say()
    say("卸载完成。插件本体仍在 %s，如不再需要可整个文件夹删除。" % ROOT)
    say("提示：已经生成的原理图工程在「文档\\QuartusBatch」里，不会被删除。")
    input("\n按回车键关闭…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
