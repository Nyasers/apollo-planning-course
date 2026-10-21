"""Transparent local self-scoring on top of Apollo Claw evaluation results."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

CRITICAL_METRICS = {
    "SpeedLimit",
    "TTC",
    "OnRoad",
    "TimeLimit",
    "ReachEnd",
    "Collision",
    "DistToObstacleCar",
    "KeyPoint",
}

PERFORMANCE_WEIGHT = 0.8
COMFORT_WEIGHT = 0.2


def _number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def threshold_score(value: Any, threshold: float) -> Optional[float]:
    """Score 100 below the threshold, 0 at twice the threshold, linear between."""
    number = _number(value)
    limit = _number(threshold)
    if number is None or limit is None or limit <= 0:
        return None
    number = max(0.0, number)
    if number <= limit:
        return 100.0
    if number >= 2 * limit:
        return 0.0
    return round(100.0 * (2.0 - number / limit), 1)


def _metric_items(score_metrics: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for metric in score_metrics or []:
        if not isinstance(metric, dict):
            continue
        passed = bool(metric.get("pass"))
        score = _number(metric.get("score"))
        if not passed:
            score = 0.0
        items.append({
            "name": metric.get("name", ""),
            "pass": passed,
            "score": score,
            "critical": metric.get("name") in CRITICAL_METRICS,
        })
    return items


def _comfort_breakdown(metrics: Dict[str, Any]) -> Dict[str, Any]:
    specs = [
        ("longitudinal_accel", "纵向加速度", "max_lon_accel", 3.0, 0.30, "m/s²"),
        ("jerk", "纵向 Jerk", "max_jerk", 4.0, 0.30, "m/s³"),
        ("lateral_accel", "横向加速度", "max_lat_accel", 2.0, 0.20, "m/s²"),
    ]
    components = []
    weighted_sum = 0.0
    available_weight = 0.0
    for key, label, metric_key, limit, weight, unit in specs:
        measured = _number(metrics.get(metric_key))
        component_score = threshold_score(measured, limit)
        if component_score is None:
            continue
        components.append({
            "id": key,
            "label": label,
            "measured": measured,
            "threshold": limit,
            "unit": unit,
            "score": component_score,
            "weight": weight,
        })
        weighted_sum += component_score * weight
        available_weight += weight

    hard_brake = _number(metrics.get("hard_brake"))
    if hard_brake is not None:
        hard_brake = max(0, int(round(hard_brake)))
        component_score = max(0.0, 100.0 - 25.0 * hard_brake)
        components.append({
            "id": "hard_brake",
            "label": "急刹车",
            "measured": hard_brake,
            "threshold": 0,
            "unit": "次",
            "score": component_score,
            "weight": 0.20,
        })
        weighted_sum += component_score * 0.20
        available_weight += 0.20

    score = round(weighted_sum / available_weight, 1) if available_weight else None
    return {
        "score": score,
        "components": components,
        "weights_rebalanced": available_weight not in (0.0, 1.0),
    }


def compute_self_score(
    score_section: Dict[str, Any],
    metrics: Dict[str, Any],
    *,
    scenario_pass: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build a transparent, explicitly non-official score for one experiment."""
    items = _metric_items((score_section or {}).get("metrics", []))
    scored = [item["score"] for item in items if item.get("score") is not None]
    performance_score = round(sum(scored) / len(scored), 1) if scored else None

    critical_failures = [
        item["name"] for item in items if item["critical"] and not item["pass"]
    ]
    gate_passed = scenario_pass
    if gate_passed is None:
        gate_passed = not critical_failures
    else:
        gate_passed = bool(gate_passed) and not critical_failures

    comfort = _comfort_breakdown(metrics or {})
    comfort_score = comfort["score"]
    if not gate_passed:
        overall = 0.0
    elif performance_score is None:
        overall = None
    elif comfort_score is None:
        overall = performance_score
    else:
        overall = round(
            performance_score * PERFORMANCE_WEIGHT
            + comfort_score * COMFORT_WEIGHT,
            1,
        )

    return {
        "value": overall,
        "performance_score": performance_score,
        "comfort_score": comfort_score,
        "performance_weight": PERFORMANCE_WEIGHT,
        "comfort_weight": COMFORT_WEIGHT,
        "gate_passed": bool(gate_passed),
        "gate_status": "PASS" if gate_passed else "FAIL",
        "critical_failures": critical_failures,
        "critical_metrics": sorted(CRITICAL_METRICS),
        "comfort_components": comfort["components"],
        "comfort_weights_rebalanced": comfort["weights_rebalanced"],
        "method": "performance 80% + comfort 20%; critical gate failure => 0",
        "is_official": False,
    }