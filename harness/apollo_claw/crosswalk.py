"""Crosswalk stopping-distance calibration and relative measurement."""
from __future__ import annotations

import csv
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

STOP_SPEED_THRESHOLD_MPS = 0.3
MIN_STOP_DURATION_SEC = 1.0
CALIBRATION_SCHEMA = "apollo-crosswalk-calibration-v1"
DEFAULT_REFERENCE = "front_bumper_to_crosswalk_near_edge"
DISTANCE_MIN_M = 1.5
DISTANCE_MAX_M = 2.0


def _number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def read_localization_rows(path: Path) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            row = {key: _number(item.get(key)) for key in ("t", "x", "y", "heading", "speed_mps")}
            if all(value is not None for value in row.values()):
                rows.append(row)  # type: ignore[arg-type]
    rows.sort(key=lambda item: item["t"])
    return rows


def find_stop_pose(rows: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find a sustained low-speed interval between movement phases."""
    ordered = sorted(rows, key=lambda item: float(item.get("t", 0.0)))
    intervals: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    started = False
    for row in ordered:
        speed = _number(row.get("speed_mps")) or 0.0
        if speed > 1.0:
            started = True
        low = started and speed <= STOP_SPEED_THRESHOLD_MPS
        if low:
            current.append(row)
        elif current:
            intervals.append(current)
            current = []
    if current:
        intervals.append(current)

    candidates = []
    for index, group in enumerate(intervals):
        if len(group) < 2:
            continue
        start_t = float(group[0].get("t", 0.0))
        end_t = float(group[-1].get("t", start_t))
        duration = end_t - start_t
        if start_t < 3.0 or duration < MIN_STOP_DURATION_SEC:
            continue
        after = any(
            float(item.get("t", 0.0)) > end_t
            and (_number(item.get("speed_mps")) or 0.0) > 1.0
            for item in ordered
        )
        candidates.append((after, duration, group))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, duration, group = candidates[0]
    x = statistics.median(float(item.get("x", 0.0)) for item in group)
    y = statistics.median(float(item.get("y", 0.0)) for item in group)
    heading = statistics.median(float(item.get("heading", 0.0)) for item in group)
    t = statistics.median(float(item.get("t", 0.0)) for item in group)
    return {
        "t": round(t, 3),
        "x": round(x, 6),
        "y": round(y, 6),
        "heading": round(heading, 6),
        "duration_sec": round(duration, 3),
        "speed_max_mps": round(max(float(item.get("speed_mps", 0.0)) for item in group), 4),
    }


def measure_distance(
    experiment_id: str,
    stop_pose: Dict[str, Any],
    calibration: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    known = _number(calibration.get("distance_m"))
    known_pose = calibration.get("stop_pose") or {}
    x0 = _number(known_pose.get("x"))
    y0 = _number(known_pose.get("y"))
    heading = _number(known_pose.get("heading"))
    x = _number(stop_pose.get("x"))
    y = _number(stop_pose.get("y"))
    if known is None or None in (x0, y0, heading, x, y):
        return None
    if str(calibration.get("experiment_id", "")) == experiment_id:
        distance = known
        source = "manual_calibration"
    else:
        along = (x - x0) * math.cos(heading) + (y - y0) * math.sin(heading)
        distance = known - along
        source = "relative_to_calibration"
    distance = round(distance, 3)
    return {
        "distance_m": distance,
        "pass": bool(DISTANCE_MIN_M <= distance <= DISTANCE_MAX_M),
        "min_m": DISTANCE_MIN_M,
        "max_m": DISTANCE_MAX_M,
        "reference": calibration.get("reference", DEFAULT_REFERENCE),
        "source": source,
        "calibration_experiment_id": calibration.get("experiment_id"),
        "calibration_distance_m": known,
        "stop_pose": stop_pose,
    }


def load_calibration(path: Path) -> Optional[Dict[str, Any]]:
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") == CALIBRATION_SCHEMA and _number(data.get("distance_m")) is not None:
            return data
    except (OSError, ValueError, TypeError):
        return None
    return None


def save_calibration(path: Path, experiment_id: str, distance_m: float, stop_pose: Dict[str, Any]) -> Path:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": CALIBRATION_SCHEMA,
        "experiment_id": experiment_id,
        "distance_m": round(float(distance_m), 3),
        "reference": DEFAULT_REFERENCE,
        "stop_pose": stop_pose,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
