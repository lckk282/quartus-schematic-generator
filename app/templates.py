# -*- coding: utf-8 -*-
"""内置电路模板：直接生成已排序、已连好的 .bdf。

版式规则（与 Quartus 一致）：
  元件内部坐标 = 实例 rect 左上角 + 符号内部坐标
  所以端口绝对坐标 = 实例锚点 + .bsf 里 port 的 (pt dx dy)
"""
import os
import time

import generator


TEMPLATES = [
    {
        "id": "full_adder",
        "group": "组合逻辑",
        "name": "一位全加器",
        "desc": "XOR×2 + AND2×2 + OR2×1，Sum=A⊕B⊕Cin，Cout=AB+Cin(A⊕B)",
        "items": [
            {"name": "xor", "count": 2},
            {"name": "and2", "count": 2},
            {"name": "or2", "count": 1},
            {"name": "INPUT", "count": 3},
            {"name": "OUTPUT", "count": 2},
        ],
    },
    {
        "id": "half_adder",
        "group": "组合逻辑",
        "name": "半加器",
        "desc": "XOR×1 + AND2×1，Sum=A⊕B，Carry=A·B",
        "items": [{"name": "xor", "count": 1}, {"name": "and2", "count": 1},
                  {"name": "INPUT", "count": 2}, {"name": "OUTPUT", "count": 2}],
    },
    {
        "id": "decoder_3to8",
        "group": "组合逻辑",
        "name": "3-8 译码器（74138）",
        "desc": "74LS138：C B A 三位地址 → Y0N..Y7N 低有效输出，使能端 G1 接高、G2AN/G2BN 接低",
        "items": [{"name": "74138", "count": 1}, {"name": "gnd", "count": 2},
                  {"name": "vcc", "count": 1}, {"name": "INPUT", "count": 3},
                  {"name": "OUTPUT", "count": 8}],
    },
    {
        "id": "mux_8to1",
        "group": "组合逻辑",
        "name": "8 选 1 数据选择器（74151）",
        "desc": "74LS151：D0..D7 八路数据 + C B A 选择 → Y / WN（反相）",
        "items": [{"name": "74151", "count": 1}, {"name": "gnd", "count": 1},
                  {"name": "INPUT", "count": 11}, {"name": "OUTPUT", "count": 2}],
    },
    {
        "id": "mux_4to1",
        "group": "组合逻辑",
        "name": "双 4 选 1 选择器（74153）",
        "desc": "74LS153：AB 公共选择，1C0..1C3→1Y，2C0..2C3→2Y",
        "items": [{"name": "74153", "count": 1}, {"name": "gnd", "count": 2},
                  {"name": "INPUT", "count": 10}, {"name": "OUTPUT", "count": 2}],
    },
    {
        "id": "seven_seg_7447",
        "group": "组合逻辑",
        "name": "七段译码器（7447）",
        "desc": "74LS47：D C B A 的 BCD → OA..OG 七段（共阳，低有效），熄灭/灭零端接高",
        "items": [{"name": "7447", "count": 1}, {"name": "vcc", "count": 3},
                  {"name": "INPUT", "count": 4}, {"name": "OUTPUT", "count": 8}],
    },
    {
        "id": "comparator_4bit",
        "group": "组合逻辑",
        "name": "四位数值比较器（7485）",
        "desc": "74LS85：A3..A0 与 B3..B0 比较 → ALBO(A<B)/AEBO(A=B)/AGBO(A>B)，级联输入接默认值",
        "items": [{"name": "7485", "count": 1}, {"name": "gnd", "count": 2},
                  {"name": "vcc", "count": 1}, {"name": "INPUT", "count": 8},
                  {"name": "OUTPUT", "count": 3}],
    },
    {
        "id": "adder_4bit_chip",
        "group": "组合逻辑",
        "name": "四位加法器（74283）",
        "desc": "74LS283：A4..A1 + B4..B1 + C0 → S4..S1 与进位 C4",
        "items": [{"name": "7483", "count": 1}, {"name": "INPUT", "count": 9},
                  {"name": "OUTPUT", "count": 5}],
    },
    {
        "id": "mod60",
        "group": "计数器",
        "name": "模 60 计数器（7490）",
        "desc": "两片 7490：个位十进制、十位六进制，QC·QB 反馈归零，COUT 在 59 时进位",
        "items": [
            {"name": "7490", "count": 2},
            {"name": "and2", "count": 1},
            {"name": "and4", "count": 1},
            {"name": "gnd", "count": 1},
            {"name": "INPUT", "count": 1},
            {"name": "OUTPUT", "count": 9},
        ],
    },
    {
        "id": "mod24",
        "group": "计数器",
        "name": "模 24 计数器（7490）",
        "desc": "两片 7490：个位十进制、十位三进制；计到 24 归零，COUT 在 23 时进位",
        "items": [
            {"name": "7490", "count": 2},
            {"name": "and2", "count": 1},
            {"name": "and3", "count": 1},
            {"name": "gnd", "count": 1},
            {"name": "INPUT", "count": 1},
            {"name": "OUTPUT", "count": 9},
        ],
    },
    {
        "id": "mod100",
        "group": "计数器",
        "name": "模 100 计数器（7490）",
        "desc": "两片 7490 级联成 00~99，天然回环不需要反馈门，COUT 在 99 时进位",
        "items": [
            {"name": "7490", "count": 2},
            {"name": "and4", "count": 1},
            {"name": "gnd", "count": 1},
            {"name": "INPUT", "count": 1},
            {"name": "OUTPUT", "count": 9},
        ],
    },
    {
        "id": "counter_74161",
        "group": "计数器",
        "name": "四位二进制计数器（74161）",
        "desc": "74LS161：CLK 计数 → QA..QD，进位 RCO；置数/清零/使能端已按“常计数”接好",
        "items": [{"name": "74161", "count": 1}, {"name": "gnd", "count": 4},
                  {"name": "vcc", "count": 4}, {"name": "INPUT", "count": 1},
                  {"name": "OUTPUT", "count": 5}],
    },
    {
        "id": "counter_74160",
        "group": "计数器",
        "name": "十进制计数器（74160）",
        "desc": "74LS160：CLK 计数 0..9（BCD）→ QA..QD，进位 RCO",
        "items": [{"name": "74160", "count": 1}, {"name": "gnd", "count": 4},
                  {"name": "vcc", "count": 4}, {"name": "INPUT", "count": 1},
                  {"name": "OUTPUT", "count": 5}],
    },
    {
        "id": "register_74175",
        "group": "时序逻辑",
        "name": "四位寄存器（74175）",
        "desc": "74LS175：1D..4D 在 CLK 上升沿锁存 → 1Q..4Q，清零端 CLRN 接高",
        "items": [{"name": "74175", "count": 1}, {"name": "vcc", "count": 1},
                  {"name": "INPUT", "count": 5}, {"name": "OUTPUT", "count": 4}],
    },
    {
        "id": "shift_74194",
        "group": "时序逻辑",
        "name": "四位双向移位寄存器（74194）",
        "desc": "74LS194：右移模式(S1S0=01)，SRSI 串行输入 → QA..QD",
        "items": [{"name": "74194", "count": 1}, {"name": "gnd", "count": 5},
                  {"name": "vcc", "count": 2}, {"name": "INPUT", "count": 2},
                  {"name": "OUTPUT", "count": 4}],
    },
    {
        "id": "dff_flipflop",
        "group": "时序逻辑",
        "name": "D 触发器",
        "desc": "D 在 CLK 上升沿锁存到 Q；置位/清零端接高，均不动作",
        "items": [{"name": "dff", "count": 1}, {"name": "vcc", "count": 2},
                  {"name": "INPUT", "count": 2}, {"name": "OUTPUT", "count": 1}],
    },
    {
        "id": "jk_flipflop",
        "group": "时序逻辑",
        "name": "JK 触发器",
        "desc": "J、K 在 CLK 上升沿更新 Q；置位/清零端接高，均不动作",
        "items": [{"name": "jkff", "count": 1}, {"name": "vcc", "count": 2},
                  {"name": "INPUT", "count": 3}, {"name": "OUTPUT", "count": 1}],
    },
    {
        "id": "div2",
        "group": "时序逻辑",
        "name": "二分频器",
        "desc": "D 触发器把 Q 取反后送回 D，输出为输入时钟的二分频",
        "items": [{"name": "dff", "count": 1}, {"name": "not", "count": 1},
                  {"name": "vcc", "count": 2}, {"name": "INPUT", "count": 1},
                  {"name": "OUTPUT", "count": 1}],
    },
    {
        "id": "ring_counter",
        "group": "时序逻辑",
        "name": "扭环计数器（74194）",
        "desc": "74LS194 右移模式 + 反相反馈（/QD→SRSI）构成 Johnson 计数器，"
                "自启动 8 个状态，四位循环点亮",
        "items": [{"name": "74194", "count": 1}, {"name": "not", "count": 1},
                  {"name": "gnd", "count": 6}, {"name": "vcc", "count": 2},
                  {"name": "INPUT", "count": 1}, {"name": "OUTPUT", "count": 4}],
    },
    {
        "id": "digital_clock",
        "group": "综合系统",
        "name": "数字秒表（顶层，7490）",
        "desc": "四个计数器元件级联：0.01s(模100)→秒(模60)→分(模60)→时(模24)，24h 自动归零；"
                "同时生成子元件 .bdf 与 .bsf 符号文件，可直接编译",
        "items": [
            {"name": "7490", "count": 8},
            {"name": "and2", "count": 3},
            {"name": "and3", "count": 1},
            {"name": "and4", "count": 2},
            {"name": "gnd", "count": 4},
        ],
    },
    {
        "id": "adder_4bit",
        "group": "组合逻辑",
        "name": "四位全加器（门电路）",
        "desc": "4 级一位全加器串接（行波进位）：A3..A0 + B3..B0 + Cin = Cout:S3..S0",
        "items": [
            {"name": "xor", "count": 8},
            {"name": "and2", "count": 8},
            {"name": "or2", "count": 4},
            {"name": "INPUT", "count": 9},
            {"name": "OUTPUT", "count": 5},
        ],
    },
]


