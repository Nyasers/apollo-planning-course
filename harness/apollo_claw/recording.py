"""Stateful cyber_recorder session control for the local Harness."""
from __future__ import annotations

import re
import shlex
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import Settings
from .experiment import ExperimentStore
from .runner import docker_exec


CHANNELS = [
    "/apollo/planning",
    "/apollo/control",
    "/apollo/localization/pose",
    "/apollo/canbus/chassis",
    "/apollo/perception/obstacles",
    "/apollo/prediction",
]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def elapsed_seconds(record: Dict[str, Any], now: datetime | None = None) -> int:
    """Return active recording time; a paused segment does not count."""
    session = record.get("session", {}) or {}
    base = float(record.get("elapsed_sec", 0) or 0)
    resumed = _parse_time(str(session.get("resumed_at", ""))) if session.get("phase") == "recording" else None
    if resumed:
        base += max(0.0, ((now or datetime.now().astimezone()) - resumed).total_seconds())
    return int(base)


def is_active(record: Dict[str, Any]) -> bool:
    session = record.get("session", {}) or {}
    return bool(session.get("active")) and record.get("status") in {"recording", "paused"}


def _host_path(settings: Settings, path: str) -> Path:
    prefix = settings.apollo_workspace_container.rstrip("/") + "/"
    if path.startswith(prefix):
        return Path(settings.apollo_workspace_host).expanduser() / path[len(prefix):]
    return Path(path).expanduser()


def _artifacts(settings: Settings, base_path: str) -> Tuple[List[Path], int]:
    host_path = _host_path(settings, base_path)
    parent = host_path.parent
    files = sorted(parent.glob(host_path.name + "*")) if parent.exists() else []
    files = [path for path in files if path.is_file() and ".record" in path.name]
    return files, sum(path.stat().st_size for path in files)


def _process_alive(settings: Settings, pid: int) -> bool:
    if pid <= 0:
        return False
    result = docker_exec(settings, ["bash", "-c", f"kill -0 {pid} >/dev/null 2>&1"], timeout=10)
    return result.ok


def _signal(settings: Settings, pid: int, signal: str) -> None:
    result = docker_exec(settings, ["bash", "-c", f"kill -{signal} {pid}"], timeout=10)
    if not result.ok:
        raise RuntimeError((result.stderr or result.stdout or f"无法向录制进程发送 {signal}").strip())


def _record_command(settings: Settings, record_path: str) -> List[str]:
    command = ["cyber_recorder", "record", "-o", record_path]
    for channel in CHANNELS:
        command.extend(["-c", channel])
    return command


def _persist(store: ExperimentStore, experiment: Dict[str, Any]) -> None:
    store.save(experiment)


def start_recording(
    settings: Settings,
    store: ExperimentStore,
    experiment: Dict[str, Any],
    *,
    tag: str,
    execute: bool,
) -> Dict[str, Any]:
    exp_id = experiment["meta"]["experiment_id"]
    record_dir = f"{settings.record_root_container}/{exp_id}"
    record_base = f"{record_dir}/{tag}.record"
    command = _record_command(settings, record_base)
    preview = shlex.join(command)
    previous = experiment.get("record", {}) or {}
    if is_active(previous):
        raise RuntimeError("当前实验已经在录制或暂停中")

    record: Dict[str, Any] = {
        "path": record_base,
        "directory": record_dir,
        "profile": "pnc",
        "channels_requested": CHANNELS,
        "channel_count": None,
        "status": "dry-run" if not execute else "starting",
        "command_preview": preview,
        "elapsed_sec": 0,
        "session": {
            "active": False,
            "phase": "dry-run" if not execute else "starting",
            "segments": 1,
        },
    }
    experiment["record"] = record
    if not execute:
        _persist(store, experiment)
        return record

    experiment["meta"]["mode"] = "real"
    mkdir = docker_exec(settings, ["bash", "-c", f"mkdir -p {shlex.quote(record_dir)}"], timeout=30)
    if not mkdir.ok:
        record["status"] = "failed"
        record["session"]["phase"] = "failed"
        experiment["meta"]["status"] = "record_failed"
        store.add_error(experiment, "record-start", "无法创建 record 目录", mkdir.stderr)
        _persist(store, experiment)
        raise RuntimeError((mkdir.stderr or mkdir.stdout or "无法创建 record 目录").strip())

    log_path = f"{record_dir}/cyber_recorder.log"
    launch = (
        "source /opt/apollo/neo/setup.sh >/dev/null 2>&1; "
        f"cd /apollo_workspace; nohup {shlex.join(command)} > {shlex.quote(log_path)} 2>&1 & echo \\$!"
    )
    result = docker_exec(settings, ["bash", "-c", launch], timeout=30)
    pid_match = re.search(r"(?m)^\s*(\d+)\s*$", result.stdout)
    if not result.ok or not pid_match:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        detail = f"cyber_recorder 启动失败（returncode={result.returncode}，未取得进程 PID）"
        if output:
            detail += "：" + output[-4000:]
        record["status"] = "failed"
        record["session"]["phase"] = "failed"
        record["launch_error"] = detail[-4000:]
        experiment["meta"]["status"] = "record_failed"
        store.add_error(experiment, "record-start", "cyber_recorder 启动失败", detail)
        _persist(store, experiment)
        raise RuntimeError(detail)

    pid = int(pid_match.group(1))
    time.sleep(0.8)
    alive = _process_alive(settings, pid)
    if not alive:
        log = docker_exec(settings, ["bash", "-c", f"tail -n 80 {shlex.quote(log_path)} 2>/dev/null"], timeout=15)
        detail = (log.stdout or log.stderr or "cyber_recorder 启动后立即退出").strip()
        record["status"] = "failed"
        record["session"]["phase"] = "failed"
        record["launch_error"] = detail[-4000:]
        experiment["meta"]["status"] = "record_failed"
        store.add_error(experiment, "record-start", "cyber_recorder 启动后立即退出", detail)
        _persist(store, experiment)
        raise RuntimeError(detail)

    started_at = _now()
    record.update({
        "status": "recording",
        "pid": pid,
        "log_path": log_path,
        "started_at": started_at,
        "elapsed_sec": 0,
    })
    record["session"].update({
        "active": True,
        "phase": "recording",
        "pid": pid,
        "started_at": started_at,
        "resumed_at": started_at,
        "paused_at": "",
        "paused_total_sec": 0,
    })
    experiment["meta"]["status"] = "recording"
    _persist(store, experiment)
    return record


