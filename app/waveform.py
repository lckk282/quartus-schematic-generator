# -*- coding: utf-8 -*-
"""按模板生成时序波形图（SVG + CSV）。

思路：每个模板配一个「行为模型」，给出逐拍（slot）的引脚电平；渲染器把
这些电平画成标准数字波形图，可以直接下载成 SVG 贴进实验报告，或导入 Excel。

对外接口：
    spec(template_id)        -> 波形数据（或 None）
    render_svg(spec)         -> 自包含 SVG 文本
    render_csv(spec)         -> CSV 文本
    export(template_id, out_dir, stem) -> 写出的文件路径列表
"""
import os

# ---------------------------------------------------------------- 行为模型
LEFT = 168          # 左侧信号名列宽
SLOT_MIN = 14        # 每拍最小像素宽
ROW_H = 44
TOP = 78            # 标题 + 刻度占用的高度


def _bits(value, width, msb_first=False):
    """把整数拆成 width 位（默认 LSB 在前）。"""
    seq = [(value >> i) & 1 for i in range(width)]
    return seq[::-1] if msb_first else seq


def _adder(a, b, cin, width):
    total = a + b + cin
    return _bits(total & ((1 << width) - 1), width), (total >> width) & 1


def _sig(name, values, role="out", clock=False):
    return {"name": name, "values": list(values), "role": role, "clock": clock}


def _clock(n):
    return [1] * n


SEG = {  # 7447 共阳段码：a..g，0 表示该段点亮（低有效）
    0: [0, 0, 0, 0, 0, 0, 1],
    1: [1, 0, 0, 1, 1, 1, 1],
    2: [0, 0, 1, 0, 0, 1, 0],
    3: [0, 0, 0, 0, 1, 1, 0],
    4: [1, 0, 0, 1, 1, 0, 0],
    5: [0, 1, 0, 0, 1, 0, 0],
    6: [0, 1, 0, 0, 0, 0, 0],
    7: [0, 0, 0, 1, 1, 1, 1],
    8: [0, 0, 0, 0, 0, 0, 0],
    9: [0, 0, 0, 0, 1, 0, 0],
}


def m_full_adder():
    n = 8
    sig = []
    a = [i >> 2 & 1 for i in range(n)]
    b = [i >> 1 & 1 for i in range(n)]
    c = [i & 1 for i in range(n)]
    sig += [_sig("A", a, "in"), _sig("B", b, "in"), _sig("Cin", c, "in")]
    sig.append(_sig("SUM", [x ^ y ^ z for x, y, z in zip(a, b, c)]))
    sig.append(_sig("COUT", [1 if (x + y + z) >= 2 else 0 for x, y, z in zip(a, b, c)]))
    return {"title": "一位全加器 波形", "slots": n, "signals": sig,
            "note": "8 组输入组合全覆盖：SUM=A⊕B⊕Cin，COUT=AB+Cin(A⊕B)"}


def m_half_adder():
    n = 4
    a = [i >> 1 for i in range(n)]
    b = [i & 1 for i in range(n)]
    return {"title": "半加器 波形", "slots": n,
            "signals": [_sig("A", a, "in"), _sig("B", b, "in"),
                        _sig("SUM", [x ^ y for x, y in zip(a, b)]),
                        _sig("CARRY", [x & y for x, y in zip(a, b)])],
            "note": "4 组输入组合全覆盖"}


def _adder4(is_chip):
    cases = [(3, 5, 0), (9, 6, 0), (15, 15, 1), (0, 12, 1)]
    n = len(cases)
    sig = []
    labels = []
    a_bits = [[c[0] >> i & 1 for c in cases] for i in range(4)]
    b_bits = [[c[1] >> i & 1 for c in cases] for i in range(4)]
    cin = [c[2] for c in cases]
    sums = []
    couts = []
    for a, b, c in cases:
        s, co = _adder(a, b, c, 4)
        sums.append(s)
        couts.append(co)
        labels.append("%d+%d+%d=%d" % (a, b, c, a + b + c))
    if is_chip:
        for i in range(4):
            sig.append(_sig("A%d" % (i + 1), a_bits[i], "in"))
        for i in range(4):
            sig.append(_sig("B%d" % (i + 1), b_bits[i], "in"))
        sig.append(_sig("C0", cin, "in"))
        for i in range(4):
            sig.append(_sig("S%d" % (i + 1), [s[i] for s in sums]))
        sig.append(_sig("C4", couts))
    else:
        for i in range(4):
            sig.append(_sig("A%d" % i, a_bits[i], "in"))
        for i in range(4):
            sig.append(_sig("B%d" % i, b_bits[i], "in"))
        sig.append(_sig("Cin", cin, "in"))
        for i in range(4):
            sig.append(_sig("S%d" % i, [s[i] for s in sums]))
        sig.append(_sig("Cout", couts))
    return {"title": "四位加法器 波形", "slots": n, "signals": sig,
            "annotations": labels,
            "note": "行波进位：Cin 逐级传递，最高位溢出进 Cout/C4"}