def connector(x1, y1, x2, y2):
    return "(connector (pt %d %d)(pt %d %d))" % (x1, y1, x2, y2)


def junction(x, y):
    return "(junction (pt %d %d))" % (x, y)


def _raw(name):
    info = generator.find_symbol(name)
    if not info:
        raise ValueError("库里找不到元件: %s" % name)
    return generator.read_block(os.path.join(generator.load_symbols()["lib_root"], info["rel"]))


def _gate(parts, name, inst_name, x, y):
    """放一个门，返回 {端口名: 绝对坐标}。"""
    raw = _raw(name)
    body, _w, _h = generator.place(generator._instance_name(raw, inst_name), x, y)
    parts.append(body)
    geom = generator.geometry(name)
    return {p: (x + dx, y + dy) for p, (dx, dy, _d) in geom["ports"].items()}


def _pin(parts, kind, pin_name, conn_x, conn_y):
    """按连接点位置放输入/输出引脚。"""
    geom = generator.geometry(kind)
    dx, dy = geom.get("conn", (0, 8))
    body, _w, _h = generator.place(
        generator._instance_name(_raw(kind), pin_name), conn_x - dx, conn_y - dy)
    parts.append(body)
    return (conn_x, conn_y)


def _subtract(a, b, a2, b2):
    """从线段 a-b 里扣掉与 a2-b2 共线重叠的部分，返回剩下的线段列表。"""
    if a[0] == b[0] == a2[0] == b2[0]:                     # 同一条竖线
        lo, hi = sorted((a[1], b[1]))
        lo2, hi2 = sorted((a2[1], b2[1]))
        if hi <= lo2 or hi2 <= lo:
            return [(a, b)]
        out = []
        if lo < lo2:
            out.append(((a[0], lo), (a[0], lo2)))
        if hi2 < hi:
            out.append(((a[0], hi2), (a[0], hi)))
        return out
    if a[1] == b[1] == a2[1] == b2[1]:                     # 同一条横线
        lo, hi = sorted((a[0], b[0]))
        lo2, hi2 = sorted((a2[0], b2[0]))
        if hi <= lo2 or hi2 <= lo:
            return [(a, b)]
        out = []
        if lo < lo2:
            out.append(((lo, a[1]), (lo2, a[1])))
        if hi2 < hi:
            out.append(((hi2, a[1]), (hi, a[1])))
        return out
    return [(a, b)]


def _on_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    if ax == bx:
        return px == ax and min(ay, by) < py < max(ay, by)
    if ay == by:
        return py == ay and min(ax, bx) < px < max(ax, bx)
    return False


def _as_seg(item):
    """导线既可以写成 (x1,y1,x2,y2)，也可以写成 ((x1,y1),(x2,y2))。"""
    if len(item) == 4:
        x1, y1, x2, y2 = item
        return (int(x1), int(y1)), (int(x2), int(y2))
    (x1, y1), (x2, y2) = item
    return (int(x1), int(y1)), (int(x2), int(y2))


def emit_wires(parts, wires):
    """把导线列表写进画布，并且自动做到三件事：

      1. 去掉与已有导线重合的段（同一条线不重复画，避免“看起来短路”）；
      2. 在 T 型分支（某条线端点落在另一条线中段）处补上 junction，
         否则 Quartus 认为只是交叉、不连接；
      3. 把被分支的那条线在该点断开成两段，和 Quartus 自己保存的 .bdf 一致。

    这样各模板只需要给出“从 A 到 B”的路径，连接点不会再漏。
    """
    segs = []
    for item in wires:
        a, b = _as_seg(item)
        if a == b:
            continue
        queue = [(a, b)]
        while queue:
            na, nb = queue.pop(0)
            clash = None
            for sa, sb in segs:
                if _on_seg(na, sa, sb) and _on_seg(nb, sa, sb):
                    clash = (sa, sb)
                    break
            if clash:
                continue                                    # 完全被已有导线覆盖
            rest = [(na, nb)]
            for sa, sb in segs:
                nxt = []
                for ra, rb in rest:
                    nxt += _subtract(ra, rb, sa, sb)
                rest = nxt
            segs.extend(rest)

    junctions = set()
    for a, b in segs:
        for p in (a, b):
            for sa, sb in segs:
                if _on_seg(p, sa, sb):
                    junctions.add(p)

    # 在被分支的导线中段断开
    if junctions:
        split = []
        for a, b in segs:
            cuts = [p for p in junctions if _on_seg(p, a, b)]
            if not cuts:
                split.append((a, b))
                continue
            if a[0] == b[0]:
                cuts.sort(key=lambda p: p[1], reverse=b[1] < a[1])
            else:
                cuts.sort(key=lambda p: p[0], reverse=b[0] < a[0])
            pts = [a] + cuts + [b]
            split += list(zip(pts, pts[1:]))
        segs = split

    for a, b in segs:
        parts.append(connector(a[0], a[1], b[0], b[1]))
    for p in sorted(junctions):
        parts.append(junction(p[0], p[1]))


