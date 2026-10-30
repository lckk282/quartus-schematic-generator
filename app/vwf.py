# -*- coding: utf-8 -*-
"""生成 Quartus 波形文件（.vwf）：把真实仿真结果（VCD）写成 VWF 文本格式。

VWF 文本结构参考 Quartus 自带的示例文件：
  HEADER / SIGNAL / TRANSITION_LIST / DISPLAY_LINE / ";"
总线（如 XL[3..0]）用一个 SIGNAL_TYPE=BUS 的通道做父节点，四个位做子节点，
显示时父节点的 RADIX 用 Unsigned，就变成试卷参考图里那种“梯形”数值波形。
"""
import os
import re

BUS_LAYOUT = [
    ("CLK", "INPUT", None, "Binary"),
    ("XL[3..0]", "OUTPUT", ["XL3", "XL2", "XL1", "XL0"], "Unsigned"),
    ("XH[3..0]", "OUTPUT", ["XH3", "XH2", "XH1", "XH0"], "Unsigned"),
    ("SL[3..0]", "OUTPUT", ["SL3", "SL2", "SL1", "SL0"], "Unsigned"),
    ("SH[3..0]", "OUTPUT", ["SH3", "SH2", "SH1", "SH0"], "Unsigned"),
    ("ML[3..0]", "OUTPUT", ["ML3", "ML2", "ML1", "ML0"], "Unsigned"),
    ("MH[3..0]", "OUTPUT", ["MH3", "MH2", "MH1", "MH0"], "Unsigned"),
    ("HL[3..0]", "OUTPUT", ["HL3", "HL2", "HL1", "HL0"], "Unsigned"),
    ("HH[3..0]", "OUTPUT", ["HH3", "HH2", "HH1", "HH0"], "Unsigned"),
    ("C24", "OUTPUT", None, "Binary"),
]

COUNTER_LAYOUT = [
    ("CLK", "INPUT", None, "Binary"),
    ("U[3..0]", "OUTPUT", ["U3", "U2", "U1", "U0"], "Unsigned"),
    ("T[3..0]", "OUTPUT", ["T3", "T2", "T1", "T0"], "Unsigned"),
    ("COUT", "OUTPUT", None, "Binary"),
]


