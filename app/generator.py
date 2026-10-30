# -*- coding: utf-8 -*-
"""把「元件 + 数量」清单生成为 Quartus Block Editor 画布文件（.bdf）。

原理：Quartus 库中每个元件的 .bsf 文件里的 (symbol ...) / (pin ...) 块
与 .bdf 里实例块的格式完全一致，只要改坐标和实例名就能直接拼进 .bdf。
"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYMBOLS_JSON = os.path.join(BASE_DIR, "symbols.json")

MARGIN_X = 80
MARGIN_Y = 80
GAP_X = 48
GAP_Y = 48
MAX_X = 1200

_INDEX = None


def load_symbols():
    global _INDEX
    if _INDEX is None:
        with open(SYMBOLS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        # 若 config.json 指定的 Quartus 库目录存在，就用它（换机器/换安装路径）
        try:
            import config
            lib = config.load()["quartus_lib"]
            if lib and os.path.isdir(lib):
                data["lib_root"] = lib
        except Exception:
            pass
        _INDEX = data
    return _INDEX


def find_symbol(name):
    data = load_symbols()
    key = name.strip().lower()
    for item in data["items"]:
        if item["name"].lower() == key:
            return item
    return None


def _block_start(src):
    """返回 (symbol|pin) 块的起始位置和类型。"""
    best = None
    for token in ("(symbol", "(pin"):
        i = src.find(token)
        if i >= 0 and (best is None or i < best[0]):
            best = (i, token)
    return best


def read_block(bsf_path):
    """读 .bsf，返回不含 header 的实例块源码。"""
    with open(bsf_path, encoding="latin-1") as f:
        src = f.read()
    found = _block_start(src)
    if not found:
        raise ValueError("该符号文件没有可用的符号块: %s" % bsf_path)
    return src[found[0]:].strip()


def _instance_name(block, inst_name):
    """把块头部的实例名（第二个 text）替换成指定名字。"""
    head_end = block.find("(port")
    head = block if head_end < 0 else block[:head_end]
    names = list(re.finditer(r'\(text "([^"]*)"', head))
    if len(names) >= 2:
        m = names[1]
        return block[:m.start(1)] + inst_name + block[m.end(1):]
    return block


RECT_RE = re.compile(r"\(rect\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*\)")


def place(block, x, y):
    """把实例块左上角移动到 (x, y)，宽高保持不变。"""
    head = re.search(r"\((?:symbol|pin)\b", block)
    if not head:
        raise ValueError("无法解析符号块")
    m = RECT_RE.search(block, head.end())
    if not m:
        raise ValueError("无法解析符号坐标")
    x1, y1, x2, y2 = (int(v) for v in m.groups())
    w, h = x2 - x1, y2 - y1
    rect = "(rect %d %d %d %d)" % (x, y, x + w, y + h)
    block = block[:m.start()] + rect + block[m.end():]
    return block, w, h


PORT_RE = re.compile(
    r'\(port \(pt (-?\d+) (-?\d+)\)\((input|output)\)\(text "([^"]*)"')
PIN_PT_RE = re.compile(r"\(pt (-?\d+) (-?\d+)\)")


def geometry(name):
    """读符号定义，返回端口相对锚点的偏移。

    Quartus 的规则：实例内部坐标 = 实例 rect 左上角 + 符号内部坐标。
    返回 {"w","h","ports":{端口名:(dx,dy,方向)},"kind":"symbol"|"pin"}；
    pin 类型额外返回 "conn":(dx,dy)，即引脚连接点偏移。
    """
    info = find_symbol(name)
    if not info:
        raise ValueError("库里找不到元件: %s" % name)
    raw = read_block(os.path.join(load_symbols()["lib_root"], info["rel"]))
    m = RECT_RE.search(raw)
    if not m:
        raise ValueError("无法解析符号坐标: %s" % name)
    x1, y1, x2, y2 = (int(v) for v in m.groups())
    kind = "symbol" if raw.lstrip().startswith("(symbol") else "pin"
    ports = {}
    for pm in PORT_RE.finditer(raw):
        dx, dy, direction, pname = int(pm.group(1)), int(pm.group(2)), pm.group(3), pm.group(4)
        ports[pname] = (dx, dy, direction)
    result = {"w": x2 - x1, "h": y2 - y1, "ports": ports, "kind": kind}
    if kind == "pin":
        pm = PIN_PT_RE.search(raw)
        if pm:
            result["conn"] = (int(pm.group(1)), int(pm.group(2)))
            direction = "input" if "(pin (input)" in raw else "output"
            # 引脚的连接点就是它唯一的「端口」，供走线/校验统一使用
            result["ports"] = {"PIN": (result["conn"][0], result["conn"][1], direction)}
    return result


def build_bdf(items, lib_root=None):
    """items: [{"name": "7490", "count": 3}, ...] -> .bdf 文本。"""
    data = load_symbols()
    lib_root = lib_root or data["lib_root"]

    parts = ['(header "graphic" (version "1.3"))']
    x = MARGIN_X
    y = MARGIN_Y
    row_h = 0
    index = 0
    placed = []

    for entry in items:
        name = entry.get("name", "")
        try:
            count = int(entry.get("count", 1))
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(count, 500))
        info = find_symbol(name)
        if not info:
            raise ValueError("库里找不到元件: %s" % name)
        raw = read_block(os.path.join(lib_root, info["rel"]))
        for _ in range(count):
            inst = "inst" if index == 0 else "inst%d" % index
            body, w, h = place(_instance_name(raw, inst), x, y)
            parts.append(body)
            placed.append({"name": info["name"], "x": x, "y": y})
            index += 1
            x += w + GAP_X
            row_h = max(row_h, h)
            if x + w > MAX_X:
                x = MARGIN_X
                y += row_h + GAP_Y
                row_h = 0

    text = "\n".join(parts) + "\n"
    return text, placed


def generate_to_file(items, out_path, lib_root=None):
    text, placed = build_bdf(items, lib_root)
    write_text(out_path, text)
    return placed


def write_text(out_path, text):
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_path, "w", encoding="latin-1", newline="\n") as f:
        f.write(text)