def full_adder():
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "1-bit Full Adder  SUM = A XOR B XOR Cin   COUT = AB + Cin(A XOR B)"'
                 '(rect 192 48 860 64)(font "Courier New"(font_size 9)(bold)))')

    # 所有坐标取 8 的整数倍（Quartus 画布最小格），否则导线不会被识别为连接
    a = _pin(parts, "INPUT", "A", 192, 160)
    b = _pin(parts, "INPUT", "B", 192, 240)
    cin = _pin(parts, "INPUT", "Cin", 192, 96)
    s = _pin(parts, "OUTPUT", "SUM", 1536, 216)
    cout = _pin(parts, "OUTPUT", "COUT", 1536, 312)

    x1 = _gate(parts, "xor", "U1", 320, 192)      # A ⊕ B
    a1 = _gate(parts, "and2", "U2", 320, 384)     # A · B
    x2 = _gate(parts, "xor", "U3", 704, 192)      # (A ⊕ B) ⊕ Cin = SUM
    a2 = _gate(parts, "and2", "U4", 704, 384)     # Cin · (A ⊕ B)
    o1 = _gate(parts, "or2", "U5", 1088, 288)     # Cout

    wires = [
        # A -> U1.IN1 / U2.IN1
        (a[0], a[1], 224, a[1]),
        (224, a[1], 224, a1["IN1"][1]),
        (224, x1["IN1"][1], x1["IN1"][0], x1["IN1"][1]),
        (224, a1["IN1"][1], x1["IN1"][0], a1["IN1"][1]),
        # B -> U1.IN2 / U2.IN2
        (b[0], b[1], 256, b[1]),
        (256, x1["IN2"][1], 256, a1["IN2"][1]),
        (256, x1["IN2"][1], x1["IN2"][0], x1["IN2"][1]),
        (256, a1["IN2"][1], x1["IN2"][0], a1["IN2"][1]),
        # Cin -> U3.IN2 / U4.IN2
        (cin[0], cin[1], 576, cin[1]),
        (576, cin[1], 576, a2["IN2"][1]),
        (576, x2["IN2"][1], x2["IN2"][0], x2["IN2"][1]),
        (576, a2["IN2"][1], x2["IN2"][0], a2["IN2"][1]),
        # U1.OUT -> U3.IN1 / U4.IN1
        (x1["OUT"][0], x1["OUT"][1], 512, x1["OUT"][1]),
        (512, x2["IN1"][1], 512, a2["IN1"][1]),
        (512, x2["IN1"][1], x2["IN1"][0], x2["IN1"][1]),
        (512, a2["IN1"][1], x2["IN1"][0], a2["IN1"][1]),
        # U3.OUT -> SUM
        (x2["OUT"][0], x2["OUT"][1], s[0], s[1]),
        # U2.OUT -> U5.IN1（从下方绕开 U4）
        (a1["OUT"][0], a1["OUT"][1], 600, a1["OUT"][1]),
        (600, a1["OUT"][1], 600, 264),
        (600, 264, 1024, 264),
        (1024, 264, 1024, o1["IN1"][1]),
        (1024, o1["IN1"][1], o1["IN1"][0], o1["IN1"][1]),
        # U4.OUT -> U5.IN2
        (a2["OUT"][0], a2["OUT"][1], 960, a2["OUT"][1]),
        (960, a2["OUT"][1], 960, o1["IN2"][1]),
        (960, o1["IN2"][1], o1["IN2"][0], o1["IN2"][1]),
        # U5.OUT -> COUT
        (o1["OUT"][0], o1["OUT"][1], cout[0], cout[1]),
    ]
    emit_wires(parts, wires)

    # 分支点的连接点由 emit_wires 自动补齐
    return "\n".join(parts) + "\n"


BAND_H = 512          # 每位占一条横向带，带宽取 512（8 的整数倍）
CARRY_X = 1800        # 进位竖直通道，放在输出引脚符号右侧，避免压到图形


def ripple_adder(bits=4):
    """N 位行波进位全加器：把一位全加器逐级串接。

    每一位 = 一个一位全加器单元（XOR×2 + AND2×2 + OR2×1），
    本级进位从 OR2 输出向右拉到竖直通道，下落一位后绕回下一级的 Cin 干线。
    """
    parts = ['(header "graphic" (version "1.3"))']
    parts.append(
        '(text "%d-bit Ripple Carry Adder   {Cout,S3..S0} = A3..A0 + B3..B0 + Cin"'
        '(rect 192 32 1500 48)(font "Courier New"(font_size 9)(bold)))' % bits)

    cin = _pin(parts, "INPUT", "Cin", 192, 96)
    cout = _pin(parts, "OUTPUT", "COUT", 1536, (bits - 1) * BAND_H + 312)

    bands = []
    for i in range(bits):
        oy = i * BAND_H
        bands.append({
            "oy": oy,
            "a": _pin(parts, "INPUT", "A%d" % i, 192, oy + 160),
            "b": _pin(parts, "INPUT", "B%d" % i, 192, oy + 240),
            "s": _pin(parts, "OUTPUT", "S%d" % i, 1536, oy + 216),
            "x1": _gate(parts, "xor", "U%d" % (i * 5 + 1), 320, oy + 192),   # A ⊕ B
            "a1": _gate(parts, "and2", "U%d" % (i * 5 + 2), 320, oy + 384),  # A · B
            "x2": _gate(parts, "xor", "U%d" % (i * 5 + 3), 704, oy + 192),   # ⊕ Cin = S
            "a2": _gate(parts, "and2", "U%d" % (i * 5 + 4), 704, oy + 384),  # Cin · (A⊕B)
            "o1": _gate(parts, "or2", "U%d" % (i * 5 + 5), 1088, oy + 288),  # Cout
        })

    wires = []
    for i, bd in enumerate(bands):
        oy = bd["oy"]
        a, b, s = bd["a"], bd["b"], bd["s"]
        x1, a1, x2, a2, o1 = bd["x1"], bd["a1"], bd["x2"], bd["a2"], bd["o1"]

        # 本位 Cin 干线：第 0 位接 Cin 引脚，其余接上一级的进位竖直通道
        cin_x = cin[0] if i == 0 else CARRY_X
        wires += [
            (cin_x, oy + 96, 576, oy + 96),
            (576, oy + 96, 576, a2["IN2"][1]),
            (576, x2["IN2"][1], x2["IN2"][0], x2["IN2"][1]),
            (576, a2["IN2"][1], x2["IN2"][0], a2["IN2"][1]),
            # A -> U1.IN1 / U2.IN1
            (a[0], a[1], 224, a[1]),
            (224, a[1], 224, a1["IN1"][1]),
            (224, x1["IN1"][1], x1["IN1"][0], x1["IN1"][1]),
            (224, a1["IN1"][1], x1["IN1"][0], a1["IN1"][1]),
            # B -> U1.IN2 / U2.IN2
            (b[0], b[1], 256, b[1]),
            (256, x1["IN2"][1], 256, a1["IN2"][1]),
            (256, x1["IN2"][1], x1["IN2"][0], x1["IN2"][1]),
            (256, a1["IN2"][1], x1["IN2"][0], a1["IN2"][1]),
            # U1.OUT -> U3.IN1 / U4.IN1
            (x1["OUT"][0], x1["OUT"][1], 512, x1["OUT"][1]),
            (512, x2["IN1"][1], 512, a2["IN1"][1]),
            (512, x2["IN1"][1], x2["IN1"][0], x2["IN1"][1]),
            (512, a2["IN1"][1], x2["IN1"][0], a2["IN1"][1]),
            # U3.OUT -> SUM
            (x2["OUT"][0], x2["OUT"][1], s[0], s[1]),
            # U2.OUT -> U5.IN1（从下方绕开 U4）
            (a1["OUT"][0], a1["OUT"][1], 600, a1["OUT"][1]),
            (600, a1["OUT"][1], 600, oy + 264),
            (600, oy + 264, 1024, oy + 264),
            (1024, oy + 264, 1024, o1["IN1"][1]),
            (1024, o1["IN1"][1], o1["IN1"][0], o1["IN1"][1]),
            # U4.OUT -> U5.IN2
            (a2["OUT"][0], a2["OUT"][1], 960, a2["OUT"][1]),
            (960, a2["OUT"][1], 960, o1["IN2"][1]),
            (960, o1["IN2"][1], o1["IN2"][0], o1["IN2"][1]),
        ]
        if i < bits - 1:
            # 进位：本级 Cout → 右侧竖直通道 → 下一级 Cin 干线
            wires += [
                (o1["OUT"][0], o1["OUT"][1], CARRY_X, o1["OUT"][1]),
                (CARRY_X, o1["OUT"][1], CARRY_X, oy + BAND_H + 96),
            ]
        else:
            wires.append((o1["OUT"][0], o1["OUT"][1], cout[0], cout[1]))

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


