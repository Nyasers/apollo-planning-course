"""Local-only graphical harness panel and read/write API."""
from __future__ import annotations

import html
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .config import Settings
from .experiment import ExperimentStore

WEB_ROOT = Path(__file__).resolve().parent / "web"


def _load_tasks(settings: Settings) -> Dict[str, Any]:
    path = Path(settings.tasks_file).expanduser() if settings.tasks_file else None
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"tasks": [], "error": "invalid tasks file"}
    return {"tasks": []}


@dataclass
class Job:
    job_id: str
    action: str
    experiment_id: str
    status: str
    started_at: str
    finished_at: str = ""
    returncode: Optional[int] = None
    stdout_path: str = ""
    stderr_path: str = ""
    error: str = ""


class JobManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = Path(settings.output_dir).expanduser() / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()

    def _active(self) -> Optional[Job]:
        with self.lock:
            return next((job for job in self.jobs.values() if job.status == "running"), None)

    def start(self, action: str, experiment_id: str, argv: list[str]) -> Job:
        with self.lock:
            active = next((job for job in self.jobs.values() if job.status == "running"), None)
            if active:
                raise RuntimeError(f"another job is running: {active.job_id}")
            job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
            job = Job(job_id, action, experiment_id, "running", datetime.now().astimezone().isoformat(timespec="seconds"))
            job.stdout_path = str(self.root / f"{job_id}.stdout.txt")
            job.stderr_path = str(self.root / f"{job_id}.stderr.txt")
            self.jobs[job_id] = job
        env = os.environ.copy()
        env.update({
            "APOLLO_CLAW_OUTPUT_DIR": self.settings.output_dir,
            "APOLLO_CLAW_SKILLS_DIR": self.settings.skills_dir,
            "APOLLO_CONTAINER_NAME": self.settings.apollo_container_name,
            "APOLLO_CONTAINER_USER": self.settings.apollo_container_user,
            "APOLLO_WORKSPACE_HOST": self.settings.apollo_workspace_host,
            "APOLLO_WORKSPACE_CONTAINER": self.settings.apollo_workspace_container,
            "APOLLO_DREAMVIEW_URL": self.settings.dreamview_url,
        })
        stdout = open(job.stdout_path, "w", encoding="utf-8")
        stderr = open(job.stderr_path, "w", encoding="utf-8")

        def run() -> None:
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "apollo_claw", *argv],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    check=False,
                )
                job.returncode = proc.returncode
                job.status = "succeeded" if proc.returncode == 0 else "failed"
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
            finally:
                job.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
                stdout.close()
                stderr.close()

        threading.Thread(target=run, daemon=True).start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def list(self) -> list[Dict[str, Any]]:
        return [self._job_dict(job) for job in sorted(self.jobs.values(), key=lambda item: item.started_at, reverse=True)]

    def _job_dict(self, job: Job) -> Dict[str, Any]:
        def tail(path: str) -> str:
            try:
                return Path(path).read_text(encoding="utf-8", errors="ignore")[-8000:]
            except OSError:
                return ""
        return {
            "job_id": job.job_id,
            "action": job.action,
            "experiment_id": job.experiment_id,
            "status": job.status,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "returncode": job.returncode,
            "error": job.error,
            "stdout": tail(job.stdout_path),
            "stderr": tail(job.stderr_path),
        }


