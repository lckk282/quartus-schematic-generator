# -*- coding: utf-8 -*-
"""一键安装：检查 Python / 找到 Quartus / 写 config.json / 建桌面快捷方式 / 自检。

用法（一般直接双击「安装.bat」即可）：
    安装.bat                     全自动：探测 Quartus，建快捷方式
    安装.bat --check             只做环境自检，不改动任何东西
    安装.bat --quartus "D:\\altera\\91\\quartus\\bin64\\quartus.exe"
    安装.bat --no-shortcut       不建桌面快捷方式
    安装.bat --autostart         顺便装「Quartus 一启动就自动打开插件」
"""
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")
sys.path.insert(0, APP)

OK = "  [OK]   "
NO = "  [FAIL] "
WARN = "  [WARN] "


def say(msg=""):
    print(msg, flush=True)


def head(msg):
    say()
    say("=" * 56)
    say("  " + msg)
    say("=" * 56)


def parse_args():
    opt = {"check": False, "shortcut": True, "autostart": True, "quartus": None}
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--check":
            opt["check"] = True
        elif a == "--no-shortcut":
            opt["shortcut"] = False
        elif a == "--no-autostart":
            opt["autostart"] = False
        elif a == "--autostart":
            opt["autostart"] = True
        elif a == "--quartus" and i + 1 < len(argv):
            opt["quartus"] = argv[i + 1]
            i += 1
        elif a.lower().endswith(".exe"):
            opt["quartus"] = a
        i += 1
    return opt


def find_quartus():
    """按顺序找 quartus.exe：已有配置 → 命令行 → 注册表 → 常见安装路径。"""
    import glob
    cands = []
    cfg_path = os.path.join(APP, "config.json")
    if os.path.exists(cfg_path):
        try:
            import config
            cands.append(config.load()["quartus_exe"])
        except Exception:
            pass

    # 注册表里的 Altera/Intel 安装信息
    try:
        import winreg
        roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Altera"),
                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Altera"),
                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Intel\Quartus")]
        for hive, key in roots:
            try:
                with winreg.OpenKey(hive, key) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        name = winreg.EnumKey(k, i)
                        for sub in ("", r"\Quartus"):
                            try:
                                with winreg.OpenKey(k, name + sub) as k2:
                                    p = winreg.QueryValueEx(k2, "Location")[0]
                                    for b in ("bin64", "bin"):
                                        cands.append(os.path.join(p, b, "quartus.exe"))
                            except OSError:
                                pass
            except OSError:
                pass
    except Exception:
        pass

    # 常见路径 + 全盘常见盘符的 altera/intelFPGA* 目录
    for base in ("C:\\", "D:\\", "E:\\"):
        for pat in ("altera", "intelFPGA", "intelFPGA_lite", "intelFPGA_pro"):
            for d in glob.glob(os.path.join(base, pat + "*")):
                for ver in glob.glob(os.path.join(d, "*")):
                    for b in ("bin64", "bin"):
                        cands.append(os.path.join(ver, "quartus", b, "quartus.exe"))

    seen = set()
    for p in cands:
        if not p:
            continue
        p = os.path.normpath(p)
        if p in seen:
            continue
        seen.add(p)
        if os.path.isfile(p):
            return p
    return None


def lib_dir_of(quartus_exe):
    """由 bin64\\quartus.exe 推出 <安装根>/libraries。"""
    root = os.path.dirname(os.path.dirname(quartus_exe))
    lib = os.path.join(root, "libraries")
    return lib if os.path.isdir(lib) else ""


def port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def probe_port(port):
    """None=空闲；'ours'=本插件旧实例；'other'=被别的软件占用。"""
    if port_free(port):
        return None
    try:
        import json
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/config" % port, timeout=0.9) as r:
            data = json.loads(r.read().decode("utf-8"))
        return "ours" if "default_dir" in data else "other"
    except Exception:
        return "other"


def pick_port(preferred):
    if port_free(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 30):
        if port_free(p):
            return p
    return preferred


def make_shortcut(target_bat, name="Quartus原理图生成器"):
    """在桌面建 .lnk，指向启动脚本。"""
    desk = os.path.join(os.environ.get("USERPROFILE", ROOT), "Desktop")
    if not os.path.isdir(desk):
        desk = os.path.join(os.environ.get("USERPROFILE", ROOT), "OneDrive", "Desktop")
    if not os.path.isdir(desk):
        return None
    lnk = os.path.join(desk, name + ".lnk")
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath='%s';$s.WorkingDirectory='%s';"
        "$s.Description='Quartus 原理图批量生成器';$s.Save()"
        % (lnk, target_bat, ROOT)
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=60)
        return lnk if os.path.isfile(lnk) else None
    except Exception:
        return None


