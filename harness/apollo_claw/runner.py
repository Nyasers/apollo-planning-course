"""Whitelisted command runner for host and Apollo container."""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import Settings

HOST_WHITELIST = {"docker", "aem", "buildtool", "python3", "bash", "sh", "ls", "cat", "grep", "find", "head", "tail", "wc", "df", "du", "free", "uname", "test", "mkdir"}
CONTAINER_WHITELIST = {"cyber_recorder", "cyber_monitor", "cyber_channel", "python3", "bash", "aem", "buildtool", "ls", "cat", "grep", "find", "head", "tail", "wc", "mkdir", "test", "source"}


@dataclass
class CommandResult:
    argv: List[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _check_whitelist(argv: List[str], whitelist: set[str]) -> None:
    if not argv:
        raise ValueError("empty command")
    name = argv[0]
    if name not in whitelist:
        raise PermissionError(f"command not allowed: {name}")


def run_host(argv: List[str], timeout: int = 60, check_whitelist: bool = True) -> CommandResult:
    if check_whitelist:
        _check_whitelist(argv, HOST_WHITELIST)
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return CommandResult(argv, proc.returncode, proc.stdout, proc.stderr)


def docker_exec(settings: Settings, command: str, timeout: int = 120, env: Optional[Dict[str, str]] = None) -> CommandResult:
    try:
        argv_preview = shlex.split(command)
        if argv_preview and argv_preview[0] not in CONTAINER_WHITELIST:
            raise PermissionError(f"container command not allowed: {argv_preview[0]}")
    except ValueError:
        pass
    env = env or {}
    argv = ["docker", "exec", "-u", settings.apollo_container_user]
    base_env = {
        "HOME": f"/home/{settings.apollo_container_user}",
        "CYBER_IP": settings.cyber_ip,
        "CYBER_DOMAIN_ID": settings.cyber_domain_id,
        "CYBER_PATH": "/apollo/cyber",
        "APOLLO_ROOT_DIR": "/apollo",
        "APOLLO_DAG_PATH": "/apollo",
        "APOLLO_LAUNCH_PATH": "/apollo",
        "APOLLO_CONF_PATH": "/apollo",
        "APOLLO_FLAG_PATH": "/apollo",
        "PYTHONPATH": "/opt/apollo/neo/python",
        "PATH": "/opt/apollo/neo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }
    base_env.update(env)
    for key, value in base_env.items():
        argv.extend(["-e", f"{key}={value}"])
    argv.extend([settings.apollo_container_name, "bash", "-lc", command])
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return CommandResult(argv, proc.returncode, proc.stdout, proc.stderr)

