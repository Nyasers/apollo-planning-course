"""Layered probes for the local WSL, Docker, Apollo and DreamView runtime."""
from __future__ import annotations

import shlex
import subprocess
import time
import urllib.request
from typing import Any, Dict

from .config import Settings
from .runner import decode_process_output, run_wsl


_WSL_STATES = {"Running", "Stopped", "Installing", "Uninstalling", "Converting", "Disabled"}


def check_dreamview(settings: Settings) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(settings.dreamview_url, timeout=settings.dreamview_timeout) as response:
            return {
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "url": settings.dreamview_url,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": settings.dreamview_url}


def wsl_distribution(settings: Settings) -> Dict[str, Any]:
    """Inspect distro state without starting a stopped WSL distribution."""
    argv = ["wsl.exe", "-l", "-v"]
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=10, check=False)
        text = decode_process_output(proc.stdout)
        error = decode_process_output(proc.stderr)
    except Exception as exc:
        return {
            "installed": False,
            "running": False,
            "state": "unknown",
            "distro": settings.wsl_distro,
            "error": str(exc),
        }

    rows = []
    for raw in text.splitlines():
        line = raw.replace("*", " ").strip()
        if not line:
            continue
        parts = line.split()
        state = next((part for part in parts if part in _WSL_STATES), "")
        if state:
            rows.append({"name": parts[0], "state": state, "version": parts[-1]})
    match = next((row for row in rows if row["name"] == settings.wsl_distro), None)
    if match:
        return {
            "installed": True,
            "running": match["state"].lower() == "running",
            "state": match["state"],
            "distro": match["name"],
            "version": match["version"],
        }
    return {
        "installed": False,
        "running": False,
        "state": "not-found",
        "distro": settings.wsl_distro,
        "error": error.strip() or text.strip()[:1000],
    }


def _parse_key_values(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def probe_runtime(settings: Settings) -> Dict[str, Any]:
    """Return a non-invasive layered snapshot of the real local runtime."""
    linux = wsl_distribution(settings)
    dreamview = check_dreamview(settings)
    docker: Dict[str, Any] = {"started": False, "version": ""}
    apollo: Dict[str, Any] = {
        "started": False,
        "container": settings.apollo_container_name,
        "state": "unknown",
    }
    kernel = ""
    uptime_sec = None
    probe_error = ""

    if linux.get("running"):
        container = shlex.quote(settings.apollo_container_name)
        script = (
            "printf 'KERNEL=%s\\n' \"$(uname -r)\"; "
            "printf 'UPTIME=%s\\n' \"$(awk '{print int($1)}' /proc/uptime 2>/dev/null)\"; "
            "printf 'DOCKER_VERSION=%s\\n' \"$(docker info --format '{{.ServerVersion}}' 2>/dev/null)\"; "
            f"printf 'CONTAINER_STATE=%s\\n' \"$(docker inspect -f '{{{{.State.Status}}}}' {container} 2>/dev/null)\""
        )
        probe = run_wsl(settings, script, timeout=20)
        values = _parse_key_values(probe.stdout)
        kernel = values.get("KERNEL", "")
        try:
            uptime_sec = int(values.get("UPTIME", "") or 0)
        except ValueError:
            uptime_sec = None
        docker["version"] = values.get("DOCKER_VERSION", "")
        docker["started"] = bool(docker["version"])
        apollo["state"] = values.get("CONTAINER_STATE", "") or "stopped"
        apollo["started"] = apollo["state"] == "running"
        if not probe.ok:
            probe_error = (probe.stderr or probe.stdout).strip()[-2000:]
    elif linux.get("installed"):
        docker["detail"] = "WSL 尚未运行，已跳过启动检查"
        apollo["detail"] = "WSL 尚未运行，已跳过容器检查"
    else:
        docker["error"] = "未找到配置的 WSL 发行版"
        apollo["error"] = "未找到配置的 WSL 发行版"

    simulation_started = bool(
        linux.get("running") and docker["started"] and apollo["started"] and dreamview.get("ok")
    )
    if not linux.get("running"):
        summary = "Linux 环境未启动"
    elif not docker["started"]:
        summary = "Linux 已启动，Docker 未就绪"
    elif not apollo["started"]:
        summary = "Linux 和 Docker 已启动，Apollo 仿真容器未运行"
    elif not dreamview.get("ok"):
        summary = "仿真容器已运行，DreamView 未就绪"
    else:
        summary = "Linux、Docker、Apollo 容器和 DreamView 均已就绪"

    return {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "linux": {
            **linux,
            "kernel": kernel,
            "uptime_sec": uptime_sec,
        },
        "docker": docker,
        "apollo": apollo,
        "dreamview": dreamview,
        "simulation": {"started": simulation_started, "summary": summary},
        "error": probe_error,
    }


def stop_simulation(settings: Settings) -> Dict[str, Any]:
    """Stop Apollo and fully shut down WSL so no related processes remain."""
    before = probe_runtime(settings)
    script = f"bash {shlex.quote(settings.apollo_stop_script)}"
    result = run_wsl(settings, script, timeout=180)
    shutdown_argv = ["wsl.exe", "--shutdown"]
    try:
        shutdown_proc = subprocess.run(shutdown_argv, capture_output=True, timeout=30, check=False)
        shutdown_ok = shutdown_proc.returncode == 0
        shutdown_stdout = decode_process_output(shutdown_proc.stdout)
        shutdown_stderr = decode_process_output(shutdown_proc.stderr)
    except Exception as exc:
        shutdown_ok = False
        shutdown_stdout = ""
        shutdown_stderr = str(exc)
    time.sleep(1)
    after = probe_runtime(settings)
    return {
        "before": before,
        "after": after,
        "command_ok": result.ok,
        "command_returncode": result.returncode,
        "command_stdout": result.stdout[-8000:],
        "command_stderr": result.stderr[-8000:],
        "shutdown_ok": shutdown_ok,
        "shutdown_stdout": shutdown_stdout[-2000:],
        "shutdown_stderr": shutdown_stderr[-2000:],
    }

def start_simulation(settings: Settings) -> Dict[str, Any]:
    """Start WSL if needed, then run the documented Apollo/DreamView script."""
    before = probe_runtime(settings)
    script = f"bash {shlex.quote(settings.apollo_start_script)}"
    result = run_wsl(settings, script, timeout=300)
    after = probe_runtime(settings)
    if not after["simulation"]["started"]:
        for _ in range(6):
            if after["dreamview"].get("ok"):
                break
            time.sleep(2)
            after = probe_runtime(settings)
    return {
        "before": before,
        "after": after,
        "command_ok": result.ok,
        "command_returncode": result.returncode,
        "command_stdout": result.stdout[-8000:],
        "command_stderr": result.stderr[-8000:],
    }