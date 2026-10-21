"""Build a website-ready integrated lab report from one or two harness reports."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA = "apollo-claw.lab-report.v1"


def _metrics(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        item.get("name"): item
        for item in (report.get("score", {}) or {}).get("metrics", []) or []
        if isinstance(item, dict) and item.get("name")
    }


def _number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pass_text(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "—"


def _trend(before: Any, after: Any) -> str:
    b = _pass_text(before)
    a = _pass_text(after)
    if b == a:
        return "unchanged"
    if b == "FAIL" and a == "PASS":
        return "improved"
    if b == "PASS" and a == "FAIL":
        return "regressed"
    return "changed"


def _metric_comparison(before: Dict[str, Any], after: Dict[str, Any], name: str) -> Dict[str, Any]:
    b = _number(before.get("fail"))
    a = _number(after.get("fail"))
    return {
        "id": name.lower(),
        "label": name,
        "before": _pass_text(before.get("pass")),
        "after": _pass_text(after.get("pass")),
        "before_detail": f"{before.get('fail', '—')}/{before.get('total', '—')}",
        "after_detail": f"{after.get('fail', '—')}/{after.get('total', '—')}",
        "status": _trend(before.get("pass"), after.get("pass")),
        "before_score": before.get("score"),
        "after_score": after.get("score"),
    }


def _summary(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not report:
        return {}
    score = report.get("score", {}) or {}
    metrics = report.get("metrics", {}) or {}
    return {
        "experiment_id": (report.get("meta", {}) or {}).get("experiment_id", ""),
        "created_at": (report.get("meta", {}) or {}).get("created_at", ""),
        "status": (report.get("meta", {}) or {}).get("status", ""),
        "passed_metrics": score.get("passed_metrics", "—"),
        "scenario_pass": score.get("scenario_pass"),
        "score_value": score.get("value"),
        "performance_score": score.get("performance_score"),
        "comfort_score": score.get("comfort_score"),
        "gate_status": score.get("gate_status"),
        "metrics": metrics,
        "failing": [
            item.get("name")
            for item in score.get("metrics", []) or []
            if isinstance(item, dict) and item.get("pass") is False
        ],
    }


def _dedupe_evidence(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "file"))
        path = str(item.get("path", ""))
        # Prefer the real record filename over the base-name entry.
        key = (kind, path.rsplit("/", 1)[-1])
        if kind == "record":
            # Keep only the latest record entry (usually the real *.record.* file).
            result = [old for old in result if old.get("type") != "record"]
            result.append(copy.deepcopy(item))
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(copy.deepcopy(item))
    return result


def build_lab_report(current: Dict[str, Any], baseline: Optional[Dict[str, Any]] = None, review_note: str = "") -> Dict[str, Any]:
    report = copy.deepcopy(current)
    report.pop("commands", None)
    report["evidence"] = _dedupe_evidence(report.get("evidence", []))
    report.setdefault("meta", {})
    report.setdefault("environment", {})
    report.setdefault("record", {})
    report.setdefault("metrics", {})
    report.setdefault("ai", {})
    report.setdefault("score", {"source": "apollo-claw-selfeval", "value": None, "is_official": False})
    report.setdefault("verification", {})
    report.setdefault("evidence", [])
    report.setdefault("capability", {})

    # A failed TTC frame is not a 100-point result; normalize the web contract.
    for metric in report.get("score", {}).get("metrics", []) or []:
        if isinstance(metric, dict) and metric.get("name") == "TTC" and metric.get("pass") is False and metric.get("score") == 100:
            metric["score"] = None

    after_metrics = _metrics(report)
    before_metrics = _metrics(baseline or {})
    current_summary = _summary(report)
    baseline_summary = _summary(baseline)

    comparison = []
    if baseline:
        for name in ["ReachEnd", "TTC", "AccelerationLimit", "HardBrake", "Collision", "SpeedLimit"]:
            if name in before_metrics or name in after_metrics:
                comparison.append(_metric_comparison(before_metrics.get(name, {}), after_metrics.get(name, {}), name))

        b_jerk = _number((baseline.get("metrics", {}) or {}).get("max_jerk"))
        a_jerk = _number((report.get("metrics", {}) or {}).get("max_jerk"))
        comparison.append({
            "id": "jerk",
            "label": "最大 Jerk（m/s³）",
            "before": "—" if b_jerk is None else b_jerk,
            "after": "—" if a_jerk is None else a_jerk,
            "before_detail": "越低越好",
            "after_detail": "越低越好",
            "status": "improved" if b_jerk is not None and a_jerk is not None and a_jerk < b_jerk else "unchanged",
        })

    warnings = []
    if not report.get("environment"):
        warnings.append("当前报告没有绑定环境检查数据（doctor.json）；请确认 doctor 使用了同一个 experiment。")
    failing = current_summary.get("failing", [])
    if "TTC" in failing:
        warnings.append("TTC 仍未通过，不能把本轮写成完全通过；请回放失败时间窗并确认目标对象。")
    if "AccelerationLimit" in failing:
        warnings.append("AccelerationLimit 存在失败帧；需要确认是真实加速度还是时间戳跳变造成的差分假峰。")
    if baseline_summary.get("scenario_pass") is False and current_summary.get("scenario_pass") is False:
        warnings.append("baseline 与本轮都未完全通过；当前报告应定位为“真实优化验证/未完成”，不是最终成功案例。")

    next_actions = []
    if "TTC" in failing:
        next_actions.append("检查 TTC 失败区间、目标对象和实际减速时点；若为行人冲突，提前减速并保持安全 TTC。")
    if "AccelerationLimit" in failing:
        next_actions.append("检查 chassis 速度序列和评分器的小时间差处理，区分真实加速度与数据跳变。")
    if not report.get("environment"):
        next_actions.append("对同一实验运行 doctor --experiment，并重新执行 report bundle。")
    if not next_actions:
        next_actions.append("保留本轮报告，继续扩展场景或进行教师复核。")

    score_value = current_summary.get("score_value")
    headline = (
        f"本轮真实自评：通过 {current_summary.get('passed_metrics', '—')} 项。"
        + (f"综合自评 {score_value}/100（非官方）。" if score_value is not None else "")
        + ("已到达终点。" if (after_metrics.get("ReachEnd", {}) or {}).get("pass") is True else "")
    )
    lab = {
        "schema": SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "badge": "真实本地自评",
        "is_official": False,
        "headline": headline,
        "summary": "本报告由 Apollo Claw Harness 生成，评分与判定来自脚本，AI 只解释证据，不替代教师或官方评测。",
        "current": current_summary,
        "baseline": baseline_summary,
        "comparison": comparison,
        "warnings": warnings,
        "next_actions": next_actions,
        "human_review": [review_note] if review_note else [],
        "files": {
            "report_json": "report.json",
            "report_md": "report.md",
            "selfeval_md": "selfeval.md",
            "doctor_json": "doctor.json",
            "channel_summary": "channel_summary.csv",
            "record_report": "record_report.md",
            "plots": "plots/",
        },
    }
    report["lab"] = lab
    return report


def to_markdown(report: Dict[str, Any]) -> str:
    lab = report.get("lab", {}) or {}
    current = lab.get("current", {}) or {}
    baseline = lab.get("baseline", {}) or {}
    lines = [
        f"# {lab.get('headline', 'Apollo Claw 实验报告')}",
        "",
        f"> {lab.get('summary', '')}",
        "",
        f"- 报告模式：{lab.get('badge', '真实本地自评')}",
        f"- 本轮实验：`{current.get('experiment_id', '—')}`",
        f"- 通过指标：{current.get('passed_metrics', '—')}",
    ]
    if baseline:
        lines.append(f"- Baseline：`{baseline.get('experiment_id', '—')}`（{baseline.get('passed_metrics', '—')}）")
    lines.extend(["", "## 基线与本轮对比", ""])
    rows = lab.get("comparison", []) or []
    if rows:
        lines.extend(["| 指标 | Baseline | 本轮 | 结果 |", "| --- | --- | --- | --- |"])
        for row in rows:
            label = row.get("label", "—")
            before = row.get("before", "—")
            after = row.get("after", "—")
            detail = row.get("after_detail", "")
            lines.append(f"| {label} | {before} {row.get('before_detail', '')} | {after} {detail} | {row.get('status', '—')} |")
    else:
        lines.append("- 暂无 baseline 对比数据。")
    if lab.get("human_review"):
        lines.extend(["", "## 人工核验", ""])
        for note in lab.get("human_review", []):
            lines.append(f"- {note}")
    lines.extend(["", "## 需要关注", ""])
    for warning in lab.get("warnings", []) or []:
        lines.append(f"- {warning}")
    if not lab.get("warnings"):
        lines.append("- 无")
    lines.extend(["", "## 下一步", ""])
    for action in lab.get("next_actions", []) or []:
        lines.append(f"- {action}")
    lines.extend(["", "## 文件", ""])
    for key, value in (lab.get("files", {}) or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "> 本地自评估不等于官方评分。"])
    return "\n".join(lines) + "\n"


def export_lab_report(report: Dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab-report.json"
    md_path = out_dir / "lab-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path
