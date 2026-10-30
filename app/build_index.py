# -*- coding: utf-8 -*-
"""扫描 Quartus II 库里的 .bsf 符号文件，生成 symbols.json 索引。"""
import json
import os
import re
import sys

QUARTUS_LIB = r"C:\altera\91\quartus\libraries"

# 库目录 -> 界面分类名
CATEGORIES = {
    "primitives/logic": "门电路",
    "primitives/storage": "触发器",
    "primitives/buffer": "缓冲/驱动器",
    "primitives/other": "其他基本单元",
    "primitives/pin": "输入输出引脚",
    "others/maxplus2": "74 系列 / 经典器件",
    "others/opencore_plus": "其他器件",
}

# 需要 MegaWizard 配置参数的 megafunctions 目录不收录（无法用清单直接复制）
SKIP_DIRS = {"megafunctions", "design_assistant", "sim", "vhdl"}


def parse_geometry(text):
    """从 .bsf 内容里取出符号宽高，失败返回 None。"""
    m = re.search(r"\((?:symbol|pin)\b[\s\S]*?\(rect\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*\)", text)
    if not m:
        return None
    x1, y1, x2, y2 = (int(v) for v in m.groups())
    return x2 - x1, y2 - y1


def build(lib_root):
    items = []
    for dirpath, dirnames, filenames in os.walk(lib_root):
        rel_dir = os.path.relpath(dirpath, lib_root).replace("\\", "/")
        top = rel_dir.split("/")[0]
        if top in SKIP_DIRS:
            continue
        cat = CATEGORIES.get(rel_dir)
        if cat is None:
            continue
        for fn in filenames:
            if not fn.lower().endswith(".bsf"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                with open(full, encoding="latin-1") as f:
                    text = f.read()
            except OSError:
                continue
            geo = parse_geometry(text)
            if not geo:
                continue
            w, h = geo
            items.append({
                "name": os.path.splitext(fn)[0],
                "lib": rel_dir,
                "cat": cat,
                "w": w,
                "h": h,
                "rel": os.path.relpath(full, lib_root).replace("\\", "/"),
            })
    items.sort(key=lambda d: (d["cat"], d["name"].upper()))
    return items


def main():
    lib_root = sys.argv[1] if len(sys.argv) > 1 else QUARTUS_LIB
    if not os.path.isdir(lib_root):
        print("找不到 Quartus 库目录: %s" % lib_root)
        return 1
    items = build(lib_root)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"lib_root": lib_root, "items": items}, f, ensure_ascii=False, indent=1)
    print("已生成 %s，共 %d 个符号" % (out, len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