# ---------------- 7490 计数器单元（模 24 / 模 60 / 模 100） ----------------
# 版式：N1 = 个位，N2 = 十位，两片左右排开（实例名不能和引脚名重名，否则报
# "already defined as a signal name"，所以叫 N1/N2 而不是 U1/U2）。
# 每个 7490 的 Q 输出都引一条专属竖直通道：既下到底部的输出引脚，
# 又被复位/进位译码门用连接点抽头，这样任意译码组合都不用重排走线。
_X_CH = {                                   # 通道 x（8 的整数倍，互不重叠）
    "N1": {"QA": 616, "QB": 640, "QC": 664, "QD": 688},
    "N2": {"QA": 1072, "QB": 1080, "QC": 1096, "QD": 1104},
}
_Y_OUT = {                                  # 底部输出引脚的 y
    "N1": {"QA": 880, "QB": 912, "QC": 944, "QD": 976},
    "N2": {"QA": 1008, "QB": 1040, "QC": 1072, "QD": 1104},
}
_OUT_NAME = {                               # 输出引脚名：U=个位片 T=十位片，0 是最低位
    "N1": {"QA": "U0", "QB": "U1", "QC": "U2", "QD": "U3"},
    "N2": {"QA": "T0", "QB": "T1", "QC": "T2", "QD": "T3"},
}
_RESET_RAIL = 1296      # 反馈复位干线（顶部）
_RESET_Y = 160
_TAP_Y = 200            # 输出通道向上延伸到的抽头高度（译码门都在这之上取信号）
_OUT_X = 1488           # 底部/右侧输出引脚的连接点 x（8 的整数倍）
_GND_BUS = {"N1": 432, "N2": 912}       # SET9 接地竖线
_CLR_BUS = {"N1": 456, "N2": 936}       # CLRA/CLRB 竖线（接复位干线或接地）


def _counter_cell(title, reset_bits, carry_bits):
    """两片 7490 组成的计数器。

    reset_bits / carry_bits 形如 [("N1","QD"), ("N2","QA"), ...]；
    reset_bits 为空表示不用反馈门（自然模 100），CLRA/CLRB 直接接地。
    """
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "%s"(rect 192 32 1504 48)'
                 '(font "Courier New"(font_size 9)(bold)))' % title)

    clk = _pin(parts, "INPUT", "CLK", 240, 568)
    n1 = _gate(parts, "7490", "N1", 480, 480)
    n2 = _gate(parts, "7490", "N2", 960, 480)
    gnd = _gate(parts, "gnd", "GND1", 336, 96)
    ports = {"N1": n1, "N2": n2}
    wires = []

    # 时钟进个位；个位的 QD 下降沿给十位当时钟（7490 是下降沿触发）
    wires.append((clk[0], clk[1], n1["CLKA"][0], n1["CLKA"][1]))
    wires.append((n1["QD"][0], n1["QD"][1], n2["CLKA"][0], n2["CLKA"][1]))

    # 先把两个译码门摆好，才知道每条输出通道要向上延伸到哪个高度
    rst = _gate(parts, "and2", "G1", 1152, 240) if reset_bits else None
    gate_name = {2: "and2", 3: "and3", 4: "and4"}[len(carry_bits)]
    cg = _gate(parts, gate_name, "G2", 1152, 640)
    gate_taps = []
    if rst:
        gate_taps += [(src, rst[key]) for src, key in zip(reset_bits, ("IN1", "IN2"))]
    gate_taps += [(src, cg[key]) for src, key in
                  zip(carry_bits, ("IN1", "IN2", "IN3", "IN4"))]

    tap_tops = {}
    for src, (_tx, ty) in gate_taps:
        tap_tops.setdefault(src, []).append(ty)

    # 每个输出：引脚 -> 竖直通道 -> 底部输出引脚。
    # 通道按需向上延伸到「抽头高度」或抽头区（QA 要接自己的 CLKB），
    # 不会被抽头的通道就只向下走，绝不留下悬空线段。
    for u in ("N1", "N2"):
        for bit in ("QA", "QB", "QC", "QD"):
            sx, sy = ports[u][bit]
            cx, cy = _X_CH[u][bit], _Y_OUT[u][bit]
            wires.append((sx, sy, cx, sy))
            tops = [sy] + tap_tops.get((u, bit), [])
            if bit == "QA":
                tops.append(_TAP_Y)
            top = min(tops)
            if top < sy:
                wires.append((cx, top, cx, sy))
            wires.append((cx, sy, cx, cy))
            wires.append((cx, cy, _OUT_X, cy))
            _pin(parts, "OUTPUT", _OUT_NAME[u][bit], _OUT_X, cy)

    # 十进制接法：QA -> 自己的 CLKB（QA 下降沿让 QB..QD 进位，凑成 8421 BCD）
    for u, lx in (("N1", 408), ("N2", 888)):
        cx = _X_CH[u]["QA"]
        wires.append((cx, _TAP_Y, lx, _TAP_Y))
        wires.append((lx, _TAP_Y, lx, ports[u]["CLKB"][1]))
        wires.append((lx, ports[u]["CLKB"][1], ports[u]["CLKB"][0], ports[u]["CLKB"][1]))

    # 接地干线：SET9A/SET9B 恒低（永不置 9）；模 100 时 CLRA/CLRB 也一起接地
    gx, gy = gnd["1"]
    bus_xs = [_GND_BUS["N1"], _GND_BUS["N2"]]
    if not reset_bits:
        bus_xs += [_CLR_BUS["N1"], _CLR_BUS["N2"]]
    trunk_end = max(bus_xs)
    wires.append((gx, gy, trunk_end, gy))
    for u in ("N1", "N2"):
        ch = _GND_BUS[u]
        wires.append((ch, gy, ch, ports[u]["SET9B"][1]))
        wires.append((ch, ports[u]["SET9B"][1], ports[u]["SET9B"][0], ports[u]["SET9B"][1]))
        wires.append((ch, ports[u]["SET9A"][1], ports[u]["SET9A"][0], ports[u]["SET9A"][1]))

    # 译码门抽头：从输出通道的竖直段横向接到门的输入脚
    for src, (tx, ty) in gate_taps:
        wires.append((_X_CH[src[0]][src[1]], ty, tx, ty))

    # 反馈复位：译码门输出 -> 顶部干线 -> 两片的 CLRA/CLRB
    if rst:
        ox, oy = rst["OUT"]
        wires.append((ox, oy, _RESET_RAIL, oy))
        wires.append((_RESET_RAIL, oy, _RESET_RAIL, _RESET_Y))
        wires.append((_RESET_RAIL, _RESET_Y, _CLR_BUS["N1"], _RESET_Y))
        top = _RESET_Y
    else:
        top = gy

    for u in ("N1", "N2"):
        ch = _CLR_BUS[u]
        wires.append((ch, top, ch, ports[u]["CLRB"][1]))
        wires.append((ch, ports[u]["CLRB"][1], ports[u]["CLRB"][0], ports[u]["CLRB"][1]))
        wires.append((ch, ports[u]["CLRA"][1], ports[u]["CLRA"][0], ports[u]["CLRA"][1]))

    # 进位译码：59（或 23 / 99）时 COUT 输出 1
    cout = _pin(parts, "OUTPUT", "COUT", 1352, cg["OUT"][1])
    wires.append((cg["OUT"][0], cg["OUT"][1], cout[0], cout[1]))

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