def m_decoder():
    n = 8
    sig = [_sig("C", [i >> 2 for i in range(n)], "in"),
           _sig("B", [i >> 1 & 1 for i in range(n)], "in"),
           _sig("A", [i & 1 for i in range(n)], "in")]
    for k in range(8):
        sig.append(_sig("Y%dN" % k, [0 if i == k else 1 for i in range(n)]))
    return {"title": "3-8 译码器（74138）波形", "slots": n, "signals": sig,
            "annotations": ["%d" % i for i in range(n)],
            "note": "G1=1、G2AN=G2BN=0 使能；输出低有效，选中的那一路为 0"}


def m_mux8():
    d = [1, 0, 0, 1, 1, 0, 1, 0]
    n = 8
    sig = [_sig("C", [i >> 2 for i in range(n)], "in"),
           _sig("B", [i >> 1 & 1 for i in range(n)], "in"),
           _sig("A", [i & 1 for i in range(n)], "in")]
    for k in range(8):
        sig.append(_sig("D%d" % k, [d[k]] * n, "in"))
    sig.append(_sig("Y", [d[i] for i in range(n)]))
    sig.append(_sig("WN", [1 - d[i] for i in range(n)]))
    return {"title": "8 选 1 数据选择器（74151）波形", "slots": n, "signals": sig,
            "annotations": ["D%d" % i for i in range(n)],
            "note": "C B A 依次选中 D0..D7，WN 是 Y 的反相输出"}


def m_mux4():
    c1 = [1, 0, 1, 1]
    c2 = [0, 1, 1, 0]
    n = 4
    sig = [_sig("B", [i >> 1 for i in range(n)], "in"),
           _sig("A", [i & 1 for i in range(n)], "in")]
    for k in range(4):
        sig.append(_sig("1C%d" % k, [c1[k]] * n, "in"))
    for k in range(4):
        sig.append(_sig("2C%d" % k, [c2[k]] * n, "in"))
    sig.append(_sig("1Y", c1))
    sig.append(_sig("2Y", c2))
    return {"title": "双 4 选 1 选择器（74153）波形", "slots": n, "signals": sig,
            "annotations": ["00", "01", "10", "11"],
            "note": "1GN=2GN=0 使能；两组数据共用 AB 选择码，各自独立输出"}


def m_7447():
    n = 10
    sig = [_sig("A", [i & 1 for i in range(n)], "in"),
           _sig("B", [i >> 1 & 1 for i in range(n)], "in"),
           _sig("C", [i >> 2 & 1 for i in range(n)], "in"),
           _sig("D", [i >> 3 & 1 for i in range(n)], "in")]
    for s in range(7):
        sig.append(_sig("O" + "ABCDEFG"[s], [SEG[i][s] for i in range(n)]))
    return {"title": "七段译码器（7447）波形", "slots": n, "signals": sig,
            "annotations": ["%d" % i for i in range(n)],
            "note": "共阳数码管：OA..OG 低电平点亮对应段；LTN/RBIN/BIN=1"}


def m_comparator():
    cases = [(3, 5), (5, 5), (9, 4), (0, 15)]
    n = len(cases)
    sig = []
    for i in range(4):
        sig.append(_sig("A%d" % i, [c[0] >> i & 1 for c in cases], "in"))
    for i in range(4):
        sig.append(_sig("B%d" % i, [c[1] >> i & 1 for c in cases], "in"))
    sig.append(_sig("ALBO", [0 if c[0] < c[1] else 1 for c in cases]))
    sig.append(_sig("AEBO", [0 if c[0] == c[1] else 1 for c in cases]))
    sig.append(_sig("AGBO", [0 if c[0] > c[1] else 1 for c in cases]))
    return {"title": "四位数值比较器（7485）波形", "slots": n, "signals": sig,
            "annotations": ["%d ? %d" % c for c in cases],
            "note": "级联输入取默认值（AEBI=1，ALBI=AGBI=0）；三个输出低有效"}


