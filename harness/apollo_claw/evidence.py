"""Evidence and report data helpers."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def empty_evidence(task: str, scenario: str = "") -> Dict[str, Any]:
    return {
        "meta": {
            "experiment_id": datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + task,
            "task": task,
            "scenario": scenario or task,
            "created_at": datetime.now().astimezone().isoformat(),
            "source": "local-harness",
            "mode": "planned",
        },
        "environment": {},
        "record": {},
        "metrics": {},
        "ai": {},
        "verification": {},
        "evidence": [],
        "capability": {},
    }