def main():
    opt = parse_args()

    head("Quartus 原理图批量生成器 - 安装程序")

    # 1. Python
    say("步骤 1/5  检查 Python 运行环境")
    if sys.version_info < (3, 6):
        say(NO + "需要 Python 3.6 或更高版本，当前 %s" % sys.version.split()[0])
        say("        请到 https://www.python.org/downloads/ 安装（勾选 Add Python to PATH）")
        return 1
    say(OK + "Python %s" % sys.version.split()[0])

    # 2. 插件文件
    say()
    say("步骤 2/5  检查插件文件完整性")
    need = ["server.py", "generator.py", "templates.py", "symbols.json",
            "bdf_render.py", "waveform.py", "config.py",
            os.path.join("static", "index.html")]
    miss = [f for f in need if not os.path.exists(os.path.join(APP, f))]
    if miss:
        say(NO + "缺少文件：" + ", ".join(miss))
        say("        请重新下载仓库（Download ZIP 或 git clone），保持 app 文件夹完整")
        return 1
    say(OK + "app 目录完整（%d 个关键文件）" % len(need))
    try:
        import generator
        n = len(generator.load_symbols()["items"])
        say(OK + "器件库已就绪：%d 个元件符号" % n)
    except Exception as exc:                        # noqa: BLE001
        say(NO + "器件库读取失败：%s" % exc)
        return 1

    # 3. Quartus
    say()
    say("步骤 3/5  定位 Quartus II 安装位置")
    qexe = opt["quartus"] or find_quartus()
    if not qexe:
        say(NO + "没有自动找到 quartus.exe")
        say("        请把 Quartus 的 bin64\\quartus.exe 完整路径粘贴到这里（直接回车跳过）：")
        try:
            typed = input("        路径> ").strip().strip('"')
        except EOFError:
            typed = ""
        if typed and os.path.isfile(typed):
            qexe = typed
    if not qexe:
        say(WARN + "暂时跳过：不配置 Quartus 也能生成原理图文件，只是「生成后自动打开」不可用")
        qexe = ""
    else:
        say(OK + "Quartus: %s" % qexe)
    lib = lib_dir_of(qexe) if qexe else ""

    if opt["check"]:
        import config
        eff = config.load()
        if qexe:
            eff["quartus_exe"] = qexe
        if lib:
            eff["quartus_lib"] = lib
        say()
        say("--check 模式：不做任何修改。生效配置（含默认值）：")
        for k in ("quartus_exe", "quartus_lib", "output_dir", "port", "auto_open"):
            say("        %-12s %s" % (k, eff[k]))
        say()
        say("自检结束。")
        return 0

    # 4. 写配置
    say()
    say("步骤 4/5  写入配置 config.json")
    import config
    cfg = config.load()
    if qexe:
        cfg["quartus_exe"] = qexe
    if lib:
        cfg["quartus_lib"] = lib
    if not os.path.isdir(cfg["output_dir"]):
        try:                                        # 用户自己改过路径就照他的建出来
            os.makedirs(cfg["output_dir"], exist_ok=True)
        except OSError:
            say(WARN + "输出目录 %s 用不了，改用默认的「文档\\QuartusBatch」" % cfg["output_dir"])
            cfg["output_dir"] = os.path.join(os.path.expanduser("~"), "Documents", "QuartusBatch")
    owner = probe_port(int(cfg["port"]))
    if owner == "other":
        newp = pick_port(int(cfg["port"]))
        say(WARN + "端口 %s 被别的软件占用，改用 %s" % (cfg["port"], newp))
        cfg["port"] = newp
    elif owner == "ours":
        say(OK + "端口 %s 上已有插件实例在运行（安装完刷新页面即可）" % cfg["port"])
    config.save(cfg)
    say(OK + "config.json 已写入：%s" % config.CONFIG_PATH)
    for k in ("quartus_exe", "quartus_lib", "output_dir", "port"):
        say("        %-12s %s" % (k, cfg[k]))

    # 5. 快捷方式 / 自启 / 试运行
    say()
    say("步骤 5/5  创建快捷方式并试启动")
    if opt["shortcut"]:
        lnk = make_shortcut(os.path.join(ROOT, "启动插件.bat"))
        if lnk:
            say(OK + "桌面快捷方式：%s" % os.path.basename(lnk))
        else:
            say(WARN + "桌面快捷方式没建成功（不影响使用，直接双击「启动插件.bat」即可）")

    if opt["autostart"]:
        try:
            subprocess.run([sys.executable, os.path.join(APP, "install_autostart.py")],
                           check=True, capture_output=True)
            say(OK + "已装好自动弹出：以后一打开 Quartus，插件就自动弹出")
            say("        （不需要的话：安装.bat --no-autostart，或运行 卸载.bat）")
        except Exception as exc:                    # noqa: BLE001
            say(WARN + "自动弹出安装失败：%s" % exc)
    else:
        say("        已跳过自动弹出（按 --no-autostart 指定的）")

    # 试启动
    port = int(cfg["port"])
    already = probe_port(port) == "ours"
    if already:
        say(OK + "服务已在运行：http://127.0.0.1:%d/" % port)
        ok = True
    else:
        pyw = config.pythonw()
        log = open(os.path.join(APP, "server.log"), "a", encoding="utf-8")
        log.write("\n=== %s start on port %d ===\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), port))
        log.flush()
        subprocess.Popen([pyw, os.path.join(APP, "server.py"), str(port), "--no-browser"],
                         cwd=APP, stdout=log, stderr=log,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = False
        for _ in range(40):
            time.sleep(0.25)
            if probe_port(port) == "ours":
                ok = True
                break
        if ok:                       # 再确认一次，防止「刚绑上就崩」
            time.sleep(1.2)
            ok = probe_port(port) == "ours"
    if ok and not already:
        say(OK + "服务已启动：http://127.0.0.1:%d/" % port)
    elif not ok:
        say(WARN + "服务启动较慢，稍后双击「启动插件.bat」即可")

    say()
    say("安装完成！")
    if opt["autostart"]:
        say("  - 打开 Quartus，插件会自动弹出（和以前一样）")
    if opt["shortcut"]:
        say("  - 也可以双击桌面的「Quartus原理图生成器」手动打开")
    say("  - 手动启动：双击「启动插件.bat」，或访问 http://127.0.0.1:%d/" % int(cfg["port"]))
    say("  - 详细用法见「安装教程.html」")
    say("  - 想改 Quartus 路径/端口/输出目录：用记事本打开 app\\config.json")
    say()
    try:
        os.startfile(os.path.join(ROOT, "安装教程.html"))
    except Exception:
        pass
    if os.environ.get("QUARTUS_NO_PAUSE") != "1":
        try:
            input("\n按回车键关闭本窗口…")
        except EOFError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
