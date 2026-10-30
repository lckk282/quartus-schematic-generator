# -*- coding: utf-8 -*-
"""本地服务：提供网页界面，按模板或元件清单生成 Quartus .bdf 原理图。

接口：
  GET  /api/config      默认输出目录
  GET  /api/templates   模板清单
  GET  /api/symbols     器件库
  GET  /api/health      环境自检
  POST /api/preview     只渲染预览（SVG，不写文件）
  POST /api/generate    生成 .bdf（可选附带 Quartus 工程文件）并打开
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

import bdf_render
import config
import generator
import quartus_open
import templates
import waveform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

CFG = config.load()
DEFAULT_DIR = CFG["output_dir"]
PORT = int(CFG["port"])

QUARTUS_BIN = config.quartus_exe()

# Quartus 实体名规则：不能以数字开头，不能含空格/中文
VALID_ENTITY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _entity_name(stem):
    """把用户输入的文件名洗成合法实体名。"""
    name = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    if not name or name[0].isdigit():
        name = "sch_" + name
    return name


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---------------- GET ----------------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if self.path == "/api/symbols":
            return self._json(200, generator.load_symbols())
        if self.path == "/api/config":
            return self._json(200, {
                "default_dir": DEFAULT_DIR,
                "port": PORT,
                "quartus_exe": QUARTUS_BIN,
            })
        if self.path == "/api/templates":
            return self._json(200, {"items": templates.TEMPLATES})
        if self.path == "/api/health":
            return self._json(200, self.health())
        self.send_error(404)

    def health(self):
        checks = []

        def add(name, ok, detail=""):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        add("Python", sys.version_info >= (3, 6), " ".join(sys.version.split()[:2]))
        add("Quartus II 可执行文件", os.path.isfile(QUARTUS_BIN), QUARTUS_BIN)

        try:
            data = generator.load_symbols()
            n = len(data["items"])
            add("器件库", n > 0 and os.path.isdir(data.get("lib_root", "")),
                "%d 个符号（%s）" % (n, data.get("lib_root", "")))
        except Exception as exc:                       # noqa: BLE001
            add("器件库", False, str(exc))

        try:
            os.makedirs(DEFAULT_DIR, exist_ok=True)
            probe = os.path.join(DEFAULT_DIR, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            add("输出目录可写", True, DEFAULT_DIR)
        except OSError as exc:
            add("输出目录可写", False, "%s (%s)" % (DEFAULT_DIR, exc))

        add("模板库", bool(templates.TEMPLATES),
            "%d 个模板" % len(templates.TEMPLATES))
        covered = sum(1 for t in templates.TEMPLATES if t["id"] in waveform.MODELLERS)
        add("波形导出", covered == len(templates.TEMPLATES),
            "%d/%d 个模板有波形模型" % (covered, len(templates.TEMPLATES)))
        running = quartus_open.quartus_running()
        add("Quartus 进程", True,
            "正在运行" if running else "未运行，生成时会自动启动")

        return {"ok": all(c["ok"] for c in checks), "checks": checks}

    # ---------------- POST ----------------
    def do_POST(self):
        try:
            self._post()
        except Exception as exc:                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                self._json(200, {"ok": False, "error": "服务内部错误: %s" % exc})
            except OSError:
                pass

    def _post(self):
        if self.path in ("/api/opendir", "/api/reveal"):
            return self._open_path()
        if self.path not in ("/api/generate", "/api/preview", "/api/waveform"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return self._json(400, {"ok": False, "error": "请求格式错误"})

        template_id = payload.get("template") or ""
        if self.path == "/api/waveform":
            return self._waveform(payload, template_id)

        items = payload.get("items") or []
        if template_id and not templates.get_template(template_id):
            return self._json(400, {"ok": False, "error": "未知模板: %s" % template_id})
        if not items and not template_id:
            return self._json(400, {"ok": False,
                                    "error": "请先选一个电路模板，或在元件库里挑几个元件"})

        try:
            text = self._build_text(template_id, items)
        except Exception as exc:                       # noqa: BLE001
            return self._json(200, {"ok": False, "error": str(exc)})

        count = len(re.findall(r"^\((?:symbol|pin) ", text, re.M))

        if self.path == "/api/preview":
            try:
                svg = bdf_render.render_svg(text)
            except Exception as exc:                   # noqa: BLE001
                return self._json(200, {"ok": False, "error": "预览渲染失败: %s" % exc})
            return self._json(200, {"ok": True, "svg": svg, "count": count,
                                    "template": template_id})

        return self._json(200, self._generate(payload, template_id, items, text, count))

    def _waveform(self, payload, template_id):
        """生成波形图：save=true 时同时把 SVG / CSV 落到输出目录。"""
        if not template_id:
            return self._json(200, {"ok": False,
                                    "error": "波形图只对内置模板有效，请先选一张模板卡片"})
        try:
            sp = waveform.spec(template_id)
        except Exception as exc:                       # noqa: BLE001
            return self._json(200, {"ok": False, "error": "波形模型出错: %s" % exc})
        if not sp:
            return self._json(200, {"ok": False,
                                    "error": "模板 %s 没有波形模型" % template_id})
        result = {"ok": True, "svg": waveform.render_svg(sp), "template": template_id,
                  "title": sp["title"], "note": sp.get("note", ""),
                  "slots": sp["slots"], "signals": len(sp["signals"])}
        if payload.get("save"):
            out_dir = (payload.get("dir") or "").strip() or DEFAULT_DIR
            stem = (payload.get("stem") or "").strip() or (
                "%s_wave_%s" % (_entity_name(template_id), time.strftime("%Y%m%d_%H%M%S")))
            try:
                files, _sp = waveform.export(template_id, out_dir, stem)
            except Exception as exc:                   # noqa: BLE001
                return self._json(200, {"ok": False, "error": "导出失败: %s" % exc})
            result["files"] = files
            result["path"] = files[0]
            result["dir"] = out_dir
            result["stem"] = stem
        return self._json(200, result)

    def _build_text(self, template_id, items):
        if template_id:
            return templates.build_template(template_id)
        text, _placed = generator.build_bdf(items)
        return text

    def _open_path(self):
        """在资源管理器中定位文件 / 打开目录。"""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return self._json(400, {"ok": False, "error": "请求格式错误"})

        target = (payload.get("path") or payload.get("dir") or "").strip()
        if not target:
            return self._json(200, {"ok": False, "error": "路径为空"})
        target = os.path.abspath(target)
        try:
            if os.path.isfile(target):
                subprocess.Popen(["explorer", "/select,", target])
            elif os.path.isdir(target):
                os.makedirs(target, exist_ok=True)
                subprocess.Popen(["explorer", target])
            else:
                return self._json(200, {"ok": False, "error": "路径不存在: %s" % target})
        except OSError as exc:
            return self._json(200, {"ok": False, "error": str(exc)})
        return self._json(200, {"ok": True})

    def _generate(self, payload, template_id, items, text, count):
        out_path = (payload.get("path") or "").strip()
        if not out_path:
            os.makedirs(DEFAULT_DIR, exist_ok=True)
            stem = _entity_name(template_id or "batch")
            out_path = os.path.join(
                DEFAULT_DIR, "%s_%s.bdf" % (stem, time.strftime("%Y%m%d_%H%M%S")))
        if not out_path.lower().endswith(".bdf"):
            out_path += ".bdf"

        out_dir = os.path.dirname(os.path.abspath(out_path))
        stem = os.path.splitext(os.path.basename(out_path))[0]
        entity = _entity_name(stem)
        files = {}

        try:
            if template_id == "digital_clock":
                # 顶层秒表需要连子元件（.bdf + .bsf）一起产出
                out_path, files = templates.build_clock_project(out_dir, entity)
            else:
                generator.write_text(out_path, text)
                files["bdf"] = out_path

            if payload.get("make_project", True):
                qpf, qsf = self._write_project(out_dir, entity,
                                              template_id, items)
                files["qpf"] = qpf
                files["qsf"] = qsf
        except Exception as exc:                       # noqa: BLE001
            return {"ok": False, "error": "生成失败: %s" % exc}

        opened = False
        note = ""
        if payload.get("open", False):
            try:
                ok, msg = quartus_open.open_in_quartus(out_path)
            except Exception as exc:                   # noqa: BLE001
                ok, msg = False, "自动打开出错: %s" % exc
            if ok:
                opened = True
            else:
                note = ("文件已生成，但没能自动切到 Quartus 窗口（%s）。"
                        "可在下方点「在资源管理器中显示」手动打开。" % msg)
        return {
            "ok": True, "path": out_path, "count": count,
            "template": template_id, "opened": opened, "note": note,
            "entity": entity, "dir": out_dir,
            "files": [files[k] for k in ("bdf", "qpf", "qsf") if k in files],
        }

    def _write_project(self, out_dir, entity, template_id, items):
        os.makedirs(out_dir, exist_ok=True)
        qpf = os.path.join(out_dir, entity + ".qpf")
        generator.write_text(
            qpf,
            'QUARTUS_VERSION = "9.1"\nDATE = "%s"\n\nPROJECT_REVISION = "%s"\n'
            % (time.strftime("%H:%M:%S  %B %d, %Y"), entity))

        lines = ['set_global_assignment -name TOP_LEVEL_ENTITY %s' % entity,
                 'set_global_assignment -name FAMILY "Stratix II"',
                 'set_global_assignment -name DEVICE AUTO']
        if template_id == "digital_clock":
            for name in (entity, "mod100", "mod60", "mod24"):
                lines.append('set_global_assignment -name BDF_FILE %s.bdf' % name)
        else:
            lines.append('set_global_assignment -name BDF_FILE %s.bdf' % entity)
        qsf = os.path.join(out_dir, entity + ".qsf")
        generator.write_text(qsf, "\n".join(lines) + "\n")
        return qpf, qsf


def main():
    port = PORT
    for arg in sys.argv[1:]:
        if arg.isdigit():
            port = int(arg)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % port
    try:                      # pythonw 下 sys.stdout 是 None，print 会抛异常
        print("Quartus 原理图生成器已启动: %s" % url, flush=True)
    except Exception:
        pass
    if "--no-browser" not in sys.argv and CFG.get("auto_open", True):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
