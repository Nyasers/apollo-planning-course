"""Minimal local panel server. Listens on 127.0.0.1 only."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Settings


def _latest_report(settings: Settings):
    root = Path(settings.output_dir)
    if not root.exists():
        return None
    reports = sorted(root.rglob("report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def make_handler(settings: Settings):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str = "application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/health"):
                data = {
                    "ok": True,
                    "service": "apollo-claw-harness",
                    "settings": {
                        "container": settings.apollo_container_name,
                        "workspace": settings.apollo_workspace_host,
                        "deepseek_configured": bool(settings.deepseek_api_key),
                    },
                }
                self._send(200, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
                return
            if self.path.startswith("/api/latest"):
                report = _latest_report(settings)
                if not report:
                    self._send(404, b'{"error":"no report found"}')
                    return
                self._send(200, report.read_bytes())
                return
            html = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Apollo Claw Harness</title>
<body style="font-family:system-ui;max-width:760px;margin:40px auto;line-height:1.7">
<h1>Apollo Claw Harness</h1>
<p>本地实验面板正在运行。</p>
<ul>
<li><a href="/health">/health</a>：环境状态</li>
<li><a href="/api/latest">/api/latest</a>：最近一次实验报告 JSON</li>
</ul>
<p>真实 record、评分和 DeepSeek 解释都在本地执行。API Key 不进入网页。</p>
</body></html>"""
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

        def log_message(self, fmt, *args):
            return

    return Handler


def serve(settings: Settings, port: int = 8765) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings))
    print(f"Apollo Claw Harness running at http://127.0.0.1:{port}/")
    httpd.serve_forever()
