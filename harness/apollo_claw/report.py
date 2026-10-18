"""Report contract, sanitisation and Markdown export."""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

REQUIRED_SECTIONS = ("meta", "environment", "record", "metrics", "ai", "verification", "evidence", "capability")


def _sanitize_string(value: str, root: Path, home: Path) -> str:
    text = value
    root_str = str(root)
    home_str = str(home)
    if root_str and root_str in text:
        text = text.replace(root_str + "/", "").replace(root_str + "\\", "")
        text = text.replace(root_str, ".")
    if home_str and home_str in text:
        text = text.replace(home_str, "~")
    text = text.replace("\\", "/")
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<redacted-api-key>", text)
    text = re.sub(r"(?i)(DEEPSEEK_API_KEY\s*=\s*)\S+", r"\1<redacted>", text)
    return text


def sanitize_value(value: Any, root: Path, home: Path) -> Any:
    if isinstance(value, str):
        return _sanitize_string(value, root, home)
    if isinstance(value, list):
        return [sanitize_value(item, root, home) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_value(item, root, home) for key, item in value.items()}
    return value


def build_report(experiment: Dict[str, Any], experiment_dir: Path, home: Path | None = None) -> Dict[str, Any]:
    report = copy.deepcopy(experiment)
    report.setdefault("meta", {})
    report.setdefault("environment", {})
    report.setdefault("record", {})
    report.setdefault("metrics", {})
    report.setdefault("score", {"source": "not-run", "value": None, "is_official": False})
    report.setdefault("ai", {})
    report.setdefault("verification", {})
    report.setdefault("evidence", [])
    report.setdefault("capability", {})
    report.setdefault("commands", [])
    report.setdefault("errors", [])
    report["meta"]["source"] = report["meta"].get("source", "local-harness")
    report["meta"]["mode"] = report["meta"].get("mode", "real")
    # Keep command summaries, not raw output; raw output remains in the experiment folder.
    compact_commands = []
    for item in report.get("commands", []):
        result = item.get("result", {}) if isinstance(item, dict) else {}
        compact_commands.append({
            "purpose": item.get("purpose", ""),
            "argv": item.get("argv", []),
            "ok": result.get("ok", False),
            "returncode": result.get("returncode", None),
            "mode": result.get("mode", ""),
            "duration_sec": result.get("duration_sec", None),
        })
    report["commands"] = compact_commands
    sanitized = sanitize_value(report, experiment_dir, home or Path.home())
    sanitized["meta"]["experiment_id"] = sanitized["meta"].get("experiment_id", "")
    sanitized["meta"]["task"] = sanitized["meta"].get("task", "")
    sanitized["meta"]["scenario"] = sanitized["meta"].get("scenario", sanitized["meta"]["task"])
    return sanitized


def validate_report(report: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in report:
            errors.append(f"missing section: {section}")
    meta = report.get("meta", {})
    for key in ("experiment_id", "task", "created_at", "source", "mode"):
        if not meta.get(key):
            errors.append(f"missing meta.{key}")
    if report.get("meta", {}).get("mode") not in {"planned", "real", "demo", "replay"}:
        errors.append("meta.mode must be planned, real, demo or replay")
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        errors.append("metrics must be an object")
    else:
        for key, value in metrics.items():
            if value is not None and not isinstance(value, (int, float)):
                errors.append(f"metrics.{key} must be number or null")
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                errors.append(f"metrics.{key} is not finite")
    score = report.get("score", {})
    if not isinstance(score, dict):
        errors.append("score must be an object")
    elif score.get("is_official") not in (True, False):
        errors.append("score.is_official must be boolean")
    evidence = report.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence must be an array")
    else:
        for item in evidence:
            if not isinstance(item, dict) or not item.get("type") or not item.get("path"):
                errors.append("each evidence item needs type and path")
    blob = json.dumps(report, ensure_ascii=False)
    if re.search(r"sk-[A-Za-z0-9_-]{8,}", blob):
        errors.append("report contains an API-key-like secret")
    return errors


def to_markdown(report: Dict[str, Any]) -> str:
    meta = report.get("meta", {})
    environment = report.get("environment", {})
    record = report.get("record", {})
    metrics = report.get("metrics", {})
    score = report.get("score", {})
    ai = report.get("ai", {})
    verification = report.get("verification", {})
    capability = report.get("capability", {})
    lines = [
        "# Apollo Claw 实验报告",
        "",
        f"- 实验编号：{meta.get('experiment_id', '-')}",
        f"- 实验任务：{meta.get('scenario', meta.get('task', '-'))}",
        f"- 数据来源：{meta.get('source', '-')}",
        f"- 数据模式：{meta.get('mode', '-')}",
        f"- 当前状态：{meta.get('status', '-')}",
        "",
        "## 环境",
        "",
        "```json",
        json.dumps(environment, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 数据包",
        "",
        "```json",
        json.dumps(record, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 关键指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
    ]
    for key, value in metrics.items():
        lines.append(f"| {key} | {value if value is not None else '-'} |")
    lines.extend([
        "",
        "## 场景评分",
        "",
        f"- 来源：{score.get('source', 'not-run')}",
        f"- 分数：{score.get('value') if score.get('value') is not None else '-'}",
        f"- 是否官方评分：{score.get('is_official', False)}",
        f"- 通过项：{score.get('passed_metrics', '-')}",
    ])
    metric_rows = score.get("metrics") or []
    if metric_rows:
        lines.extend([
            "",
            "| 场景指标 | 结果 | 未通过帧 |",
            "| --- | --- | ---: |",
        ])
        for item in metric_rows:
            verdict = "PASS" if item.get("pass") else "FAIL"
            lines.append(f"| {item.get('name')} | {verdict} | {item.get('fail')}/{item.get('total')} |")
    lines.extend([
        "",
        "## AI 辅助结论",
        "",
    ])
    for key, title in (("facts", "事实"), ("hypotheses", "推测"), ("suggestions", "建议"), ("source_refs", "引用")):
        values = ai.get(key) or []
        lines.append(f"### {title}")
        lines.extend(f"- {value}" for value in values)
        if not values:
            lines.append("- 暂无")
        lines.append("")
    lines.extend(["## 优化前后验证", ""])
    if verification:
        for key, value in verification.items():
            lines.append(f"- {key}：{value}")
    else:
        lines.append("- 暂无验证数据")
    lines.extend(["", "## 能力画像", ""])
    if capability:
        for key, value in capability.items():
            lines.append(f"- {key}：{value}")
    else:
        lines.append("- 暂无能力画像数据")
    lines.extend(["", "## 证据", ""])
    for item in report.get("evidence", []):
        lines.append(f"- `{item.get('type', 'file')}`：{item.get('summary', '')} ({item.get('path', '')})")
    if not report.get("evidence"):
        lines.append("- 暂无证据文件")
    errors = report.get("errors", [])
    lines.extend(["", "## 错误与阻塞", ""])
    if errors:
        for item in errors:
            lines.append(f"- [{item.get('source', '?')}] {item.get('message', '')}")
    else:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def export_report(report: Dict[str, Any], out_dir: Path) -> Tuple[Path, Path]:
    errors = validate_report(report)
    if errors:
        raise ValueError("invalid report: " + "; ".join(errors))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path