def pause_recording(settings: Settings, store: ExperimentStore, experiment: Dict[str, Any]) -> Dict[str, Any]:
    record = experiment.get("record", {}) or {}
    session = record.get("session", {}) or {}
    if not is_active(record) or session.get("phase") != "recording":
        raise RuntimeError("当前没有正在运行的录制会话")
    pid = int(session.get("pid") or record.get("pid") or 0)
    if not _process_alive(settings, pid):
        record["status"] = "failed"
        session["phase"] = "failed"
        session["active"] = False
        experiment["meta"]["status"] = "record_failed"
        store.add_error(experiment, "record-pause", "录制进程已意外退出", "")
        _persist(store, experiment)
        raise RuntimeError("录制进程已意外退出，无法暂停")
    _signal(settings, pid, "STOP")
    now = _now()
    record["elapsed_sec"] = elapsed_seconds(record)
    record["status"] = "paused"
    session.update({"phase": "paused", "paused_at": now, "resumed_at": ""})
    experiment["meta"]["status"] = "recording_paused"
    _persist(store, experiment)
    return record


def resume_recording(settings: Settings, store: ExperimentStore, experiment: Dict[str, Any]) -> Dict[str, Any]:
    record = experiment.get("record", {}) or {}
    session = record.get("session", {}) or {}
    if not is_active(record) or session.get("phase") != "paused":
        raise RuntimeError("当前没有可继续的暂停录制")
    pid = int(session.get("pid") or record.get("pid") or 0)
    if not _process_alive(settings, pid):
        record["status"] = "failed"
        session["phase"] = "failed"
        session["active"] = False
        experiment["meta"]["status"] = "record_failed"
        store.add_error(experiment, "record-resume", "录制进程已意外退出", "")
        _persist(store, experiment)
        raise RuntimeError("录制进程已意外退出，无法继续")
    _signal(settings, pid, "CONT")
    now = _now()
    record["status"] = "recording"
    session.update({"phase": "recording", "resumed_at": now, "paused_at": ""})
    experiment["meta"]["status"] = "recording"
    _persist(store, experiment)
    return record


def stop_recording(settings: Settings, store: ExperimentStore, experiment: Dict[str, Any]) -> Dict[str, Any]:
    record = experiment.get("record", {}) or {}
    session = record.get("session", {}) or {}
    if not is_active(record):
        raise RuntimeError("当前没有可结束的录制会话")
    pid = int(session.get("pid") or record.get("pid") or 0)
    record["elapsed_sec"] = elapsed_seconds(record)
    if _process_alive(settings, pid):
        if session.get("phase") == "paused":
            _signal(settings, pid, "CONT")
            time.sleep(0.1)
        _signal(settings, pid, "INT")
        for _ in range(25):
            if not _process_alive(settings, pid):
                break
            time.sleep(0.4)
    if _process_alive(settings, pid):
        _signal(settings, pid, "TERM")
        time.sleep(0.8)
    still_running = _process_alive(settings, pid)
    files, total_bytes = _artifacts(settings, record.get("path", ""))
    has_record = bool(files) and total_bytes > 0
    now = _now()
    record.update({
        "status": "recorded" if has_record else "failed",
        "file_count": len(files),
        "size_bytes": total_bytes,
        "stop_reason": "manual",
        "stop_requested_at": now,
    })
    if files:
        record["path"] = f"{record.get('directory', '')}/{files[0].name}" if record.get("directory") else str(files[0])
    session.update({"active": False, "phase": "stopped", "stopped_at": now})
    experiment["meta"]["status"] = "recorded" if has_record else "record_failed"
    if has_record:
        store.add_evidence(
            experiment,
            "record",
            record["path"],
            f"录制 {record.get('elapsed_sec', 0)} 秒，{len(files)} 个文件，{len(CHANNELS)} 个核心 channel 请求",
        )
    else:
        store.add_error(experiment, "record-stop", "record 文件未生成或为空", "")
    if still_running:
        store.add_error(experiment, "record-stop", "录制进程未能在超时前退出", f"pid={pid}")
    _persist(store, experiment)
    return record