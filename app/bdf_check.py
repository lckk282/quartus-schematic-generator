# -*- coding: utf-8 -*-
"""Quartus .bdf 原理图自检器。

Quartus 能编译通过，并不代表图画得对：导线没接到引脚、T 型分支漏了连接点、
两根线的端点重合成短路、导线穿过元件本体……这些都能“0 error”地编译过去，
但在 Block Editor 里打开就是错的。

本模块把 .bdf 解析成几何 + 网表，逐项检查并给出可读报告：

  * 栅格      所有坐标是否为 8 的整数倍（Quartus 画布最小格）
  * 引脚      每个元件引脚 / 顶层引脚是否真的有导线接上
  * 端点      导线端点是否落在引脚、另一根导线端点，或（带连接点的）导线中段
  * 分支      T 型分支处是否放了 junction（否则两段线只是交叉，不算相连）
  * 短路      同一坐标是否被两个不同网络占用（重叠线段、端点重合）
  * 穿模      导线是否从元件本体矩形内部穿过
  * 重叠      元件本体之间是否重叠
  * 网表      每个网络实际连接了哪些引脚

用法：python bdf_check.py 文件.bdf [更多.bdf ...]
"""
import math
import re
import sys
from collections import defaultdict

import bdf_render

GRID = 8


# ---------------------------------------------------------------- 几何收集
class Part:
    __slots__ = ("kind", "name", "inst", "rect", "pins", "contacts")

    def __init__(self, kind, name, inst, rect):
        self.kind = kind          # "symbol" | "pin"
        self.name = name          # 元件名 / 引脚方向
        self.inst = inst          # 实例名
        self.rect = rect          # (x1, y1, x2, y2) 绝对坐标
        self.pins = []            # [(pin_name, x, y, direction)]
        self.contacts = []        # 连接点集合


def _txt(node, index):
    texts = [k for k in node["kids"] if k["tag"] == "text"]
    if len(texts) > index:
        t = texts[index]
        return t["atoms"][0] if t["atoms"] else ""
    return ""


def _rect(node):
    for k in node["kids"]:
        if k["tag"] == "rect" and len(k["atoms"]) >= 4:
            return tuple(int(float(v)) for v in k["atoms"][:4])
    return None


def load(src):
    roots = bdf_render.parse(src)
    parts, segs, juncs, texts = [], [], [], []
    for root in roots:
        tag = root["tag"]
        if tag in ("symbol", "pin"):
            r = _rect(root)
            if not r:
                continue
            kind = "pin" if tag == "pin" else "symbol"
            name = "PIN" if kind == "pin" else _txt(root, 0)
            inst = _txt(root, 1)
            p = Part(kind, name, inst, r)
            for k in root["kids"]:
                if k["tag"] == "port":
                    pt = None
                    direction = ""
                    pname = ""
                    for kk in k["kids"]:
                        if kk["tag"] == "pt" and len(kk["atoms"]) >= 2:
                            pt = (int(float(kk["atoms"][0])), int(float(kk["atoms"][1])))
                        elif kk["tag"] == "input":
                            direction = "input"
                        elif kk["tag"] == "output":
                            direction = "output"
                        elif kk["tag"] == "text" and kk["atoms"]:
                            pname = pname or kk["atoms"][0]
                    if pt:
                        # symbol 的 input 端口是「负载」，output 端口是「驱动源」
                        role = "source" if direction == "output" else "sink"
                        p.pins.append((pname, r[0] + pt[0], r[1] + pt[1], role))
            if kind == "pin":
                dps = [k for k in root["kids"] if k["tag"] == "pt"]
                if dps:
                    x = r[0] + int(float(dps[0]["atoms"][0]))
                    y = r[1] + int(float(dps[0]["atoms"][1]))
                    # 顶层 INPUT 引脚驱动网络，OUTPUT 引脚是负载
                    is_in = "input" in [c["tag"] for c in root["kids"]]
                    p.pins.append((_txt(root, 1), x, y, "source" if is_in else "sink"))
            parts.append(p)
        elif tag == "connector":
            pts = [(int(float(k["atoms"][0])), int(float(k["atoms"][1])))
                   for k in root["kids"] if k["tag"] == "pt" and len(k["atoms"]) >= 2]
            for a, b in zip(pts, pts[1:]):
                if a != b:
                    segs.append((a, b))
        elif tag == "junction":
            for k in root["kids"]:
                if k["tag"] == "pt" and len(k["atoms"]) >= 2:
                    juncs.append((int(float(k["atoms"][0])), int(float(k["atoms"][1]))))
        elif tag == "text":
            texts.append((_txt(root, 0),))
    return parts, segs, juncs, texts