def _counter_model(title, slots, modulus, bits_u, bits_t, note, cout_at):
    sig = [_sig("CLK", [0] * slots, "in", clock=True)]
    units = []
    tens = []
    cout = []
    labels = []
    for i in range(slots):
        v = i % modulus
        units.append(v % 10)
        tens.append(v // 10)
        cout.append(1 if v == cout_at else 0)
        labels.append("%02d" % v)
    for b in range(bits_u):
        sig.append(_sig("U%d" % b, [u >> b & 1 for u in units]))
    for b in range(bits_t):
        sig.append(_sig("T%d" % b, [t >> b & 1 for t in tens]))
    sig.append(_sig("COUT", cout))
    return {"title": title, "slots": slots, "signals": sig, "annotations": labels,
            "note": note}


def m_mod60():
    return _counter_model("模 60 计数器（7490×2）波形", 62, 60, 4, 4,
                          "个位 0-9、十位 0-5；计到 59 时 COUT 输出 1，下一拍归零", 59)


def m_mod24():
    return _counter_model("模 24 计数器（7490×2）波形", 26, 24, 4, 4,
                          "计到 23 时 COUT 输出 1，下一拍归零；十位只用 T0/T1", 23)


def m_mod100():
    return _counter_model("模 100 计数器（7490×2）波形", 102, 100, 4, 4,
                          "两片十进制级联，00-99 自然回环，COUT 在 99 时为 1", 99)


def m_74161():
    sig = [_sig("CLK", [0] * 18, "in", clock=True)]
    vals = [i % 16 for i in range(18)]
    for b in range(4):
        sig.append(_sig("Q" + "ABCD"[b], [v >> b & 1 for v in vals]))
    sig.append(_sig("RCO", [1 if v == 15 else 0 for v in vals]))
    return {"title": "四位二进制计数器（74161）波形", "slots": 18, "signals": sig,
            "annotations": ["%X" % v for v in vals],
            "note": "LDN/ENT/ENP/CLRN 均接高，处于常计数模式；RCO 在 15 时为进位"}


def m_74160():
    sig = [_sig("CLK", [0] * 12, "in", clock=True)]
    vals = [i % 10 for i in range(12)]
    for b in range(4):
        sig.append(_sig("Q" + "ABCD"[b], [v >> b & 1 for v in vals]))
    sig.append(_sig("RCO", [1 if v == 9 else 0 for v in vals]))
    return {"title": "十进制计数器（74160）波形", "slots": 12, "signals": sig,
            "annotations": ["%d" % v for v in vals],
            "note": "BCD 计数 0..9，RCO 在 9 时为进位"}


def m_74175():
    din = [1, 3, 2, 6, 4, 12, 8, 0]
    n = len(din)
    q = [0] + din[:-1]                      # 上升沿锁存：本拍输出 = 上一拍的 D
    sig = [_sig("CLK", [0] * n, "in", clock=True)]
    for b in range(4):
        sig.append(_sig("%dD" % (b + 1), [d >> b & 1 for d in din], "in"))
    for b in range(4):
        sig.append(_sig("%dQ" % (b + 1), [v >> b & 1 for v in q]))
    return {"title": "四位寄存器（74175）波形", "slots": n, "signals": sig,
            "annotations": ["%X" % v for v in din],
            "note": "CLK 上升沿把 1D..4D 锁存到 1Q..4Q（CLRN=1，初值 0000）"}


def m_74194():
    src = [1, 1, 0, 1, 0, 0, 1, 1, 0]
    n = len(src)
    state = [0, 0, 0, 0]                    # QA QB QC QD
    hist = []
    for i in range(n):
        state = [src[i], state[0], state[1], state[2]]
        hist.append(list(state))
    sig = [_sig("CLK", [0] * n, "in", clock=True),
           _sig("SRSI", src, "in")]
    for idx, name in enumerate(("QA", "QB", "QC", "QD")):
        sig.append(_sig(name, [h[idx] for h in hist]))
    return {"title": "四位双向移位寄存器（74194）波形", "slots": n, "signals": sig,
            "annotations": ["%X" % (h[0] << 3 | h[1] << 2 | h[2] << 1 | h[3]) for h in hist],
            "note": "S1S0=01 右移模式：SRSI→QA，QA→QB→QC→QD；CLRN=1"}


def m_dff():
    d = [1, 0, 1, 0, 0, 1, 1, 0]
    n = len(d)
    q = [0] + d[:-1]
    return {"title": "D 触发器 波形", "slots": n,
            "signals": [_sig("CLK", [0] * n, "in", clock=True),
                        _sig("D", d, "in"), _sig("Q", q)],
            "annotations": ["%d" % v for v in d],
            "note": "CLK 上升沿采样：本拍 Q 等于上一拍的 D（PRN=CLRN=1）"}


def m_jk():
    jk = [(0, 0), (1, 0), (0, 0), (0, 1), (0, 0), (1, 1), (1, 1), (1, 1)]
    q = 0
    qs = []
    for j, k in jk:
        if j and k:
            q = 1 - q
        elif j:
            q = 1
        elif k:
            q = 0
        qs.append(q)
    n = len(jk)
    return {"title": "JK 触发器 波形", "slots": n,
            "signals": [_sig("CLK", [0] * n, "in", clock=True),
                        _sig("J", [p[0] for p in jk], "in"),
                        _sig("K", [p[1] for p in jk], "in"),
                        _sig("Q", qs)],
            "annotations": ["保持", "置1", "保持", "清0", "保持", "翻转", "翻转", "翻转"],
            "note": "J=K=1 时每个上升沿翻转（二分频）；PRN=CLRN=1"}


def m_div2():
    n = 16
    q = [0 if i == 0 else (1 if i % 2 else 0) for i in range(n)]
    return {"title": "二分频器 波形", "slots": n,
            "signals": [_sig("CLK", [0] * n, "in", clock=True), _sig("Q", q)],
            "note": "Q 每个时钟上升沿翻转一次，输出频率为输入的 1/2；"
                    "/Q 经非门回送 D 端"}


def m_ring():
    state = [0, 0, 0, 0]
    hist = []
    for _ in range(10):
        fb = 1 - state[3]
        state = [fb, state[0], state[1], state[2]]
        hist.append(list(state))
    n = len(hist)
    sig = [_sig("CLK", [0] * n, "in", clock=True)]
    for idx, name in enumerate(("QA", "QB", "QC", "QD")):
        sig.append(_sig(name, [h[idx] for h in hist]))
    return {"title": "扭环计数器（74194）波形", "slots": n, "signals": sig,
            "annotations": ["%X" % (h[0] << 3 | h[1] << 2 | h[2] << 1 | h[3]) for h in hist],
            "note": "右移 + /QD 回送 SRSI：8 个状态循环，且能自启动"}


def m_clock():
    n = 12
    vals = [i % 100 for i in range(n)]
    sig = [_sig("CLK", [0] * n, "in", clock=True)]
    for b in range(4):
        sig.append(_sig("XL%d" % b, [(v % 10) >> b & 1 for v in vals]))
    for b in range(4):
        sig.append(_sig("XH%d" % b, [(v // 10) >> b & 1 for v in vals]))
    return {"title": "数字秒表（顶层）前 12 个 10ms 节拍", "slots": n, "signals": sig,
            "annotations": ["%02d" % v for v in vals],
            "note": "顶层把四个计数器级联：10ms(模100)→秒(模60)→分(模60)→时(模24)，"
                    "此处只画第一级 XL/XH 的低位输出"}


MODELLERS = {
    "full_adder": m_full_adder,
    "half_adder": m_half_adder,
    "adder_4bit": lambda: _adder4(False),
    "adder_4bit_chip": lambda: _adder4(True),
    "decoder_3to8": m_decoder,
    "mux_8to1": m_mux8,
    "mux_4to1": m_mux4,
    "seven_seg_7447": m_7447,
    "comparator_4bit": m_comparator,
    "mod60": m_mod60,
    "mod24": m_mod24,
    "mod100": m_mod100,
    "counter_74161": m_74161,
    "counter_74160": m_74160,
    "register_74175": m_74175,
    "shift_74194": m_74194,
    "dff_flipflop": m_dff,
    "jk_flipflop": m_jk,
    "div2": m_div2,
    "ring_counter": m_ring,
    "digital_clock": m_clock,
}


def spec(template_id):
    fn = MODELLERS.get(template_id)
    if not fn:
        return None
    spec = fn()
    spec["template"] = template_id
    for s in spec["signals"]:
        assert len(s["values"]) == spec["slots"], s["name"]
    return spec


# ---------------------------------------------------------------- SVG 渲染
def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_svg(sp):
    n = sp["slots"]
    sigs = sp["signals"]
    slot_w = max(SLOT_MIN, min(120, int(1120 / max(n, 1))))
    plot_w = slot_w * n
    width = LEFT + plot_w + 48
    height = TOP + len(sigs) * ROW_H + 74
    hi = 10           # 高电平相对行顶的偏移
    lo = ROW_H - 12   # 低电平相对行顶的偏移

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
           'width="%d" height="%d" font-family="Consolas,Menlo,monospace">'
           % (width, height, width, height),
           '<rect width="%d" height="%d" fill="#ffffff"/>' % (width, height),
           '<text x="20" y="30" font-size="17" font-weight="bold" fill="#1f2933">%s</text>'
           % _esc(sp["title"])]

    # 节拍刻度
    x0 = LEFT
    out.append('<g stroke="#e3e8ee" stroke-width="1">')
    for i in range(n + 1):
        x = x0 + i * slot_w
        out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>'
                   % (x, TOP - 12, x, TOP + len(sigs) * ROW_H))
    out.append('</g>')

    # 每条信号
    for r, s in enumerate(sigs):
      top = TOP + r * ROW_H
      vals = s["values"]
      colour = "#c026d3" if s.get("clock") else ("#2563eb" if s["role"] == "in" else "#0f766e")
      out.append('<rect x="0" y="%d" width="%d" height="%d" fill="%s"/>'
                 % (top, width, ROW_H, "#f7fafc" if r % 2 == 0 else "#ffffff"))
      out.append('<text x="%d" y="%d" font-size="13" text-anchor="end" fill="#334155">%s</text>'
                 % (LEFT - 12, top + ROW_H // 2 + 5, _esc(s["name"])))

      pts = []
      if s.get("clock"):
          for i in range(n):
              xa = x0 + i * slot_w
              pts += [(xa, top + lo), (xa, top + hi), (xa + slot_w * 0.62, top + hi),
                      (xa + slot_w * 0.62, top + lo)]
          pts.append((x0 + n * slot_w, top + lo))
      else:
          prev = vals[0]
          pts.append((x0, top + (hi if prev else lo)))
          for i, v in enumerate(vals):
              xa = x0 + i * slot_w
              y = top + (hi if v else lo)
              pts.append((xa, y))
              pts.append((xa + slot_w, y))
      d = " ".join("%.1f,%.1f" % p for p in pts)
      out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.2" '
                 'stroke-linejoin="miter"/>' % (d, colour))

    # 每拍标注（拍数不多时才有意义）
    ann = sp.get("annotations")
    if ann and len(ann) == n and slot_w >= 16:
        out.append('<g font-size="11" fill="#64748b" text-anchor="middle">')
        for i, a in enumerate(ann):
            out.append('<text x="%.1f" y="%d">%s</text>'
                       % (x0 + (i + 0.5) * slot_w, TOP - 18, _esc(a)))
        out.append('</g>')

    note = sp.get("note") or ""
    base_y = TOP + len(sigs) * ROW_H + 26
    out.append('<text x="20" y="%d" font-size="12" fill="#64748b">%s</text>'
               % (base_y, _esc(note)))
    out.append('<text x="20" y="%d" font-size="11" fill="#94a3b8">'
               'Quartus 原理图生成器 · 共 %d 拍（每拍一个时钟周期或一组激励）</text>'
               % (base_y + 22, n))
    out.append("</svg>")
    return "\n".join(out)


def render_csv(sp):
    names = [s["name"] for s in sp["signals"]]
    lines = ["tick," + ",".join(names)]
    for i in range(sp["slots"]):
        row = [str(i)] + [str(s["values"][i]) for s in sp["signals"]]
        lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def export(template_id, out_dir, stem, formats=("svg", "csv")):
    sp = spec(template_id)
    if not sp:
        raise ValueError("模板 %s 暂无波形模型" % template_id)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for fmt in formats:
        path = os.path.join(out_dir, "%s_waveform.%s" % (stem, fmt))
        text = render_svg(sp) if fmt == "svg" else render_csv(sp)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        paths.append(path)
    return paths, sp