def counter_mod60():
    """00~59：十位到 6（QB·QC）即反馈归零；59（十位 5、个位 9）时 COUT 进位。"""
    return _counter_cell(
        "Mod-60 Counter (7490 x2)   CLK -> U0..U3 / T0..T3, COUT at 59",
        [("N2", "QB"), ("N2", "QC")],
        [("N2", "QA"), ("N2", "QC"), ("N1", "QA"), ("N1", "QD")],
    )


def counter_mod24():
    """00~23：十位为 2 且个位为 4 时归零；23（十位 2、个位 3）时 COUT 进位。"""
    return _counter_cell(
        "Mod-24 Counter (7490 x2)   CLK -> U0..U3 / T0..T3, COUT at 23",
        [("N2", "QB"), ("N1", "QC")],
        [("N2", "QB"), ("N1", "QA"), ("N1", "QB")],
    )


def counter_mod100():
    """00~99：两片十进制级联自然回环，不需要反馈门；99 时 COUT 进位。"""
    return _counter_cell(
        "Mod-100 Counter (7490 x2)   CLK -> U0..U3 / T0..T3, COUT at 99",
        [],
        [("N2", "QA"), ("N2", "QD"), ("N1", "QA"), ("N1", "QD")],
    )


# ---------------- 顶层：数字秒表（调用三个计数器元件） ----------------
# 层级符号：一个矩形，左边一个 CLK，右边 8 个 Q 输出 + 1 个 COUT。
# 引脚坐标全为 8 的整数倍；符号内部坐标 = 实例 rect 左上角 + 符号内坐标。
SYM_W = 240
Q_Y0 = 32
SYM_CLK_Y = 144
SYM_COUT_Y = 288


def _hier_symbol(entity, q_names, clk_name="CLK"):
    """生成层次实体的矩形符号块（和 Quartus 生成的 .bsf 结构一致）。"""
    h = SYM_COUT_Y + 32
    out = ['(symbol (rect 0 0 %d %d)' % (SYM_W, h)]
    out.append('(text "%s"(rect 8 4 %d 20)(font "Arial"(font_size 10)))'
               % (entity, 8 + 9 * len(entity)))
    out.append('(text "inst1"(rect 8 24 48 34)(font "Arial"(font_size 6)))')
    out.append('(port (pt 0 %d)(input)(text "%s"(rect 10 %d 40 %d)(font "Arial"(font_size 8)))'
               '(text "%s"(rect 10 %d 40 %d)(font "Arial"(font_size 8)))'
               '(line (pt 0 %d)(pt 16 %d)(line_width 1)))'
               % (SYM_CLK_Y, clk_name, SYM_CLK_Y - 7, SYM_CLK_Y + 7,
                  clk_name, SYM_CLK_Y - 7, SYM_CLK_Y + 7, SYM_CLK_Y, SYM_CLK_Y))
    for i, q in enumerate(q_names):
        y = Q_Y0 + 32 * i
        out.append('(port (pt %d %d)(output)(text "%s"(rect %d %d %d %d)(font "Arial"(font_size 8)))'
                   '(text "%s"(rect %d %d %d %d)(font "Arial"(font_size 8)))'
                   '(line (pt %d %d)(pt %d %d)(line_width 1)))'
                   % (SYM_W, y, q, SYM_W - 40, y - 7, SYM_W - 12, y + 7,
                      q, SYM_W - 40, y - 7, SYM_W - 12, y + 7,
                      SYM_W - 16, y, SYM_W, y))
    out.append('(port (pt %d %d)(output)(text "COUT"(rect %d %d %d %d)(font "Arial"(font_size 8)))'
               '(text "COUT"(rect %d %d %d %d)(font "Arial"(font_size 8)))'
               '(line (pt %d %d)(pt %d %d)(line_width 1)))'
               % (SYM_W, SYM_COUT_Y, SYM_W - 40, SYM_COUT_Y - 7, SYM_W - 12, SYM_COUT_Y + 7,
                  SYM_W - 40, SYM_COUT_Y - 7, SYM_W - 12, SYM_COUT_Y + 7,
                  SYM_W - 16, SYM_COUT_Y, SYM_W, SYM_COUT_Y))
    out.append('(drawing (text "%s"(rect 90 150 170 166)(font "Arial"(font_size 8)))'
               '(line (pt 16 8)(pt %d 8)(line_width 1))'
               '(line (pt 16 8)(pt 16 %d)(line_width 1))'
               '(line (pt %d 8)(pt %d %d)(line_width 1))'
               '(line (pt 16 %d)(pt %d %d)(line_width 1))))'
               % (entity, SYM_W - 16, h - 8, SYM_W - 16, SYM_W - 16, h - 8,
                  h - 8, SYM_W - 16, h - 8))
    return "\n".join(out) + "\n"


def symbol_bsf(entity, q_names):
    """计数器实体的 .bsf（Quartus「生成元件符号」产物，可直接放在工程里）。"""
    return ('// This file was created by the Quartus batch placer\n'
            '(header "symbol" (version "0.1"))\n' + _hier_symbol(entity, q_names))


CLOCK_PITCH = 704       # 相邻计数器水平间距（8 的整数倍，保证全图在栅格上）
CLOCK_Y = 200           # 计数器顶边 y

# 计数器实体对外就是这 9 个端口（个位片 U0..U3、十位片 T0..T3、进位 COUT）
COUNTER_Q_PORTS = ["U0", "U1", "U2", "U3", "T0", "T1", "T2", "T3"]


def _clock_stages():
    """四个计数器：10ms(模100) → 秒(模60) → 分(模60) → 时(模24)。

    第三项是顶层输出引脚名（HH/HL/MH/ML/SH/SL/XH/XL，和试卷波形一致）。
    """
    return [
        ("I0", "mod100", ["XL0", "XL1", "XL2", "XL3", "XH0", "XH1", "XH2", "XH3"]),
        ("I1", "mod60", ["SL0", "SL1", "SL2", "SL3", "SH0", "SH1", "SH2", "SH3"]),
        ("I2", "mod60", ["ML0", "ML1", "ML2", "ML3", "MH0", "MH1", "MH2", "MH3"]),
        ("I3", "mod24", ["HL0", "HL1", "HL2", "HL3", "HH0", "HH1", "HH2", "HH3"]),
    ]