# ---------------------------------------------------------------- 检查
def _on_seg(p, a, b):
    """p 是否严格位于线段 a-b 内部（不含端点）。"""
    (px, py), (ax, ay), (bx, by) = p, a, b
    if ax == bx:                                  # 竖线
        return px == ax and min(ay, by) < py < max(ay, by)
    if ay == by:                                  # 横线
        return py == ay and min(ax, bx) < px < max(ax, bx)
    return False


def _overlap(a1, b1, a2, b2):
    """两条线段是否有共线重叠（不是简单交叉，而是压在一条线上）。"""
    if a1[0] == b1[0] == a2[0] == b2[0]:          # 同竖线
        lo1, hi1 = sorted((a1[1], b1[1]))
        lo2, hi2 = sorted((a2[1], b2[1]))
        return min(hi1, hi2) - max(lo1, lo2) > 0
    if a1[1] == b1[1] == a2[1] == b2[1]:          # 同横线
        lo1, hi1 = sorted((a1[0], b1[0]))
        lo2, hi2 = sorted((a2[0], b2[0]))
        return min(hi1, hi2) - max(lo1, lo2) > 0
    return False


def _crosses_rect(a, b, rect, shrink=2):
    x1, y1, x2, y2 = rect[0] + shrink, rect[1] + shrink, rect[2] - shrink, rect[3] - shrink
    if x1 >= x2 or y1 >= y2:
        return False
    (ax, ay), (bx, by) = a, b
    lo_x, hi_x = sorted((ax, bx))
    lo_y, hi_y = sorted((ay, by))
    # 只关心穿过内部：线段与矩形内部有交集，且不是只碰边
    if ax == bx:
        return x1 < ax < x2 and lo_y < y2 and hi_y > y1
    if ay == by:
        return y1 < ay < y2 and lo_x < x2 and hi_x > x1
    return False


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.notes = []
        self.info = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.notes.append(msg)