def _report(store: ExperimentStore, experiment_id: str):
    path = store.report_path(experiment_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def make_handler(settings: Settings, token: Optional[str] = None):
    token = token or secrets.token_urlsafe(24)
    store = ExperimentStore(Path(settings.output_dir))
    jobs = JobManager(settings)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data: Any):
            self._send(code, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8")

        def _authorized(self) -> bool:
            return self.headers.get("X-Apollo-Claw-Token") == token

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 64 * 1024:
                raise ValueError("request body too large")
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_POST(self):
            if not self._authorized():
                self._json(403, {"error": "missing or invalid token"})
                return
            path = urlparse(self.path).path
            if not path.startswith("/api/actions/"):
                self._json(404, {"error": "not found"})
                return
            action = path.rsplit("/", 1)[-1]
            if action not in {"doctor", "record", "report", "eval", "export", "explain"}:
                self._json(404, {"error": "unknown action"})
                return
            try:
                body = self._read_json()
                experiment_id = body.get("experiment_id") or ""
                if action in {"doctor", "record"} and not experiment_id:
                    experiment = store.create(body.get("task", "crosswalk"), body.get("scenario", "人行道避让"))
                    experiment_id = experiment["meta"]["experiment_id"]
                if action == "doctor":
                    argv = ["doctor", "--json", "--experiment", experiment_id]
                elif action == "record":
                    argv = ["test", "record", "--experiment", experiment_id, "--tag", body.get("tag", "crosswalk"), "--seconds", str(int(body.get("seconds", 25))), "--task", body.get("task", "crosswalk"), "--scenario", body.get("scenario", "人行道避让")]
                    if body.get("execute"):
                        argv.append("--execute")
                elif action == "report":
                    if not experiment_id or not body.get("record"):
                        raise ValueError("report requires experiment_id and record")
                    argv = ["test", "report", "--experiment", experiment_id, "--record", body["record"]]
                    if body.get("execute"):
                        argv.append("--execute")
                elif action == "eval":
                    if not experiment_id or not body.get("scenario_path") or not body.get("bag"):
                        raise ValueError("eval requires experiment_id, scenario_path and bag")
                    argv = ["eval", "--experiment", experiment_id, "--scenario", body["scenario_path"], "--bag", body["bag"], "--scenario-name", body.get("scenario", "人行道避让")]
                    if body.get("execute"):
                        argv.append("--execute")
                elif action == "explain":
                    if not experiment_id:
                        raise ValueError("explain requires experiment_id")
                    argv = ["explain", "--experiment", experiment_id]
                    if body.get("question"):
                        argv.extend(["--question", body["question"]])
                    if body.get("log"):
                        argv.extend(["--log", body["log"]])
                else:
                    if not experiment_id:
                        raise ValueError("export requires experiment_id")
                    argv = ["report", "export", "--experiment", experiment_id]
                job = jobs.start(action, experiment_id, argv)
                self._json(202, {"job": jobs._job_dict(job), "experiment_id": experiment_id})
            except RuntimeError as exc:
                self._json(409, {"error": str(exc)})
            except Exception as exc:
                self._json(400, {"error": str(exc)})

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health" or path == "/api/health":
                self._json(200, {
                    "ok": True,
                    "service": "apollo-claw-harness",
                    "version": "0.3.0",
                    "settings": {
                        "container": settings.apollo_container_name,
                        "workspace": settings.apollo_workspace_host,
                        "dreamview": settings.dreamview_url,
                        "deepseek_configured": bool(settings.deepseek_api_key),
                    },
                    "skills": str(Path(settings.skills_dir).expanduser()),
                })
                return
            if path == "/api/session":
                self._json(200, {"token": token, "tasks": _load_tasks(settings), "deepseek_configured": bool(settings.deepseek_api_key), "version": "0.3.0"})
                return
            if path == "/api/tasks":
                self._json(200, _load_tasks(settings))
                return
            if path == "/api/jobs":
                self._json(200, {"jobs": jobs.list()})
                return
            if path.startswith("/api/jobs/"):
                job = jobs.get(path.rsplit("/", 1)[-1])
                if job is None:
                    self._json(404, {"error": "job not found"})
                else:
                    self._json(200, jobs._job_dict(job))
                return
            if path == "/api/experiments":
                items = []
                for exp in store.list():
                    meta = exp.get("meta", {})
                    items.append({"experiment_id": meta.get("experiment_id"), "task": meta.get("task"), "scenario": meta.get("scenario"), "status": meta.get("status"), "created_at": meta.get("created_at"), "record": exp.get("record", {})})
                self._json(200, {"experiments": items})
                return
            if path == "/api/latest" or path == "/api/report/latest":
                latest = store.latest()
                if not latest:
                    self._json(404, {"error": "no experiment found"})
                else:
                    exp_id = latest["meta"]["experiment_id"]
                    self._json(200, _report(store, exp_id) or latest)
                return
            if path.startswith("/api/experiments/"):
                suffix = path[len("/api/experiments/"):]
                if suffix.endswith("/report"):
                    exp_id = suffix[:-7]
                    report = _report(store, exp_id)
                    if report is None:
                        self._json(404, {"error": "report not found"})
                    else:
                        self._json(200, report)
                    return
                try:
                    self._json(200, store.load(suffix))
                except Exception:
                    self._json(404, {"error": "experiment not found"})
                return
            if path in ("/", "/index.html"):
                index = WEB_ROOT / "index.html"
                body = index.read_text(encoding="utf-8").replace("__APOLLO_CLAW_TOKEN__", token)
                self._send(200, body.encode("utf-8"))
                return
            if path in ("/app.css", "/app.js"):
                asset = WEB_ROOT / path.lstrip("/")
                if asset.exists():
                    ctype = "text/css; charset=utf-8" if asset.suffix == ".css" else "application/javascript; charset=utf-8"
                    self._send(200, asset.read_bytes(), ctype)
                    return
            self._json(404, {"error": "not found"})

        def log_message(self, fmt, *args):
            return

    return Handler


def serve(settings: Settings, port: int = 8765) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings))
    print(f"Apollo Claw Harness running at http://127.0.0.1:{port}/")
    httpd.serve_forever()
