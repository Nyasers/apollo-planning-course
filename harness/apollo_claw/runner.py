"""Whitelisted command runner for host and Apollo container."""
from __future__ import annotations

import locale
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import Settings

HOST_WHITELIST = {
    "docker", "aem", "buildtool", "python3", "bash", "sh", "ls", "cat", "grep", "find",
    "head", "tail", "wc", "df", "du", "free", "uname", "test", "mkdir", "timeout",
}
CONTAINER_WHITELIST = {
    "cyber_recorder", "cyber_monitor", "cyber_channel", "python3", "bash", "sh", "aem",
    "buildtool", "ls", "cat", "grep", "find", "head", "tail", "wc", "mkdir", "test",
    "source", "timeout",
}


@dataclass
class CommandResult:
    argv: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float = 0.0
    timed_out: bool = False
    mode: str = "host"

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "argv": self.argv,
            "returncode": self.returncode,
            "ok": self.ok,
            "timed_out": self.timed_out,
            "duration_sec": round(self.duration_sec, 3),
            "stdout_tail": self.stdout[-4000:],
            "stderr_tail": self.stderr[-4000:],
        }


def _check_whitelist(argv: List[str], whitelist: set[str]) -> None:
    if not argv:
        raise ValueError("empty command")
    if argv[0] not in whitelist:
        raise PermissionError(f"command not allowed: {argv[0]}")


def run_host(argv: Iterable[str], timeout: int = 60, check_whitelist: bool = True) -> CommandResult:
    command = list(argv)
    if check_whitelist:
        _check_whitelist(command, HOST_WHITELIST)
    started = time.monotonic()
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return CommandResult(command, proc.returncode, proc.stdout, proc.stderr, time.monotonic() - started, mode="host")
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(command, 124, stdout, stderr + "\ncommand timed out", time.monotonic() - started, True, "host")


def docker_exec(settings: Settings, command: Iterable[str], timeout: Optional[int] = None, env: Optional[Dict[str, str]] = None, check_whitelist: bool = True) -> CommandResult:
    """Execute a quoted argv inside the Apollo container.

    The command is passed as a list, not as an unquoted user string. The only
    shell layer is the container's explicit `bash -lc`, needed for Apollo's
    environment setup and `source` commands.
    """
    command = list(command)
    if check_whitelist:
        _check_whitelist(command, CONTAINER_WHITELIST)
    env = env or {}
    base_env = {
        "HOME": f"/home/{settings.apollo_container_user}",
        "CYBER_IP": settings.cyber_ip,
        "CYBER_DOMAIN_ID": settings.cyber_domain_id,
        "CYBER_PATH": "/apollo/cyber",
        "APOLLO_ROOT_DIR": "/apollo",
        "APOLLO_PATH": "/apollo",
        "APOLLO_DAG_PATH": "/apollo",
        "APOLLO_LAUNCH_PATH": "/apollo",
        "APOLLO_CONF_PATH": "/apollo",
        "APOLLO_FLAG_PATH": "/apollo",
        "APOLLO_DISTRIBUTION_HOME": "/opt/apollo/neo",
        "APOLLO_DISTRIBUTION_VERSION": "9.0",
        "APOLLO_LIB_PATH": "/opt/apollo/neo/lib",
        "APOLLO_RUNTIME_PATH": "/apollo",
        "APOLLO_SYSROOT_DIR": "/opt/apollo/sysroot",
        "APOLLO_IN_DOCKER": "true",
        "APOLLO_PLUGIN_DESCRIPTION_PATH": "/apollo_workspace:/opt/apollo/neo",
        "APOLLO_PLUGIN_INDEX_PATH": "/opt/apollo/neo/share/cyber_plugin_index",
        "APOLLO_PLUGIN_LIB_PATH": "/opt/apollo/neo/lib",
        "PYTHONPATH": "/opt/apollo/neo/python",
        "PYTHONIOENCODING": "utf-8",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/opt/apollo/neo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }
    base_env.update(env)
    argv = ["docker", "exec", "-u", settings.apollo_container_user]
    for key, value in base_env.items():
        argv.extend(["-e", f"{key}={value}"])
    argv.extend([settings.apollo_container_name, "bash", "-lc", shlex.join(command)])
    started = time.monotonic()
    timeout = timeout or settings.container_tool_timeout
    if os.name == "nt":
        # The Apollo Docker daemon and CLI live inside WSL on Windows hosts.
        # Calling the Windows docker.exe either fails outright or targets a
        # different daemon, so proxy the full docker command through WSL.
        result = run_wsl(settings, shlex.join(argv), timeout=timeout)
        result.argv = command
        result.mode = "container-wsl"
        return result
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return CommandResult(command, proc.returncode, proc.stdout, proc.stderr, time.monotonic() - started, mode="container")
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(command, 124, stdout, stderr + "\ncommand timed out", time.monotonic() - started, True, "container")


def decode_process_output(raw: bytes) -> str:
    """Decode Windows/WSL command output without assuming the ANSI code page."""
    if not raw:
        return ""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    if raw.count(b"\x00") > max(4, len(raw) // 4):
        return raw.decode("utf-16-le", errors="replace")
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def run_wsl(settings: Settings, command: str, timeout: int = 60) -> CommandResult:
    """Run a fixed command inside the configured WSL distribution.

    Invoking WSL also starts a stopped distribution. Callers must check the VM
    state first when they need a non-invasive probe.
    """
    argv = [
        "wsl.exe", "-d", settings.wsl_distro, "-u", settings.wsl_user,
        "--", "bash", "-lc", command,
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
        return CommandResult(
            argv,
            proc.returncode,
            decode_process_output(proc.stdout),
            decode_process_output(proc.stderr),
            time.monotonic() - started,
            mode="wsl",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = decode_process_output(exc.stdout or b"")
        stderr = decode_process_output(exc.stderr or b"")
        return CommandResult(argv, 124, stdout, stderr + "\ncommand timed out", time.monotonic() - started, True, "wsl")

def save_command_output(result: CommandResult, directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (directory / f"{stem}.stderr.txt").write_text(result.stderr, encoding="utf-8")