def top_clock():
    """顶层数字秒表原理图：把三个计数器元件串起来，进位逐级传递。"""
    import generator

    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "Digital Clock  (24h)   CLK=10ms -> XL/XH -> SL/SH -> ML/MH -> HL/HH, '
                 'carry COUT  chain, auto clear at 24h"(rect 192 32 1800 48)'
                 '(font "Courier New"(font_size 9)(bold)))')

    stages = _clock_stages()
    wires = []
    clk_in = _pin(parts, "INPUT", "CLK", 200, CLOCK_Y + SYM_CLK_Y)

    for k, (inst, entity, qs) in enumerate(stages):
        cx = 400 + CLOCK_PITCH * k
        block = generator._instance_name(_hier_symbol(entity, COUNTER_Q_PORTS), inst)
        block, _w, _h = generator.place(block, cx, CLOCK_Y)
        parts.append(block)

        if k == 0:
            wires.append((clk_in[0], clk_in[1], cx, CLOCK_Y + SYM_CLK_Y))
        for i, q in enumerate(qs):
            y = CLOCK_Y + Q_Y0 + 32 * i
            pin = _pin(parts, "OUTPUT", q, cx + 400, y)
            wires.append((cx + SYM_W, y, pin[0], pin[1]))

        cout = (cx + SYM_W, CLOCK_Y + SYM_COUT_Y)
        if k + 1 < len(stages):
            nx = 400 + CLOCK_PITCH * (k + 1)
            wires.append((cout[0], cout[1], cx + 640, cout[1]))
            wires.append((cx + 640, cout[1], cx + 640, CLOCK_Y + SYM_CLK_Y))
            wires.append((cx + 640, CLOCK_Y + SYM_CLK_Y, nx, CLOCK_Y + SYM_CLK_Y))
        else:
            pin = _pin(parts, "OUTPUT", "C24", cx + 400, CLOCK_Y + SYM_COUT_Y)
            wires.append((cout[0], cout[1], pin[0], pin[1]))

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


COUNT_BSF = dict((e, COUNTER_Q_PORTS) for e in ("mod100", "mod60", "mod24"))


def build_clock_project(out_dir, top_name="digital_clock"):
    """生成一套可直接编译的 Quartus 工程：顶层 + 三个计数器子元件 + 符号文件。"""
    import generator

    os.makedirs(out_dir, exist_ok=True)
    written = {}

    for entity in ("mod100", "mod60", "mod24"):
        path = os.path.join(out_dir, entity + ".bdf")
        generator.write_text(path, build_template(entity))
        written[entity + ".bdf"] = path
        bsf = os.path.join(out_dir, entity + ".bsf")
        generator.write_text(bsf, symbol_bsf(entity, COUNT_BSF[entity]))
        written[entity + ".bsf"] = bsf

    top_path = os.path.join(out_dir, top_name + ".bdf")
    generator.write_text(top_path, top_clock())
    written[top_name + ".bdf"] = top_path

    qpf = os.path.join(out_dir, top_name + ".qpf")
    generator.write_text(qpf, 'QUARTUS_VERSION = "9.1"\nDATE = "%s"\n\nPROJECT_REVISION = "%s"\n'
                         % (time.strftime("%H:%M:%S  %B %d, %Y"), top_name))
    written[top_name + ".qpf"] = qpf

    qsf_lines = ['set_global_assignment -name TOP_LEVEL_ENTITY %s' % top_name,
                 'set_global_assignment -name FAMILY "Stratix II"',
                 'set_global_assignment -name DEVICE AUTO']
    for name in (top_name, "mod100", "mod60", "mod24"):
        qsf_lines.append('set_global_assignment -name BDF_FILE %s.bdf' % name)
    qsf = os.path.join(out_dir, top_name + ".qsf")
    generator.write_text(qsf, "\n".join(qsf_lines) + "\n")
    written[top_name + ".qsf"] = qsf

    return top_path, written


# ---------------- 通用芯片模板引擎 ----------------
# 布局：芯片放中间，需要在左侧引出的输入引脚一律拉到 x = cx - PIN_SPAN，
# 输出引脚拉到 x = cx + w + PIN_SPAN；固定电平（GND/VCC）的引脚用一条竖直母线
# 汇到芯片左侧的电源符号上。所有坐标保持 8 的整数倍。
PIN_SPAN = 320          # 输入/输出引脚连接点相对芯片边缘的水平距离
GND_BUS_DX = 96         # GND 母线相对芯片左边缘的距离
VCC_BUS_DX = 152        # VCC 母线相对芯片左边缘的距离


def _dpin(parts, kind, name, cx, cy):
    """放一个输入/输出引脚符号，使连接点正好落在 (cx, cy)。"""
    geom = generator.geometry(kind)
    dx, dy = geom["conn"]
    body, _w, _h = generator.place(
        generator._instance_name(_raw(kind), name), cx - dx, cy - dy)
    parts.append(body)
    return (cx, cy)


def _gnd_at(parts, x, y, name):
    """GND 符号的连接点落在 (x, y)，符号本体挂在下方。"""
    body, _w, _h = generator.place(generator._instance_name(_raw("gnd"), name), x - 16, y)
    parts.append(body)


def _vcc_at(parts, x, y, name):
    """VCC 符号的连接点落在 (x, y)，符号本体立在上方。"""
    body, _w, _h = generator.place(generator._instance_name(_raw("vcc"), name), x - 16, y - 16)
    parts.append(body)


def _tie_group(parts, wires, kind, bus_x, pts, occupied, name):
    """把一组固定电平引脚并到同一条竖直母线上，母线末端放 GND/VCC 符号。

    occupied 是「同一 x 处已经有导线经过」的 y 集合，用来保证电源符号本体
    不会压在别的导线上（否则会被判定为短路/重叠）。
    """
    ys = sorted(set(p[1] for p in pts))
    if kind == "gnd":
        end = None
        for ext in range(40, 320, 8):
            y = ys[-1] + ext
            if any(y <= o <= y + 32 for o in occupied):     # 本体在 [y, y+32]
                continue
            end = y
            break
        top, bottom = ys[0], end if end is not None else ys[-1] + 40
    else:
        end = None
        for ext in range(40, 320, 8):
            y = ys[0] - ext
            if any(y - 16 <= o <= y for o in occupied):     # 本体在 [y-16, y]
                continue
            end = y
            break
        top, bottom = (end if end is not None else ys[0] - 40), ys[-1]

    for px, py in pts:
        wires.append((bus_x, py, px, py))
    wires.append((bus_x, top, bus_x, bottom))
    if kind == "gnd":
        _gnd_at(parts, bus_x, bottom, name)
    else:
        _vcc_at(parts, bus_x, top, name)


def _chip_schematic(title, chip, cx, cy, ins, outs, gnd=(), vcc=(), tag="U1"):
    """单芯片原理图：输入走左侧，输出走右侧，GND/VCC 引脚接到电源符号。"""
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "%s"(rect 192 32 1900 48)(font "Courier New"(font_size 9)(bold)))'
                 % title)
    geom = generator.geometry(chip)
    ports = _gate(parts, chip, tag, cx, cy)
    wires = []

    for p in ins:
        px, py = ports[p]
        conn = _dpin(parts, "INPUT", p, cx - PIN_SPAN, py)
        wires.append((conn[0], conn[1], px, py))
    for p, label in outs:
        px, py = ports[p]
        conn = _dpin(parts, "OUTPUT", label, cx + geom["w"] + PIN_SPAN, py)
        wires.append((px, py, conn[0], conn[1]))

    in_ys = set(ports[p][1] for p in ins)
    if gnd:
        _tie_group(parts, wires, "gnd", cx - GND_BUS_DX,
                   [ports[p] for p in gnd], in_ys | set(ports[p][1] for p in vcc),
                   tag + "_G")
    if vcc:
        _tie_group(parts, wires, "vcc", cx - VCC_BUS_DX,
                   [ports[p] for p in vcc], in_ys, tag + "_V")

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


