# -*- coding: utf-8 -*-
"""插件配置：读取同目录 config.json（由「安装.bat」生成），缺省时回退到默认值。

所有路径都支持在 config.json 里改，换个电脑装 Quartus 也不用改代码。
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULTS = {
    # Quartus II 9.1 主程序
    "quartus_exe": r"C:\altera\91\quartus\bin64\quartus.exe",
    # Quartus 自带元件库（.bsf 符号文件所在目录）
    "quartus_lib": r"C:\altera\91\quartus\libraries",
    # 生成的工程默认放这里
    "output_dir": os.path.join(os.path.expanduser("~"), "Documents", "QuartusBatch"),
    # 本地网页端口
    "port": 8765,
    # 生成后是否自动在 Quartus 里打开
    "auto_open": True,
}

_cache = None


def load(reload=False):
    global _cache
    if _cache is not None and not reload:
        return _cache
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except Exception as e:  # 配置坏了不能让插件起不来
            print("[config] config.json 读取失败，使用默认值:", e)
    _cache = cfg
    return cfg


def save(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    global _cache
    _cache = None


def app_dir():
    return BASE_DIR


def _pick_quartus():
    """返回第一个存在的 quartus.exe 候选路径。"""
    for p in (load()["quartus_exe"],
              r"C:\altera\91\quartus\bin64\quartus.exe",
              r"C:\altera\91\quartus\bin\quartus.exe",
              r"C:\altera\13.0\quartus\bin64\quartus.exe",
              r"C:\altera\13.1\quartus\bin64\quartus.exe",
              r"C:\intelFPGA_lite\20.1\quartus\bin64\quartus.exe"):
        if p and os.path.exists(p):
            return p
    return load()["quartus_exe"]


def quartus_exe():
    return _pick_quartus()


def quartus_bin_dir():
    return os.path.dirname(quartus_exe())


def pythonw():
    """同目录下的 pythonw.exe（用于无黑框启动服务）。"""
    cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return cand if os.path.exists(cand) else sys.executable
