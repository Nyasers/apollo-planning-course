"""Configuration loading for Apollo Claw Harness."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Settings:
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    apollo_container_name: str = "apollo_neo_dev_edu"
    apollo_container_user: str = "fqx"
    apollo_workspace_host: str = str(Path.home() / "application-pnc")
    apollo_workspace_container: str = "/apollo_workspace"
    cyber_ip: str = "127.0.0.1"
    cyber_domain_id: str = "80"
    output_dir: str = str(Path.home() / ".apollo-claw" / "outputs")

    @classmethod
    def load(cls) -> "Settings":
        load_env_file(Path.home() / ".apollo-claw" / ".env")
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            apollo_container_name=os.getenv("APOLLO_CONTAINER_NAME", "apollo_neo_dev_edu"),
            apollo_container_user=os.getenv("APOLLO_CONTAINER_USER", "fqx"),
            apollo_workspace_host=os.getenv("APOLLO_WORKSPACE_HOST", str(Path.home() / "application-pnc")),
            apollo_workspace_container=os.getenv("APOLLO_WORKSPACE_CONTAINER", "/apollo_workspace"),
            cyber_ip=os.getenv("CYBER_IP", "127.0.0.1"),
            cyber_domain_id=os.getenv("CYBER_DOMAIN_ID", "80"),
            output_dir=os.getenv("APOLLO_CLAW_OUTPUT_DIR", str(Path.home() / ".apollo-claw" / "outputs")),
        )