def half_adder():
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "1-bit Half Adder   SUM = A XOR B   CARRY = A AND B"'
                 '(rect 192 48 1400 64)(font "Courier New"(font_size 9)(bold)))')
    a = _pin(parts, "INPUT", "A", 192, 160)
    b = _pin(parts, "INPUT", "B", 192, 240)
    s = _pin(parts, "OUTPUT", "SUM", 1536, 216)
    c = _pin(parts, "OUTPUT", "CARRY", 1536, 312)
    x1 = _gate(parts, "xor", "U1", 320, 192)
    a1 = _gate(parts, "and2", "U2", 320, 384)
    wires = [
        (a[0], a[1], 240, a[1]),
        (240, a[1], 240, a1["IN1"][1]),
        (240, x1["IN1"][1], x1["IN1"][0], x1["IN1"][1]),
        (240, a1["IN1"][1], x1["IN1"][0], a1["IN1"][1]),
        (b[0], b[1], 272, b[1]),
        (272, x1["IN2"][1], 272, a1["IN2"][1]),
        (272, x1["IN2"][1], x1["IN2"][0], x1["IN2"][1]),
        (272, a1["IN2"][1], x1["IN2"][0], a1["IN2"][1]),
        (x1["OUT"][0], x1["OUT"][1], s[0], s[1]),
        (a1["OUT"][0], a1["OUT"][1], 1408, a1["OUT"][1]),
        (1408, a1["OUT"][1], 1408, c[1]),
        (1408, c[1], c[0], c[1]),
    ]
    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


def chip_decoder_3to8():
    return _chip_schematic(
        "3-to-8 Decoder (74138)   C B A -> Y0N..Y7N (active low), G1=1 G2AN=G2BN=0",
        "74138", 600, 200,
        ins=["A", "B", "C"],
        outs=[("Y%dN" % i, "Y%dN" % i) for i in range(8)],
        gnd=["G2AN", "G2BN"], vcc=["G1"])


def chip_mux_8to1():
    return _chip_schematic(
        "8-to-1 Multiplexer (74151)   D0..D7 + C B A -> Y / WN, GN=0",
        "74151", 600, 200,
        ins=["C", "B", "A"] + ["D%d" % i for i in range(8)],
        outs=[("Y", "Y"), ("WN", "WN")],
        gnd=["GN"])


def chip_mux_4to1():
    return _chip_schematic(
        "Dual 4-to-1 Multiplexer (74153)   AB select, 1C0..1C3 -> 1Y, 2C0..2C3 -> 2Y",
        "74153", 600, 200,
        ins=["B", "A", "1C0", "1C1", "1C2", "1C3", "2C0", "2C1", "2C2", "2C3"],
        outs=[("1Y", "1Y"), ("2Y", "2Y")],
        gnd=["1GN", "2GN"])


def chip_seven_seg():
    # RBIN=1：不做灭零，RBON 因此恒为高（悬空即可，不引出顶层引脚）
    return _chip_schematic(
        "BCD-to-7-Segment Decoder (7447)   D C B A -> OA..OG (active low), LTN/RBIN/BIN=1",
        "7447", 600, 200,
        ins=["A", "B", "C", "D"],
        outs=[("O%s" % s, "O%s" % s) for s in "ABCDEFG"],
        vcc=["LTN", "RBIN", "BIN"])


def chip_comparator():
    return _chip_schematic(
        "4-bit Magnitude Comparator (7485)   A3..A0 ? B3..B0 -> A>B / A=B / A<B",
        "7485", 600, 200,
        ins=["A0", "B0", "A1", "B1", "A2", "B2", "A3", "B3"],
        outs=[("ALBO", "ALBO"), ("AEBO", "AEBO"), ("AGBO", "AGBO")],
        gnd=["ALBI", "AGBI"], vcc=["AEBI"])


def chip_adder_4bit():
    return _chip_schematic(
        "4-bit Adder (74283)   {C4,S4..S1} = A4..A1 + B4..B1 + C0",
        "7483", 600, 200,
        ins=["C0", "A1", "B1", "A2", "B2", "A3", "B3", "A4", "B4"],
        outs=[("S1", "S1"), ("S2", "S2"), ("S3", "S3"), ("S4", "S4"), ("C4", "C4")])


def chip_counter_74161():
    return _chip_schematic(
        "4-bit Binary Counter (74161)   CLK -> QA..QD, RCO carry; LDN/ENT/ENP/CLRN=1",
        "74161", 600, 200,
        ins=["CLK"],
        outs=[("QA", "QA"), ("QB", "QB"), ("QC", "QC"), ("QD", "QD"), ("RCO", "RCO")],
        gnd=["A", "B", "C", "D"], vcc=["LDN", "ENT", "ENP", "CLRN"])


def chip_counter_74160():
    return _chip_schematic(
        "Decade Counter (74160)   CLK -> QA..QD (BCD 0..9), RCO carry",
        "74160", 600, 200,
        ins=["CLK"],
        outs=[("QA", "QA"), ("QB", "QB"), ("QC", "QC"), ("QD", "QD"), ("RCO", "RCO")],
        gnd=["A", "B", "C", "D"], vcc=["LDN", "ENT", "ENP", "CLRN"])


def chip_register_74175():
    return _chip_schematic(
        "4-bit Register (74175)   1D..4D latched to 1Q..4Q on CLK rising edge, CLRN=1",
        "74175", 600, 200,
        ins=["1D", "2D", "3D", "4D", "CLK"],
        outs=[("%dQ" % i, "%dQ" % i) for i in range(1, 5)]
             + [("%dQN" % i, "%dQN" % i) for i in range(1, 5)],
        vcc=["CLRN"])


def chip_shift_74194():
    return _chip_schematic(
        "4-bit Shift Register (74194)   S1S0=01 shift right, SRSI -> QA..QD, CLRN=1",
        "74194", 600, 200,
        ins=["SRSI", "CLK"],
        outs=[("QA", "QA"), ("QB", "QB"), ("QC", "QC"), ("QD", "QD")],
        gnd=["SLSI", "A", "B", "C", "D", "S1"], vcc=["S0", "CLRN"])


# ---------------- D/JK 触发器（置位/清零在上下沿，需专门走线） ----------------
def dff_flipflop():
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "D Flip-Flop   Q = D on CLK rising edge   (PRN = CLRN = 1)"'
                 '(rect 192 32 1500 48)(font "Courier New"(font_size 9)(bold)))')
    ports = _gate(parts, "dff", "U1", 640, 320)
    wires = []

    conn = _dpin(parts, "INPUT", "D", 320, ports["D"][1])
    wires.append((conn[0], conn[1], ports["D"][0], ports["D"][1]))
    conn = _dpin(parts, "INPUT", "CLK", 320, 424)
    wires += [(320, 424, 400, 424), (400, 424, 400, ports["CLK"][1]),
              (400, ports["CLK"][1], ports["CLK"][0], ports["CLK"][1])]

    q = _dpin(parts, "OUTPUT", "Q", 1024, ports["Q"][1])
    wires.append((ports["Q"][0], ports["Q"][1], q[0], q[1]))

    # PRN 在上沿：直接往上接 VCC；CLRN 在下沿：向下绕一圈再上行接 VCC
    wires.append((ports["PRN"][0], ports["PRN"][1], ports["PRN"][0], 288))
    _vcc_at(parts, ports["PRN"][0], 288, "U1_PRN")
    wires += [(ports["CLRN"][0], ports["CLRN"][1], ports["CLRN"][0], 448),
              (ports["CLRN"][0], 448, 496, 448),
              (496, 448, 496, 424)]
    _vcc_at(parts, 496, 424, "U1_CLRN")

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


