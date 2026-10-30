# -*- coding: utf-8 -*-
"""在已经打开的 Quartus II 窗口里打开生成好的 .bdf（不新开 Quartus 实例）。

做法：Win32 消息自动化 —— 激活 Quartus 主窗口 → Ctrl+O → 在「打开」对话框里
填文件名 → 点「打开」。全部用 ctypes，无第三方依赖。
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

WM_SETTEXT = 0x000C
WM_CLOSE = 0x0010
BM_CLICK = 0x00F5
SW_RESTORE = 9
VK_CONTROL = 0x11
VK_O = 0x4F
KEYUP = 0x0002

user32.EnumWindows.argtypes = [EnumProc, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.EnumChildWindows.argtypes = [wt.HWND, EnumProc, wt.LPARAM]
user32.EnumChildWindows.restype = wt.BOOL
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.GetDlgCtrlID.argtypes = [wt.HWND]
user32.GetDlgCtrlID.restype = ctypes.c_int
user32.GetForegroundWindow.restype = wt.HWND
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.AttachThreadInput.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SendMessageW.restype = wt.LPARAM
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.GetDlgItem.argtypes = [wt.HWND, ctypes.c_int]
user32.GetDlgItem.restype = wt.HWND
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wt.DWORD, ctypes.c_size_t]
kernel32.GetCurrentThreadId.restype = wt.DWORD


def _title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _cls(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _pid(hwnd):
    p = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value


def _top_windows():
    rows = []

    def cb(hwnd, _):
        rows.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return rows


def _children(hwnd):
    rows = []

    def cb(child, _):
        rows.append(child)
        return True

    user32.EnumChildWindows(hwnd, EnumProc(cb), 0)
    return rows


def quartus_pids():
    """拿 quartus.exe 的进程号。

    注意：中文 Windows 下 tasklist 输出是 GBK（mbcs）编码，绝不能按 UTF-8 解码，
    否则会抛 UnicodeDecodeError 把整个请求线程带崩。
    """
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq quartus.exe", "/NH"],
            capture_output=True, text=True, encoding="mbcs", errors="replace",
            timeout=10, creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return set()
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) > 1 and parts[0].lower() == "quartus.exe":
            try:
                pids.add(int(parts[1]))
            except ValueError:
                pass
    return pids


def quartus_running():
    return bool(quartus_pids())


def find_main_window():
    """返回 (hwnd, pid)；没有运行中的 Quartus 主窗口时返回 (None, None)。"""
    pids = quartus_pids()
    if not pids:
        return None, None
    for hwnd in _top_windows():
        if _pid(hwnd) not in pids:
            continue
        if not user32.IsWindowVisible(hwnd):
            continue
        if _cls(hwnd) == "#32770":
            continue
        if _title(hwnd).startswith("Quartus II"):
            return hwnd, _pid(hwnd)
    return None, None


def _activate(hwnd):
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    cur = kernel32.GetCurrentThreadId()
    attached = bool(user32.AttachThreadInput(cur, fg_thread, True))
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur, fg_thread, False)


def _send_ctrl_o():
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_O, 0, 0, 0)
    user32.keybd_event(VK_O, 0, KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)


def _wait_dialog(pid, timeout):
    """等「打开文件」对话框：必须是带文件名输入框(控件 1148)的窗口。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for hwnd in _top_windows():
            if _pid(hwnd) == pid and _cls(hwnd) == "#32770" and user32.IsWindowVisible(hwnd):
                if _filename_edit(hwnd):
                    return hwnd
        time.sleep(0.2)
    return None


def _filename_edit(dlg):
    for child in _children(dlg):
        if _cls(child) == "Edit" and user32.GetDlgCtrlID(child) == 1148 and user32.IsWindowVisible(child):
            return child
    return None


def _automate_open(path):
    """自动化路径本体。只在独立子进程里跑，避免个别 ctypes 调用崩溃拖垮服务。

    只做一件事：Ctrl+O → 填路径 → 回车/点打开。
    绝不发送 Ctrl+W 之类的其它快捷键 —— 在 Quartus 里 Ctrl+W 是「关闭窗口」，
    会直接把用户正在用的窗口关掉。
    """
    main, pid = find_main_window()
    if not main:
        return False, "Quartus 主窗口还没建出来"

    _activate(main)
    time.sleep(0.2)
    dlg = _wait_dialog(pid, 0.1)
    for _ in range(6):
        if dlg:
            break
        _activate(main)
        time.sleep(0.2)
        _send_ctrl_o()
        dlg = _wait_dialog(pid, 2.0)
    if not dlg:
        return False, "没能唤出 Quartus 的打开对话框"

    edit = _filename_edit(dlg)
    if not edit:
        return False, "找不到对话框里的文件名输入框"
    buf = ctypes.create_unicode_buffer(path)
    user32.SendMessageW(edit, WM_SETTEXT, 0, ctypes.addressof(buf))
    time.sleep(0.2)

    button = user32.GetDlgItem(dlg, 1)
    if not button:
        return False, "找不到对话框里的打开按钮"
    user32.SendMessageW(button, BM_CLICK, 0, 0)

    deadline = time.time() + 15.0
    while time.time() < deadline:
        if not user32.IsWindowVisible(dlg):
            time.sleep(0.6)
            return True, "已在 Quartus 中打开"
        time.sleep(0.3)
    return False, "打开对话框没有关闭"


def _associated_open(path):
    """最后兜底：交给 Windows 文件关联（.bdf 默认由 Quartus 打开）。"""
    try:
        os.startfile(path)            # noqa: S606  (Windows 专用)
    except OSError as exc:
        return False, "系统关联打开失败: %s" % exc
    return True, "已用系统关联交给 Quartus 打开"


def _try_automation(path, timeout=20.0):
    """在独立子进程里跑消息自动化，崩溃或超时都只算「失败」，不影响服务。"""
    try:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), path],
            capture_output=True, text=True, encoding="mbcs", errors="replace",
            timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return proc.returncode == 0 and "OK" in (proc.stdout or "")


def open_in_quartus(path, timeout=20.0):
    """打开 .bdf。两级策略，失败也只会「没能自动弹出」，不会影响文件本身。

    1) Quartus 已在运行 → 子进程消息自动化（Ctrl+O + 填路径，复用现有窗口）
    2) 否则（或自动化失败）→ 交给系统文件关联，由 Quartus 自己打开
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return False, "文件不存在: %s" % path

    if quartus_running() and _try_automation(path, timeout):
        return True, "已在正在运行的 Quartus 中打开"

    ok, msg = _associated_open(path)
    if ok:
        return True, ("已交给 Quartus 打开；若弹出「是否新建工程」提示或欢迎页，"
                      "关掉它即可看到原理图")
    return False, msg


if __name__ == "__main__":
    # 子进程入口：成功打印 OK，失败打印 FAIL + 原因
    _ok, _msg = _automate_open(os.path.abspath(sys.argv[1]))
    print(("OK " if _ok else "FAIL ") + _msg)
    sys.exit(0 if _ok else 1)

