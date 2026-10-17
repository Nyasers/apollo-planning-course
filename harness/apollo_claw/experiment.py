"""Experiment manifest and immutable artifact directory helpers."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_slug(value: str, fallback: str = "experiment") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip()).strip("-").lower()
    return cleaned[:64] or fallback


def default_experiment_id(task: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}-{safe_slug(task)}"


def new_experiment(task: str, scenario: str = "", experiment_id: Optional[str] = None) -> Dict[str, Any]:
    exp_id = experiment_id or default_experiment_id(task)
    timestamp = now_iso()
    return {
        "meta": {
            "experiment_id": exp_id,
            "task": task,
            "scenario": scenario or task,
            "created_at": timestamp,
            "updated_at": timestamp,
            "source": "local-harness",
            "mode": "planned",
            "status": "created",
        },
        "environment": {},
        "record": {},
        "metrics": {},
        "score": {"source": "not-run", "value": None, "is_official": False},
        "ai": {},
        "verification": {},
        "evidence": [],
        "commands": [],
        "errors": [],
        "capability": {},
    }


@dataclass
class ExperimentStore:
    """Filesystem-backed experiment store.

    Layout:
        <root>/experiments/<experiment-id>/experiment.json
        <root>/experiments/<experiment-id>/report.json
        <root>/experiments/<experiment-id>/report.md
        <root>/experiments/<experiment-id>/doctor.json
        <root>/experiments/<experiment-id>/record/...
    """

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def experiments_dir(self) -> Path:
        return self.root / "experiments"

    def experiment_dir(self, experiment_id: str) -> Path:
        exp_id = safe_slug(experiment_id, "experiment")
        if exp_id != experiment_id:
            raise ValueError(f"invalid experiment id: {experiment_id!r}")
        return self.experiments_dir / exp_id

    def create(self, task: str, scenario: str = "", experiment_id: Optional[str] = None) -> Dict[str, Any]:
        experiment = new_experiment(task, scenario, experiment_id)
        self.save(experiment)
        return experiment

    def load(self, experiment_id: str) -> Dict[str, Any]:
        path = self.experiment_dir(experiment_id) / "experiment.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, experiment: Dict[str, Any]) -> Path:
        experiment.setdefault("meta", {})
        exp_id = experiment["meta"].get("experiment_id")
        if not exp_id:
            raise ValueError("experiment.meta.experiment_id is required")
        directory = self.experiment_dir(exp_id)
        directory.mkdir(parents=True, exist_ok=True)
        experiment["meta"]["updated_at"] = now_iso()
        path = directory / "experiment.json"
        path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def list(self) -> List[Dict[str, Any]]:
        if not self.experiments_dir.exists():
            return []
        items: List[Dict[str, Any]] = []
        for path in sorted(self.experiments_dir.glob("*/experiment.json"), reverse=True):
            try:
                experiment = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            items.append(experiment)
        return items

    def latest(self) -> Optional[Dict[str, Any]]:
        items = self.list()
        return items[0] if items else None

    def report_path(self, experiment_id: str) -> Path:
        return self.experiment_dir(experiment_id) / "report.json"

    def sandbox_path(self, experiment_id: str, relative_path: str) -> Path:
        """Resolve a path inside the experiment directory only."""
        directory = self.experiment_dir(experiment_id).resolve()
        candidate = (directory / relative_path).resolve()
        if candidate != directory and directory not in candidate.parents:
            raise ValueError(f"path escapes experiment directory: {relative_path}")
        return candidate

    def add_command(self, experiment: Dict[str, Any], purpose: str, argv: Iterable[str], result: Dict[str, Any]) -> None:
        experiment.setdefault("commands", []).append({
            "purpose": purpose,
            "argv": list(argv),
            "result": result,
        })

    def add_evidence(self, experiment: Dict[str, Any], kind: str, path: str, summary: str = "") -> None:
        experiment.setdefault("evidence", []).append({"type": kind, "path": path, "summary": summary})

    def add_error(self, experiment: Dict[str, Any], source: str, message: str, details: str = "") -> None:
        experiment.setdefault("errors", []).append({
            "source": source,
            "message": message,
            "details": details[-4000:],
        })

    def set_section(self, experiment: Dict[str, Any], section: str, values: Dict[str, Any]) -> None:
        current = experiment.setdefault(section, {})
        current.update(values)
