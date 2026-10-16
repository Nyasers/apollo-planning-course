"""Report export helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def to_markdown(report: Dict[str, Any]) -> str:
    meta = report.get("meta", {})
    metrics = report.get("metrics", {})
    verification = report.get("verification", {})
    ai = report.get("ai", {})
    lines = [
        "# Apollo Claw 实验报告",
        "",
        f"- 实验编号：{meta.get('experiment_id', '-')}",
        f"- 实验任务：{meta.get('scenario', meta.get('task', '-'))}",
        f"- 数据来源：{meta.get('source', '-')}",
        "",
        "## 关键指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 最低 TTC | {metrics.get('min_ttc', '-')} |",
        f"| 最大 Jerk | {metrics.get('max_jerk', '-')} |",
        f"| 急刹次数 | {metrics.get('hard_brake', '-')} |",
        f"| 碰撞 | {metrics.get('collision', '-')} |",
        f"| 到达终点 | {metrics.get('reach_end', '-')} |",
        "",
        "## AI 辅助结论",
        "",
    ]
    for key, title in [("facts", "事实"), ("hypotheses", "推测"), ("suggestions", "建议")]:
        lines.append(f"### {title}")
        values = ai.get(key) or []
        if values:
            lines.extend(f"- {v}" for v in values)
        else:
            lines.append("- 暂无")
        lines.append("")
    lines.extend([
        "## 优化前后验证",
        "",
        f"- TTC：{metrics.get('min_ttc', '-')} → {verification.get('min_ttc', '-')}",
        f"- Jerk：{metrics.get('max_jerk', '-')} → {verification.get('max_jerk', '-')}",
        f"- 急刹：{metrics.get('hard_brake', '-')} → {verification.get('hard_brake', '-')}",
        "",
        "## 证据",
        "",
    ])
    for item in report.get("evidence", []):
        lines.append(f"- `{item.get('type', 'file')}`：{item.get('summary', '')} ({item.get('path', '')})")
    lines.append("")
    return "\n".join(lines)


def export_report(report: Dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    from .evidence import write_json
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    write_json(json_path, report)
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path
