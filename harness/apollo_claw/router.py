"""Map user intent to Apollo Claw skill."""
from __future__ import annotations

from typing import Dict


RULES: Dict[str, str] = {
    "docker": "apollo-env",
    "aem": "apollo-env",
    "buildtool": "apollo-env",
    "安装": "apollo-env",
    "环境": "apollo-env",
    "仿真": "apollo-dev",
    "planning": "apollo-dev",
    "task": "apollo-dev",
    "scenario": "apollo-dev",
    "配置": "apollo-dev",
    "日志": "apollo-dev",
    "record": "apollo-test",
    "channel": "apollo-test",
    "录包": "apollo-test",
    "评分": "apollo-eval",
    "ttc": "apollo-eval",
    "jerk": "apollo-eval",
    "加速度": "apollo-eval",
    "优化": "apollo-eval",
}


def route(text: str) -> str:
    lower = (text or "").lower()
    for key, skill in RULES.items():
        if key.lower() in lower:
            return skill
    return "apollo-dev"