def parse_vcd(path):
    """返回 {信号名: [(时间ps, 电平), ...]}, 仿真结束时间(ps)。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    ids, ev, end = {}, {}, 0
    t = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("$var"):
            m = re.match(r"\$var reg 1 (\S+) (\w+) \$end", s)
            if m:
                ids[m.group(1)] = m.group(2)
                ev.setdefault(m.group(2), [])
            continue
        if s.startswith("#"):
            t = int(s[1:])
            end = max(end, t)
            continue
        if s[0] in "01" and s[1:] in ids:
            name = ids[s[1:]]
            seq = ev[name]
            lvl = int(s[0])
            if not seq:
                seq.append((0, lvl))
            elif seq[-1][1] != lvl:
                seq.append((t, lvl))
    return ev, end


def _levels(seq, dur_ns):
    """事件序列 → [(电平, 持续 ns)]，总和正好是 dur_ns。"""
    out = []
    prev_t = 0
    for i, (t, lvl) in enumerate(seq):
        nxt = seq[i + 1][0] if i + 1 < len(seq) else dur_ns * 1000
        d = (nxt - t) / 1000.0
        if d <= 0:
            continue
        if out and out[-1][0] == lvl:
            out[-1] = (lvl, out[-1][1] + d)
        else:
            out.append((lvl, d))
    if not out:
        out = [(0, dur_ns)]
    return out


def _sig_block(name, direction, width, kind, parent):
    return ("SIGNAL(\"%s\")\n{\n\tVALUE_TYPE = NINE_LEVEL_BIT;\n"
            "\tSIGNAL_TYPE = %s;\n\tWIDTH = %d;\n\tLSB_INDEX = -1;\n"
            "\tDIRECTION = %s;\n\tPARENT = \"%s\";\n}\n"
            % (name, kind, width, direction, parent))


def _tl_block(name, levels):
    body = ["TRANSITION_LIST(\"%s\")\n{\n\tNODE\n\t{\n\t\tREPEAT = 1;" % name]
    for lvl, d in levels:
        body.append("\t\tLEVEL %d FOR %.1f;" % (lvl, d))
    body.append("\t}\n}\n")
    return "\n".join(body)


def build(layout, events, dur_ns, time_unit="ns"):
    """生成 VWF 文本。layout 见 BUS_LAYOUT；events 来自 parse_vcd。"""
    out = ["/* Quartus II Vector Waveform File */\n"]
    out.append("HEADER\n{\n\tVERSION = 1;\n\tTIME_UNIT = %s;\n\tDATA_OFFSET = 0.0;\n"
               "\tDATA_DURATION = %.1f;\n\tSIMULATION_TIME = %.1f;\n\tGRID_PHASE = 0.0;\n"
               "\tGRID_PERIOD = 0.0;\n\tGRID_DUTY_CYCLE = 50;\n}\n"
               % (time_unit, dur_ns, dur_ns))

    # 1) SIGNAL 定义
    for disp, direction, bits, _radix in layout:
        if bits:
            out.append(_sig_block(disp, direction, len(bits), "BUS", ""))
            for b in bits:
                out.append(_sig_block(b, direction, 1, "SINGLE_BIT", disp))
        else:
            out.append(_sig_block(disp, direction, 1, "SINGLE_BIT", ""))

    # 2) TRANSITION_LIST：只给输入端写激励，输出端留空由 Quartus 仿真算出
    for disp, direction, bits, _r in layout:
        if direction != "INPUT":
            continue
        names = bits if bits else [disp]
        for n in names:
            seq = events.get(n)
            if seq:
                out.append(_tl_block(n, _levels(seq, dur_ns)))

    # 3) DISPLAY_LINE（总线父行 + 子行，TREE_INDEX 连续）
    idx = 0
    lines = []
    for disp, _d, bits, radix in layout:
        if bits:
            parent = idx
            slots = list(range(idx + 1, idx + 1 + len(bits)))
            idx += 1 + len(bits)
            lines.append("DISPLAY_LINE\n{\n\tCHANNEL = \"%s\";\n\tEXPAND_STATUS = COLLAPSED;\n"
                         "\tRADIX = %s;\n\tTREE_INDEX = %d;\n\tTREE_LEVEL = 0;\n"
                         "\tCHILDREN = %s;\n}\n"
                         % (disp, radix, parent, ", ".join(str(c) for c in slots)))
            # bits 已按 MSB→LSB 排列；Quartus 原厂 .vwf 的约定是 MSB 占最小行号
            for slot, b in zip(slots, bits):
                lines.append("DISPLAY_LINE\n{\n\tCHANNEL = \"%s\";\n\tEXPAND_STATUS = COLLAPSED;\n"
                             "\tRADIX = Binary;\n\tTREE_INDEX = %d;\n\tTREE_LEVEL = 1;\n"
                             "\tPARENT = %d;\n}\n" % (b, slot, parent))
        else:
            lines.append("DISPLAY_LINE\n{\n\tCHANNEL = \"%s\";\n\tEXPAND_STATUS = COLLAPSED;\n"
                         "\tRADIX = %s;\n\tTREE_INDEX = %d;\n\tTREE_LEVEL = 0;\n}\n"
                         % (disp, radix, idx))
            idx += 1
    out.extend(lines)
    out.append(";\n")
    return "\n".join(out)


def write_vwf(vcd_path, out_path, layout, dur_ns=None):
    events, end_ps = parse_vcd(vcd_path)
    dur = dur_ns if dur_ns else end_ps / 1000.0
    text = build(layout, events, dur)
    with open(out_path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)
    return out_path
