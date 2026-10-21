"""Compute raw front-bumper-to-crosswalk distance from an Apollo record CSV."""
import argparse
import csv
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.common_msgs.map_msgs import map_pb2

STOP_SPEED_THRESHOLD_MPS = 0.3
MIN_STOP_DURATION_SEC = 1.0


def number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_rows(path: Path) -> List[Dict[str, float]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            row = {key: number(item.get(key)) for key in ("t", "x", "y", "heading", "speed_mps")}
            if all(value is not None for value in row.values()):
                rows.append(row)  # type: ignore[arg-type]
    return sorted(rows, key=lambda item: item["t"])


def find_stop_pose(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    intervals = []
    current = []
    started = False
    for row in rows:
        if row["speed_mps"] > 1.0:
            started = True
        low = started and row["speed_mps"] <= STOP_SPEED_THRESHOLD_MPS
        if low:
            current.append(row)
        elif current:
            intervals.append(current)
            current = []
    if current:
        intervals.append(current)

    candidates = []
    for group in intervals:
        if len(group) < 2:
            continue
        start_t = group[0]["t"]
        end_t = group[-1]["t"]
        duration = end_t - start_t
        if start_t < 3.0 or duration < MIN_STOP_DURATION_SEC:
            continue
        after = any(item["t"] > end_t and item["speed_mps"] > 1.0 for item in rows)
        candidates.append((after, duration, group))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, duration, group = candidates[0]
    return {
        "t": round(statistics.median(item["t"] for item in group), 3),
        "x": round(statistics.median(item["x"] for item in group), 6),
        "y": round(statistics.median(item["y"] for item in group), 6),
        "heading": round(statistics.median(item["heading"] for item in group), 6),
        "duration_sec": round(duration, 3),
        "speed_max_mps": round(max(item["speed_mps"] for item in group), 4),
    }


def read_front_edge(path: Path) -> float:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"front_edge_to_center\s*:\s*([0-9.]+)", text)
    if not match:
        raise ValueError(f"front_edge_to_center not found: {path}")
    return float(match.group(1))


def cross(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def ray_polygon_distance(origin: Tuple[float, float], direction: Tuple[float, float], points: List[Tuple[float, float]]) -> Optional[float]:
    best = None
    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        edge = (second[0] - first[0], second[1] - first[1])
        denominator = cross(direction, edge)
        if abs(denominator) < 1e-9:
            continue
        offset = (first[0] - origin[0], first[1] - origin[1])
        t = cross(offset, edge) / denominator
        u = cross(offset, direction) / denominator
        if t >= 0 and -1e-7 <= u <= 1 + 1e-7:
            best = t if best is None else min(best, t)
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--map-file", required=True)
    parser.add_argument("--vehicle-param", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.csv))
    stop = find_stop_pose(rows)
    if not stop:
        raise SystemExit("no sustained stop interval found")
    front_edge = read_front_edge(Path(args.vehicle_param))
    heading = float(stop["heading"])
    direction = (math.cos(heading), math.sin(heading))
    front = (
        float(stop["x"]) + front_edge * direction[0],
        float(stop["y"]) + front_edge * direction[1],
    )

    hdmap = map_pb2.Map()
    hdmap.ParseFromString(Path(args.map_file).read_bytes())
    candidates = []
    for crosswalk in hdmap.crosswalk:
        points = [(float(point.x), float(point.y)) for point in crosswalk.polygon.point]
        distance = ray_polygon_distance(front, direction, points)
        if distance is not None:
            candidates.append((distance, crosswalk.id.id, points))
    if not candidates:
        raise SystemExit("no crosswalk intersects the ego path")
    distance, crosswalk_id, points = min(candidates, key=lambda item: item[0])
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    print(json.dumps({
        "stop_pose": stop,
        "crosswalk_id": crosswalk_id,
        "front_edge_to_center_m": round(front_edge, 3),
        "front_point": [round(front[0], 6), round(front[1], 6)],
        "raw_map_distance_m": round(distance, 3),
        "crosswalk_bounds": {
            "x_min": round(min(xs), 6),
            "x_max": round(max(xs), 6),
            "y_min": round(min(ys), 6),
            "y_max": round(max(ys), 6),
        },
        "reference": "front_bumper_to_crosswalk_near_edge",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