def jk_flipflop():
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "JK Flip-Flop   Q updates on CLK rising edge   (PRN = CLRN = 1)"'
                 '(rect 192 32 1500 48)(font "Courier New"(font_size 9)(bold)))')
    ports = _gate(parts, "jkff", "U1", 640, 320)
    wires = []

    conn = _dpin(parts, "INPUT", "J", 320, ports["J"][1])
    wires.append((conn[0], conn[1], ports["J"][0], ports["J"][1]))
    conn = _dpin(parts, "INPUT", "K", 320, 440)
    wires += [(320, 440, 400, 440), (400, 440, 400, ports["K"][1]),
              (400, ports["K"][1], ports["K"][0], ports["K"][1])]
    conn = _dpin(parts, "INPUT", "CLK", 320, 488)
    wires += [(320, 488, 432, 488), (432, 488, 432, ports["CLK"][1]),
              (432, ports["CLK"][1], ports["CLK"][0], ports["CLK"][1])]

    q = _dpin(parts, "OUTPUT", "Q", 1024, ports["Q"][1])
    wires.append((ports["Q"][0], ports["Q"][1], q[0], q[1]))

    wires.append((ports["PRN"][0], ports["PRN"][1], ports["PRN"][0], 288))
    _vcc_at(parts, ports["PRN"][0], 288, "U1_PRN")
    wires += [(ports["CLRN"][0], ports["CLRN"][1], ports["CLRN"][0], 560),
              (ports["CLRN"][0], 560, 496, 560),
              (496, 560, 496, 536)]
    _vcc_at(parts, 496, 536, "U1_CLRN")

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


def div2():
    """D 触发器 + 非门：Q 取反送回 D，输出为输入时钟的二分频。"""
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "Divide-by-2   Q toggles on every CLK rising edge (QN fed back to D)"'
                 '(rect 192 32 1700 48)(font "Courier New"(font_size 9)(bold)))')
    ports = _gate(parts, "dff", "U1", 800, 320)
    nt = _gate(parts, "not", "U2", 400, 328)
    wires = []

    conn = _dpin(parts, "INPUT", "CLK", 440, 424)
    wires += [(440, 424, 560, 424), (560, 424, 560, ports["CLK"][1]),
              (560, ports["CLK"][1], ports["CLK"][0], ports["CLK"][1])]

    q = _dpin(parts, "OUTPUT", "Q", 1376, ports["Q"][1])
    wires.append((ports["Q"][0], ports["Q"][1], q[0], q[1]))
    # 反馈：Q -> 绕到左上 -> 非门 -> D
    wires += [(1056, ports["Q"][1], 1056, 200),
              (1056, 200, 352, 200),
              (352, 200, 352, nt["IN"][1]),
              (352, nt["IN"][1], nt["IN"][0], nt["IN"][1]),
              (nt["OUT"][0], nt["OUT"][1], ports["D"][0], ports["D"][1])]

    # PRN 在上沿：直接往上接 VCC；CLRN 在下沿：往下绕开时钟线后再接 VCC
    wires.append((ports["PRN"][0], ports["PRN"][1], ports["PRN"][0], 288))
    _vcc_at(parts, ports["PRN"][0], 288, "U1_PRN")
    wires += [(ports["CLRN"][0], ports["CLRN"][1], ports["CLRN"][0], 464),
              (ports["CLRN"][0], 464, 608, 464)]
    _vcc_at(parts, 608, 464, "U1_CLRN")

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


def ring_counter():
    """74194 右移模式 + QD 取反回送 SRSI：扭环（Johnson）计数器，能自启动。"""
    parts = ['(header "graphic" (version "1.3"))']
    parts.append('(text "Johnson Counter (74194)   right shift, /QD -> SRSI, self starting 8 states"'
                 '(rect 192 32 1900 48)(font "Courier New"(font_size 9)(bold)))')
    cx, cy = 640, 240
    ports = _gate(parts, "74194", "U1", cx, cy)
    nt = _gate(parts, "not", "U2", 400, 320)
    wires = []

    conn = _dpin(parts, "INPUT", "CLK", 320, ports["CLK"][1])
    wires.append((conn[0], conn[1], ports["CLK"][0], ports["CLK"][1]))

    for q in ("QA", "QB", "QC", "QD"):
        pin = _dpin(parts, "OUTPUT", q, cx + 120 + PIN_SPAN, ports[q][1])
        wires.append((ports[q][0], ports[q][1], pin[0], pin[1]))

    # QD -> 下方 -> 左侧绕回 -> 非门 -> 上行回 SRSI（扭环反馈，自启动）
    wires += [(896, ports["QD"][1], 896, 480),
              (896, 480, 352, 480),
              (352, 480, 352, nt["IN"][1]),
              (352, nt["IN"][1], nt["IN"][0], nt["IN"][1]),
              (nt["OUT"][0], nt["OUT"][1], 464, nt["OUT"][1]),
              (464, nt["OUT"][1], 464, ports["SRSI"][1]),
              (464, ports["SRSI"][1], ports["SRSI"][0], ports["SRSI"][1])]

    in_ys = set([ports["CLK"][1]])
    _tie_group(parts, wires, "gnd", cx - GND_BUS_DX,
               [ports[p] for p in ("SLSI", "A", "B", "C", "D", "S1")],
               in_ys | set([ports["S0"][1]]), "U1_G")
    _tie_group(parts, wires, "vcc", cx - VCC_BUS_DX,
               [ports[p] for p in ("S0", "CLRN")], in_ys, "U1_V")

    emit_wires(parts, wires)
    return "\n".join(parts) + "\n"


BUILDERS = {
    "full_adder": full_adder,
    "half_adder": half_adder,
    "adder_4bit": lambda: ripple_adder(4),
    "adder_4bit_chip": chip_adder_4bit,
    "decoder_3to8": chip_decoder_3to8,
    "mux_8to1": chip_mux_8to1,
    "mux_4to1": chip_mux_4to1,
    "seven_seg_7447": chip_seven_seg,
    "comparator_4bit": chip_comparator,
    "mod60": counter_mod60,
    "mod24": counter_mod24,
    "mod100": counter_mod100,
    "counter_74161": chip_counter_74161,
    "counter_74160": chip_counter_74160,
    "register_74175": chip_register_74175,
    "shift_74194": chip_shift_74194,
    "dff_flipflop": dff_flipflop,
    "jk_flipflop": jk_flipflop,
    "div2": div2,
    "ring_counter": ring_counter,
    "digital_clock": top_clock,
}


def get_template(template_id):
    for tpl in TEMPLATES:
        if tpl["id"] == template_id:
            return tpl
    return None


def build_template(template_id):
    builder = BUILDERS.get(template_id)
    if not builder:
        raise ValueError("未知模板: %s" % template_id)
    return builder()
