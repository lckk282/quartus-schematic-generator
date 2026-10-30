# -*- coding: utf-8 -*-
"""把 .bdf 画布渲染成 SVG，用于网页内直接预览原理图。

支持 .bdf 里的全部图元：
  (symbol ...) / (pin ...)        实例（子坐标相对实例 rect 左上角）
  (connector (pt a)(pt b))        导线
  (junction (pt x y))             连接点
  (text "..."(rect ...)(font ...)) 文本
"""
import re

# ---------- S 表达式解析 ----------

_TOKEN_RE = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


def parse(src):
    """把 .bdf 文本解析成嵌套节点树：[{tag, atoms, kids}]"""
    tokens = []
    for m in _TOKEN_RE.finditer(src):
        if m.group(1):
            tokens.append("(")
        elif m.group(2):
            tokens.append(")")
        elif m.group(3) is not None:
            tokens.append(("str", m.group(3)))
        elif m.group(4) is not None:
            tokens.append(("atom", m.group(4)))
    roots = []
    stack = []
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            if not stack:
                continue
            items = stack.pop()
            node = _to_node(items)
            if stack:
                stack[-1].append(node)
            else:
                roots.append(node)
        else:
            if stack:
                stack[-1].append(tok)
    return roots


def _to_node(items):
    tag = ""
    atoms = []
    kids = []
    for it in items:
        if isinstance(it, dict):
            kids.append(it)
        elif isinstance(it, tuple):
            if not tag and not atoms and not kids:
                tag = it[1] if it[0] == "atom" else '"%s"' % it[1]
            else:
                atoms.append(it[1])
        else:
            tag = it
    return {"tag": tag, "atoms": atoms, "kids": kids}


def _child(node, tag):
    for k in node["kids"]:
        if k["tag"] == tag:
            return k
    return None


def _rect(node):
    r = _child(node, "rect")
    if not r or len(r["atoms"]) < 4:
        return None
    try:
        return tuple(float(v) for v in r["atoms"][:4])
    except ValueError:
        return None


def _pt(node):
    """取块内第一个 (pt x y)。"""
    for k in node["kids"]:
        if k["tag"] == "pt" and len(k["atoms"]) >= 2:
            try:
                return (float(k["atoms"][0]), float(k["atoms"][1]))
            except ValueError:
                return None
    return None


# ---------- 图元收集 ----------

def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def collect(src):
    """解析 .bdf，返回 {lines, arcs, circles, texts, boxes, pins}（全部为绝对坐标）。"""
    lines = []       # (x1,y1,x2,y2, style)
    arcs = []        # (path d, style)
    circles = []     # (cx,cy,r, filled)
    texts = []       # (x1,y1,x2,y2, string, size)
    boxes = []       # (x1,y1,x2,y2)
    roots = parse(src)

    def walk_drawing(node, ox, oy, style):
        for k in node.get("kids", []):
            tag = k["tag"]
            if tag == "line":
                pts = [(p["atoms"][0], p["atoms"][1]) for p in k["kids"]
                       if p["tag"] == "pt" and len(p["atoms"]) >= 2]
                for a, b in zip(pts, pts[1:]):
                    lines.append((ox + float(a[0]), oy + float(a[1]),
                                  ox + float(b[0]), oy + float(b[1]), style))
            elif tag == "arc":
                pts = [(float(p["atoms"][0]), float(p["atoms"][1]))
                       for p in k["kids"] if p["tag"] == "pt" and len(p["atoms"]) >= 2]
                r = _rect(k)
                if len(pts) >= 2 and r:
                    p1 = (ox + pts[0][0], oy + pts[0][1])
                    p2 = (ox + pts[1][0], oy + pts[1][1])
                    box = (ox + r[0], oy + r[1], ox + r[2], oy + r[3])
                    arcs.append((_arc_path(p1, p2, box), style))
            elif tag == "circle":
                r = _rect(k)
                if r:
                    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
                    circles.append((ox + cx, oy + cy,
                                    max((r[2] - r[0]) / 2, 3), r[2] - r[0] < 10))
            elif tag == "text":
                tx = _rect(k)
                label = k["atoms"][0] if k["atoms"] else ""
                fz = _font_size(k)
                if tx and not _hidden(k):
                    texts.append((ox + tx[0], oy + tx[1], ox + tx[2], oy + tx[3],
                                  label, fz))
            elif tag == "drawing":
                walk_drawing(k, ox, oy, style)

    for root in roots:
        tag = root["tag"]
        if tag in ("symbol", "pin"):
            r = _rect(root)
            ox, oy = (r[0], r[1]) if r else (0, 0)
            style = "pin" if tag == "pin" else "sym"
            if r:
                boxes.append((r[0], r[1], r[2], r[3]))
            for k in root["kids"]:
                if k["tag"] == "drawing":
                    walk_drawing(k, ox, oy, style)
                elif k["tag"] == "text":
                    tx = _rect(k)
                    label = k["atoms"][0] if k["atoms"] else ""
                    if tx and label and not _hidden(k):
                        texts.append((ox + tx[0], oy + tx[1], ox + tx[2], oy + tx[3],
                                      label, _font_size(k)))
                elif k["tag"] == "port":
                    for kk in k["kids"]:
                        if kk["tag"] == "line":
                            walk_drawing({"kids": [kk]}, ox, oy, style)
        elif tag == "connector":
            pts = [(p["atoms"][0], p["atoms"][1]) for p in root["kids"]
                   if p["tag"] == "pt" and len(p["atoms"]) >= 2]
            for a, b in zip(pts, pts[1:]):
                lines.append((float(a[0]), float(a[1]), float(b[0]), float(b[1]), "wire"))
        elif tag == "junction":
            p = _pt(root)
            if p:
                circles.append((p[0], p[1], 4, True))
        elif tag == "text":
            tx = _rect(root)
            label = root["atoms"][0] if root["atoms"] else ""
            if tx and label:
                texts.append((tx[0], tx[1], tx[2], tx[3], label, _font_size(root)))

    return {"lines": lines, "arcs": arcs, "circles": circles,
            "texts": texts, "boxes": boxes}


