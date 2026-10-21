"""Build a beginner-readable AI presentation from structured metrics."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

GLOSSARY = {
    "max_jerk": ("最大 Jerk", "加速度变化的突然程度；越大，车辆越容易顿挫。", "m/s³", "≤ 4.0"),
    "jerk_p95": ("Jerk P95", "95% 时间内的 Jerk 水平，用于区分持续抖动和单点尖峰。", "m/s³", "越低越好"),
    "max_lon_accel": ("最大纵向加速度", "车辆加速或制动时的最大力度。", "m/s²", "≤ 3.0"),
    "max_lat_accel": ("最大横向加速度", "转弯时乘客感受到的侧向力。", "m/s²", "≤ 2.0"),
    "hard_brake": ("急刹车次数", "减速度过大的次数。", "次", "越少越好"),
    "passed_metrics": ("场景指标通过率", "通过的场景检查项数量。", "项", "全部通过"),
    "remaining_to_end_m": ("距终点距离", "录制结束时车辆距离场景终点的距离。", "m", "0 表示已到达"),
}

def _number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _fmt(value: Any, digits: int = 2) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")

def _finding(finding_id: str, title: str, value: Any, unit: str, threshold: str, status: str, severity: str, explanation: str, source: str) -> Dict[str, Any]:
    return {
        "id": finding_id, "title": title, "value": _fmt(value), "unit": unit,
        "threshold": threshold, "status": status, "severity": severity,
        "explanation": explanation, "source": source,
    }

def build_ai_presentation(experiment: Dict[str, Any], grading: Dict[str, Any], comfort: Dict[str, Any], remaining: Optional[float], ai: Dict[str, Any]) -> Dict[str, Any]:
    score = experiment.get("score", {}) or {}
    metrics = experiment.get("metrics", {}) or {}
    meta = experiment.get("meta", {}) or {}
    gate_pass = grading.get("scenario_pass")
    critical_names = {"SpeedLimit", "TTC", "OnRoad", "TimeLimit", "ReachEnd", "Collision", "DistToObstacleCar", "KeyPoint"}
    critical_failures = [item.get("name", "") for item in grading.get("metrics", []) or [] if item.get("name") in critical_names and item.get("pass") is False]

    findings: List[Dict[str, Any]] = []
    jerk = _number(metrics.get("max_jerk"))
    if jerk is None:
        jerk = _number(comfort.get("max_lon_jerk"))
    lon_accel = _number(metrics.get("max_lon_accel"))
    if lon_accel is None:
        lon_accel = _number(comfort.get("max_lon_accel"))
    lat_accel = _number(metrics.get("max_lat_accel"))
    if lat_accel is None:
        lat_accel = _number(comfort.get("max_lat_accel"))
    hard_brake = _number(metrics.get("hard_brake"))
    if hard_brake is None:
        hard_brake = _number(comfort.get("hard_brake_count"))
    if jerk is not None:
        over = jerk > 4.0
        findings.append(_finding("jerk", "加速度变化是否平顺", jerk, "m/s³", "≤ 4.0 m/s³", "明显超限" if over else "正常", "warning" if over else "success", "Jerk 表示加速度变化的突然程度。数值越高，乘客越容易感到顿挫；还需结合回放判断是否为短时尖峰。" if over else "加速度变化较平顺，没有超过当前参考阈值。", "metrics.max_jerk"))
    if lon_accel is not None:
        over = lon_accel > 3.0
        findings.append(_finding("longitudinal_accel", "加速和制动是否过猛", lon_accel, "m/s²", "≤ 3.0 m/s²", "轻微超限" if over else "正常", "warning" if over else "success", "纵向加速度越大，起步和刹车越猛烈。" if over else "纵向加速度处于参考范围内。", "metrics.max_lon_accel"))
    if lat_accel is not None:
        over = lat_accel > 2.0
        findings.append(_finding("lateral_accel", "转弯是否平稳", lat_accel, "m/s²", "≤ 2.0 m/s²", "超限" if over else "正常", "warning" if over else "success", "横向加速度越大，转弯时侧倾和不适感越明显。" if over else "横向加速度较低。", "metrics.max_lat_accel"))
    if hard_brake is not None:
        over = hard_brake > 0
        findings.append(_finding("hard_brake", "是否出现急刹车", hard_brake, "次", "0 次", "出现急刹" if over else "未出现", "warning" if over else "success", "急刹车次数反映紧急制动情况，应结合障碍物和跟车距离定位。" if over else "本次没有检测到急刹车。", "metrics.hard_brake"))
    if critical_failures:
        findings.insert(0, {"id": "critical_gate", "title": "关键场景检查", "value": f"{len(critical_failures)} 项未通过", "unit": "", "threshold": "全部通过", "status": "场景门槛未通过", "severity": "error", "explanation": "关键指标决定场景是否通过，失败时综合自评会归零。", "source": "score.metrics"})
    actions: List[Dict[str, Any]] = []
    if jerk is not None and jerk > 4.0:
        p95 = _number(metrics.get("jerk_p95"))
        if p95 is None:
            p95 = _number(comfort.get("jerk_p95"))
        actions.append({
            "priority": 1,
            "title": "先回放 Jerk 峰值附近的时间段",
            "why": "最大 Jerk 为 " + _fmt(jerk) + " m/s³，明显高于参考值 4.0。",
            "steps": ["回放峰值前后约 1 秒的数据。", "检查速度变化、加速度指令和控制输出是否突然跳变。", "结合 Jerk P95=" + _fmt(p95) + " 判断是持续抖动还是孤立尖峰。"],
            "done_when": "确认峰值是真实控制问题，还是记录或计算异常。",
        })
    if lon_accel is not None and lon_accel > 3.0:
        actions.append({
            "priority": len(actions) + 1,
            "title": "检查起步和制动过程",
            "why": "最大纵向加速度为 " + _fmt(lon_accel) + " m/s²，略高于参考阈值 3.0。",
            "steps": ["定位最大加速度出现的时刻。", "确认是否为起步、停车或避让动作。"],
            "done_when": "加速度峰值回落到参考范围内，或能解释该峰值的必要性。",
        })
    if hard_brake is not None and hard_brake > 0:
        actions.append({
            "priority": len(actions) + 1,
            "title": "提前处理障碍物减速",
            "why": "本次检测到 " + _fmt(hard_brake) + " 次急刹车。",
            "steps": ["回放急刹时刻。", "检查感知距离、TTC 和规划减速起点。"],
            "done_when": "重新录制后急刹次数下降或消失。",
        })
    if critical_failures:
        actions.insert(0, {
            "priority": 1,
            "title": "优先修复未通过的关键场景指标",
            "why": "未通过项：" + "、".join(critical_failures) + "。",
            "steps": ["打开对应指标的时间窗和事件记录。", "先修关键失败项，再做舒适性优化。"],
            "done_when": "关键指标全部 PASS，综合自评不再为 0。",
        })
    if not actions:
        actions.append({
            "priority": 1,
            "title": "保留本轮结果并进行对照复跑",
            "why": "当前主要场景指标和舒适性指标均未发现明显异常。",
            "steps": ["保存本轮 report.json。", "修改一个参数后重新录制并对比。"],
            "done_when": "确认修改没有引入退化。",
        })

    overall = _number(score.get("value"))
    passed = score.get("passed_metrics") or "—"
    if gate_pass is False:
        headline = "场景关键检查未通过，需要先修复失败项"
        severity = "error"
    elif overall is not None and overall >= 90:
        headline = "场景已通过，整体表现良好，但仍有舒适性优化空间"
        severity = "warning" if any(item["severity"] == "warning" for item in findings) else "success"
    else:
        headline = "场景已通过，但舒适性或稳定性仍需改进"
        severity = "warning"
    summary = (f"场景指标 {passed}。" if passed else "") + (f"综合自评 {_fmt(overall)} 分（非官方）。" if overall is not None else "") + ("当前最值得关注的是 Jerk 峰值。" if jerk is not None and jerk > 4.0 else "")
    questions = []
    if jerk is not None and jerk > 4.0:
        peak = _number(metrics.get("max_jerk_time"))
        point = (" " + _fmt(peak) + " 秒附近") if peak is not None else ""
        questions.append("请确认" + point + "是否出现过急刹、避让触发或仿真数据异常。")
    raw_questions = list(ai.get("need_student_confirm") or [])
    if any("2m" in str(item) or "2~2.5" in str(item) or "停车位置" in str(item) for item in raw_questions):
        questions.append("请确认本次自评是否包含“停车位置距人行道 2～2.5 米”的检查。")
    if any("record_duration_sec" in str(item) or "remaining_to_end_m" in str(item) for item in raw_questions):
        questions.append("请确认本次录制是否成功保存了完整时长和距终点数据。")
    if remaining is None:
        questions.append("当前报告没有计算出距终点距离，需要检查场景终点配置或定位数据。")

    return {
        "version": 1,
        "headline": headline,
        "summary": summary,
        "severity": severity,
        "badges": [
            {"label": "场景门槛", "value": "PASS" if gate_pass else "FAIL", "severity": "success" if gate_pass else "error"},
            {"label": "场景指标", "value": passed, "severity": "success" if gate_pass else "error"},
            {"label": "综合自评", "value": f"{_fmt(overall)}/100" if overall is not None else "—", "severity": "warning"},
            {"label": "是否官方", "value": "否", "severity": "neutral"},
        ],
        "findings": findings,
        "actions": actions,
        "questions": questions[:5],
        "references": (ai.get("source_refs") or [])[:8],
        "glossary": [{"term": key, "label": value[0], "meaning": value[1], "unit": value[2], "reference": value[3]} for key, value in GLOSSARY.items()],
        "generated_from": meta.get("experiment_id", ""),
    }