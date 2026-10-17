"""Local-only experiment panel. Never binds to a public interface."""
from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import Settings
from .experiment import ExperimentStore


def _load_tasks(settings: Settings):
    path = Path(settings.tasks_file).expanduser() if settings.tasks_file else None
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"tasks": [], "error": "invalid tasks file"}
    return {"tasks": []}


def _reports(settings: Settings):
    store = ExperimentStore(Path(settings.output_dir))
    return store


def make_handler(settings: Settings):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, code: int, data):
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")

        def _send(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _report_data(self, experiment_id: str):
            store = _reports(settings)
            path = store.report_path(experiment_id)
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

        def do_POST(self):
            self._send_json(405, {"error": "read-only panel; use CLI commands for execution"})

        def do_GET(self):
            parsed = urlparse(self.path)
            route = parsed.path
            if route in ("/health", "/api/health"):
                skills = _load_tasks(settings)
                self._send_json(200, {
                    "ok": True,
                    "service": "apollo-claw-harness",
                    "settings": {
                        "container": settings.apollo_container_name,
                        "workspace": settings.apollo_workspace_host,
                        "dreamview": settings.dreamview_url,
                        "deepseek_configured": bool(settings.deepseek_api_key),
                        "tasks_file": settings.tasks_file,
                    },
                    "task_count": len(skills.get("tasks", [])),
                })
                return
            if route == "/api/tasks":
                self._send_json(200, _load_tasks(settings))
                return
            if route == "/api/experiments":
                items = []
                for experiment in _reports(settings).list():
                    meta = experiment.get("meta", {})
                    items.append({
                        "experiment_id": meta.get("experiment_id"),
                        "task": meta.get("task"),
                        "scenario": meta.get("scenario"),
                        "status": meta.get("status"),
                        "created_at": meta.get("created_at"),
                    })
                self._send_json(200, {"experiments": items})
                return
            if route in ("/api/latest", "/api/report/latest"):
                latest = _reports(settings).latest()
                if not latest:
                    self._send_json(404, {"error": "no experiment found"})
                    return
                exp_id = latest["meta"]["experiment_id"]
                report = self._report_data(exp_id)
                self._send_json(200, report or latest)
                return
            if route.startswith("/api/experiments/") or route.startswith("/api/report/"):
                exp_id = route.rsplit("/", 1)[-1]
                report = self._report_data(exp_id)
                if report is None:
                    try:
                        report = _reports(settings).load(exp_id)
                    except Exception:
                        report = None
                if report is None:
                    self._send_json(404, {"error": "experiment not found"})
                else:
                    self._send_json(200, report)
                return
            # Human-readable local dashboard.
            tasks = _load_tasks(settings).get("tasks", [])
            experiments = _reports(settings).list()
            task_html = "".join(
                f"<li><strong>{html.escape(str(t.get('title', t.get('id', ''))))}</strong> "
                f"<code>{html.escape(str(t.get('id', '')))}</code> "
                f"<span>{html.escape(str(t.get('status', 'open')))}</span></li>"
                for t in tasks
            ) or "<li>未配置 tasks.json</li>"
            exp_html = "".join(
                f"<li><a href=\"/api/report/{html.escape(str(e.get('meta', {}).get('experiment_id', '')))}\">"
                f"{html.escape(str(e.get('meta', {}).get('experiment_id', '')))}</a> "
                f"{html.escape(str(e.get('meta', {}).get('status', '')))}</li>"
                for e in experiments
            ) or "<li>还没有实验记录</li>"
            body = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Apollo Claw Harness</title>
<style>body{{font-family:system-ui,sans-serif;max-width:980px;margin:40px auto;line-height:1.6}}code{{background:#eee;padding:2px 5px}}li{{margin:8px 0}}</style>
<h1>Apollo Claw Harness</h1>
<p>本地实验面板，仅监听 <code>127.0.0.1</code>。执行实验请使用 CLI，不在网页执行命令。</p>
<h2>实验任务</h2><ul>{task_html}</ul>
<h2>实验记录</h2><ul>{exp_html}</ul>
<p>健康检查：<a href="/health">/health</a> · 任务：<a href="/api/tasks">/api/tasks</a> · 实验：<a href="/api/experiments">/api/experiments</a></p>
</body></html>"""
            self._send(200, body.encode("utf-8"))

        def log_message(self, fmt, *args):
            return

    return Handler


def serve(settings: Settings, port: int = 8765) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings))
    print(f"Apollo Claw Harness running at http://127.0.0.1:{port}/")
    httpd.serve_forever()