def _font_size(node):
    for k in node["kids"]:
        if k["tag"] == "font":
            for kk in k["kids"]:
                if kk["tag"] == "font_size" and kk["atoms"]:
                    try:
                        return float(kk["atoms"][0])
                    except ValueError:
                        pass
    return 8.0


def _hidden(node):
    """Quartus 用 (invisible) 标记隐藏文字（例如端口内部名）。"""
    return any(k["tag"] in ("invisible", "hidden") for k in node.get("kids", []))


def _arc_path(p1, p2, rect):
    """把 Quartus 的 (arc (pt a)(pt b)(rect l t r b)) 还原成 SVG 路径。

    椭圆由 rect 决定，弧从 a 到 b；两个方向都有可能，选包围盒最贴合 rect 的那个。
    """
    import math
    l, t, r, b = rect
    cx, cy = (l + r) / 2.0, (t + b) / 2.0
    rx, ry = max((r - l) / 2.0, 0.1), max((b - t) / 2.0, 0.1)

    def angles(sweep):
        a1 = math.atan2((p1[1] - cy) / ry, (p1[0] - cx) / rx)
        a2 = math.atan2((p2[1] - cy) / ry, (p2[0] - cx) / rx)
        if sweep:
            while a2 <= a1:
                a2 += 2 * math.pi
        else:
            while a2 >= a1:
                a2 -= 2 * math.pi
        return a1, a2

    best = None
    for sweep in (0, 1):
        a1, a2 = angles(sweep)
        xs, ys = [], []
        steps = 24
        for i in range(steps + 1):
            ang = a1 + (a2 - a1) * i / steps
            xs.append(cx + rx * math.cos(ang))
            ys.append(cy + ry * math.sin(ang))
        err = (abs(min(xs) - l) + abs(max(xs) - r)
               + abs(min(ys) - t) + abs(max(ys) - b))
        if best is None or err < best[0]:
            best = (err, sweep, abs(a2 - a1) > math.pi)
    _, sweep, large = best
    return ('M %.1f %.1f A %.1f %.1f 0 %d %d %.1f %.1f'
            % (p1[0], p1[1], rx, ry, 1 if large else 0, sweep, p2[0], p2[1]))


# ---------- 渲染 ----------

PAD = 60


def render_svg(src, max_width=1600):
    data = collect(src)
    xs, ys = [], []
    for x1, y1, x2, y2, _ in data["lines"]:
        xs += [x1, x2]
        ys += [y1, y2]
    for cx, cy, r, _ in data["circles"]:
        xs += [cx - r, cx + r]
        ys += [cy - r, cy + r]
    for x1, y1, x2, y2, _s, _f in data["texts"]:
        xs += [x1, x2]
        ys += [y1, y2]
    for x1, y1, x2, y2 in data.get("boxes", []):
        xs += [x1, x2]
        ys += [y1, y2]
    if not xs:
        xs, ys = [0, 800], [0, 600]

    x0, x1 = min(xs) - PAD, max(xs) + PAD
    y0, y1 = min(ys) - PAD, max(ys) + PAD
    w, h = max(x1 - x0, 1), max(y1 - y0, 1)

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.1f %.1f %.1f %.1f" '
           'width="100%%" preserveAspectRatio="xMidYMid meet" '
           'style="background:#fff;max-width:%dpx">' % (x0, y0, w, h, max_width)]
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#fff"/>'
               % (x0, y0, w, h))

    # 导线
    out.append('<g stroke="#8a2be2" stroke-width="2" stroke-linecap="round" fill="none">')
    for a, b, c, d, style in data["lines"]:
        if style == "wire":
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (a, b, c, d))
    out.append("</g>")

    # 元件内部线条（含圆弧，Quartus 的门电路轮廓大多用 arc 画）
    out.append('<g stroke="#2b4a8b" stroke-width="1.6" stroke-linecap="round" fill="none">')
    for a, b, c, d, style in data["lines"]:
        if style != "wire":
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (a, b, c, d))
    for d, style in data.get("arcs", []):
        if style != "wire":
            out.append('<path d="%s"/>' % d)
    for cx, cy, r, filled in data["circles"]:
        if filled:
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#8a2be2" '
                       'stroke="none"/>' % (cx, cy, r))
        else:
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none"/>' % (cx, cy, r))
    out.append("</g>")

    # 文本
    out.append('<g font-family="Arial, Helvetica, sans-serif" fill="#16233f">')
    for x1_, y1_, x2_, y2_, label, fs in data["texts"]:
        if not label.strip():
            continue
        hgt = max(y2_ - y1_, 6)
        size = max(hgt * 0.92, fs * 1.1)
        if len(label) == 1:
            size = min(size, 15)
        out.append('<text x="%.1f" y="%.1f" font-size="%.1f" '
                   'dominant-baseline="middle">%s</text>'
                   % (x1_, (y1_ + y2_) / 2, size, _esc(label)))
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)