def check(src):
    parts, segs, juncs, _texts = load(src)
    rep = Report()

    # ---- 1. 栅格
    off_grid = set()
    for p in parts:
        off_grid.update(v for v in p.rect if v % GRID)
    for a, b in segs:
        off_grid.update(v for pt in (a, b) for v in pt if v % GRID)
    for j in juncs:
        off_grid.update(v for v in j if v % GRID)
    for msg_pt in sorted(off_grid)[:6]:
        rep.warn("坐标 %d 不在 %d 的栅格上，Quartus 里会吸附变形" % (msg_pt, GRID))

    # ---- 2. 导线穿过元件本体
    for p in parts:
        for a, b in segs:
            if _crosses_rect(a, b, p.rect):
                rep.err("%s %s 本体被导线 %s-%s 穿过" % (p.name, p.inst, a, b))
                break

    # ---- 3. 元件本体重叠
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            r1, r2 = parts[i].rect, parts[j].rect
            if r1[0] < r2[2] and r2[0] < r1[2] and r1[1] < r2[3] and r2[1] < r1[3]:
                rep.err("%s(%s) 与 %s(%s) 图形重叠" % (parts[i].name, parts[i].inst,
                                                       parts[j].name, parts[j].inst))

    # ---- 4. 端点 / 连接点
    ends = defaultdict(list)
    for idx, (a, b) in enumerate(segs):
        ends[a].append(idx)
        ends[b].append(idx)
    junctions = set(juncs)
    for pt, idxs in ends.items():
        hitting_pin = any(pt == (x, y) for p in parts for (_n, x, y, _d) in p.pins)
        if len(idxs) > 1 or hitting_pin:
            continue
        # 只有一个端点：必须落在某个引脚上，或落在另一根线中段（且要有 junction）
        on_mid = any(_on_seg(pt, *segs[k]) for k in range(len(segs)) if k not in idxs)
        if on_mid:
            if pt not in junctions:
                rep.err("导线端点 %s 落在另一根导线中段但缺少连接点（Quartus 视为不连接）" % (pt,))
        else:
            rep.err("导线端点 %s 悬空（既不是引脚，也没接到别的线）" % (pt,))

    # ---- 5. 引脚必须被接上
    for p in parts:
        for (pname, x, y, role) in p.pins:
            pt = (x, y)
            touched = pt in ends or any(_on_seg(pt, a, b) for a, b in segs)
            if touched:
                continue
            if role == "sink":
                rep.err("%s(%s) 的输入引脚 %s 没有接线（悬空，功能不成立）"
                        % (p.name, p.inst, pname or "?"))
            else:
                rep.note("%s(%s) 的输出引脚 %s 未使用（不影响功能）"
                         % (p.name, p.inst, pname or "?"))
    for pt in junctions:
        if not any(_on_seg(pt, a, b) for a, b in segs) and pt not in ends:
            rep.warn("连接点 %s 处没有导线" % (pt,))

    # ---- 6. 短路：不同网络共线重叠 / 端点重合
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a1, b1 = segs[i]
            a2, b2 = segs[j]
            if _overlap(a1, b1, a2, b2):
                rep.err("导线 %s-%s 与 %s-%s 重合成短路" % (a1, b1, a2, b2))

    # ---- 7. 网表（union-find：端点相接、经连接点接中线）
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in segs:
        union(a, b)
    for pt in ends:
        find(pt)
    # 连接点把中段也并入
    for j in junctions:
        for a, b in segs:
            if _on_seg(j, a, b):
                union(j, a)
    # 引脚并入网络
    pin_map = {}
    for p in parts:
        for (pname, x, y, direction) in p.pins:
            pt = (x, y)
            find(pt)
            for a, b in segs:
                if pt == a or pt == b or _on_seg(pt, a, b):
                    union(pt, a)
                    break
            pin_map[pt] = (p.inst or p.name, pname, direction)

    nets = defaultdict(list)
    for pt, label in pin_map.items():
        nets[find(pt)].append((label, pt))
    net_list = []
    for root, members in nets.items():
        drivers = [m for m in members if m[0][2] == "source"]
        if len(drivers) > 1:
            rep.err("网络有多个驱动源: %s" % (", ".join("%s.%s" % (m[0][0], m[0][1]) for m in drivers),))
        net_list.append(sorted("%s.%s" % (m[0][0], m[0][1]) for m in members))
    rep.info.append("网络数: %d" % len(net_list))
    return rep, net_list


def summary(path):
    with open(path, encoding="latin-1") as f:
        src = f.read()
    rep, nets = check(src)
    return rep, nets


def main(argv):
    total_err = 0
    for path in argv:
        rep, nets = summary(path)
        print("=" * 78)
        print(path)
        for line in rep.info:
            print("  " + line)
        for m in rep.errors:
            print("  [错误] " + m)
        for m in rep.warnings[:12]:
            print("  [警告] " + m)
        if len(rep.warnings) > 12:
            print("  [警告] ... 共 %d 条" % len(rep.warnings))
        if not rep.errors and not rep.warnings:
            print("  通过")
        total_err += len(rep.errors)
    print("\n合计 %d 个错误" % total_err)
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
