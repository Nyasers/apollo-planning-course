"""Resolve the four Apollo Claw skills without copying them into the package."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .config import Settings

SKILL_NAMES = ("apollo-env", "apollo-dev", "apollo-test", "apollo-eval")


def _candidate_roots(settings: Settings) -> Iterable[Path]:
    if settings.skills_dir:
        yield Path(settings.skills_dir).expanduser()
    yield Path.home() / ".apollo-claw" / "skills"
    yield Path.home() / ".openclaw" / "skills"
    yield Path(settings.apollo_workspace_host).expanduser() / ".comate" / "skills"
    yield Path.cwd() / "skills"
    yield Path(__file__).resolve().parents[1] / "skills"


def find_skill_root(settings: Settings) -> Optional[Path]:
    seen = set()
    for root in _candidate_roots(settings):
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if all((root / name).is_dir() for name in SKILL_NAMES):
            return root
    return None


@dataclass(frozen=True)
class SkillPaths:
    root: Optional[Path]

    @property
    def env_script(self) -> Optional[Path]:
        return self._path("apollo-env", "scripts", "env_check.sh")

    @property
    def dev_knowledge(self) -> Optional[Path]:
        return self._path("apollo-dev", "references", "knowledge")

    @property
    def test_record_script(self) -> Optional[Path]:
        return self._path("apollo-test", "scripts", "record_apollo_channels.sh")

    @property
    def test_report_script(self) -> Optional[Path]:
        return self._path("apollo-test", "scripts", "record_channel_report.py")

    @property
    def test_crosswalk_distance_script(self) -> Optional[Path]:
        path = self._path("apollo-test", "scripts", "crosswalk_stop_distance.py")
        if path:
            return path
        fallback = Path(__file__).resolve().parents[1] / "skills" / "apollo-test" / "scripts" / "crosswalk_stop_distance.py"
        return fallback if fallback.exists() else None

    @property
    def eval_grading_script(self) -> Optional[Path]:
        return self._path("apollo-eval", "scripts", "grading_system_py", "main.py")

    @property
    def eval_metrics_script(self) -> Optional[Path]:
        return self._path("apollo-eval", "scripts", "extract_metrics.py")

    @property
    def eval_realtime_script(self) -> Optional[Path]:
        return self._path("apollo-eval", "scripts", "realtime_monitor.py")

    def missing(self) -> List[str]:
        if self.root is None:
            return list(SKILL_NAMES)
        return [name for name in SKILL_NAMES if not (self.root / name).is_dir()]

    def _path(self, *parts: str) -> Optional[Path]:
        if self.root is None:
            return None
        path = self.root.joinpath(*parts)
        return path if path.exists() else None


def resolve_skills(settings: Settings) -> SkillPaths:
    return SkillPaths(find_skill_root(settings))
