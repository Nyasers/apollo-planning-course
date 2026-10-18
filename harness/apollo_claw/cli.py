"""CLI entry point for Apollo Claw Harness."""
from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .config import Settings
from .deepseek import DeepSeekUnavailable, explain, fallback_explain
from .evidence import read_json, write_json
from .experiment import ExperimentStore
from .knowledge import search as search_knowledge
from .report import build_report, export_report, validate_report
from .router import route
from .runner import CommandResult, docker_exec, run_host, save_command_output
from .skills import resolve_skills


def _which(name: str) -> str:
    return shutil.which(name) or ""


def _host_probe(argv):
    try:
        result = run_host(argv, timeout=20)
        return {"ok": result.ok, "returncode": result.returncode, "stdout": result.stdout.strip()[:2000], "stderr": result.stderr.strip()[:1000]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _store(settings: Settings) -> ExperimentStore:
    return ExperimentStore(Path(settings.output_dir))


def _get_or_create_experiment(settings: Settings, args) -> Dict[str, Any]:
    store = _store(settings)
    experiment_id = getattr(args, "experiment", None)
    if experiment_id:
        return store.load(experiment_id)
    scenario = getattr(args, "scenario_name", None) or getattr(args, "scenario", "人行道避让")
    return store.create(getattr(args, "task", "crosswalk"), scenario)


def _save_command(settings: Settings, experiment: Dict[str, Any], purpose: str, argv: list[str], result: CommandResult, add_error_on_failure: bool = True) -> None:
    store = _store(settings)
    directory = store.experiment_dir(experiment["meta"]["experiment_id"]) / "commands"
    save_command_output(result, directory, purpose)
    store.add_command(experiment, purpose, argv, result.to_dict())
    if add_error_on_failure and not result.ok:
        store.add_error(experiment, purpose, "command failed", result.stderr)
    store.save(experiment)


def _host_to_container(settings: Settings, path: str) -> str:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        return path
    candidate = candidate.resolve()
    host_root = Path(settings.apollo_workspace_host).expanduser().resolve()
    try:
        return settings.apollo_workspace_container + "/" + str(candidate.relative_to(host_root)).replace("\\", "/")
    except ValueError:
        pass
    skills_root = Path(settings.skills_dir).expanduser().resolve()
    try:
        return settings.skills_container_dir + "/" + str(candidate.relative_to(skills_root)).replace("\\", "/")
    except ValueError:
        return path


def _container_to_host(settings: Settings, path: str) -> Path:
    text = str(path)
    prefix = settings.apollo_workspace_container.rstrip("/") + "/"
    if text.startswith(prefix):
        return Path(settings.apollo_workspace_host).expanduser() / text[len(prefix):]
    return Path(text).expanduser()


def _record_artifacts(settings: Settings, record_path: str):
    host_path = _container_to_host(settings, record_path)
    parent = host_path.parent
    pattern = host_path.name + "*"
    files = sorted(parent.glob(pattern)) if parent.exists() else []
    files = [path for path in files if path.is_file()]
    return files, sum(path.stat().st_size for path in files)


def _parse_record_report(settings: Settings, output: str) -> Dict[str, Optional[int]]:
    report_dir = _container_to_host(settings, output)
    report_md = report_dir / "record_report.md"
    result = {"channel_count": None, "message_count": None}
    if not report_md.exists():
        return result
    text = report_md.read_text(encoding="utf-8", errors="ignore")
    for key, pattern in (("channel_count", r"Total channels:\s*(\d+)"), ("message_count", r"Total indexed messages:\s*(\d+)")):
        import re
        match = re.search(pattern, text)
        if match:
            result[key] = int(match.group(1))
    return result


def _dreamview_check(settings: Settings) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(settings.dreamview_url, timeout=settings.dreamview_timeout) as response:
            return {"ok": 200 <= response.status < 400, "status": response.status, "url": settings.dreamview_url}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": settings.dreamview_url}


def cmd_doctor(settings: Settings, args) -> int:
    store = _store(settings)
    experiment = _get_or_create_experiment(settings, args)
    workspace = Path(settings.apollo_workspace_host).expanduser()
    disk = shutil.disk_usage(workspace if workspace.exists() else Path.home())
    data: Dict[str, Any] = {
        "meta": {"version": __version__, "skill": "apollo-env", "checked_at": experiment["meta"]["updated_at"]},
        "host": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(Path.cwd()),
            "docker": _which("docker"),
            "aem": _which("aem"),
            "workspace": str(workspace),
            "workspace_exists": workspace.exists(),
            "disk_free_gb": round(disk.free / (1024 ** 3), 1),
        },
        "checks": {
            "docker_version": _host_probe(["docker", "--version"]),
            "docker_info": _host_probe(["docker", "info", "--format", "{{.ServerVersion}}"]),
            "aem_version": _host_probe(["aem", "version"]),
        },
        "dreamview": _dreamview_check(settings),
        "skills": {
            "root": str(resolve_skills(settings).root) if resolve_skills(settings).root else "",
            "missing": resolve_skills(settings).missing(),
        },
    }
    try:
        ps = run_host(["docker", "ps", "--format", "{{.Names}}"], timeout=20)
        names = [name for name in ps.stdout.splitlines() if name.strip()]
        data["apollo"] = {"containers": names, "container_running": settings.apollo_container_name in names}
    except Exception as exc:
        data["apollo"] = {"containers": [], "container_running": False, "error": str(exc)}
    directory = store.experiment_dir(experiment["meta"]["experiment_id"])
    out = Path(args.output).expanduser() if getattr(args, "output", None) else directory / "doctor.json"
    write_json(out, data)
    store.set_section(experiment, "environment", data.get("host", {}))
    store.add_evidence(experiment, "doctor", str(out), "环境检查 JSON")
    # 环境检查只描述起点，不能把已经录到数据的实验状态改回去
    if experiment["meta"].get("status") in (None, "created", "environment_checked", "environment_warning"):
        experiment["meta"]["status"] = "environment_checked" if data.get("apollo", {}).get("container_running") else "environment_warning"
    store.save(experiment)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("Apollo Claw doctor")
        print(f"experiment: {experiment['meta']['experiment_id']}")
        print(f"workspace: {data['host']['workspace']} ({data['host']['workspace_exists']})")
        print(f"docker: {data['host']['docker'] or 'not found'}")
        print(f"aem: {data['host']['aem'] or 'not found'}")
        print(f"Apollo container running: {data['apollo']['container_running']}")
        print(f"saved: {out}")
    return 0


def _load_evidence(path: Optional[str]):
    if path:
        return read_json(Path(path).expanduser())
    return {"meta": {"task": "unknown"}, "metrics": {}, "evidence": []}


def cmd_explain(settings: Settings, args) -> int:
    experiment = _get_or_create_experiment(settings, args) if getattr(args, "experiment", None) else None
    evidence = dict(experiment) if experiment else _load_evidence(args.evidence)
    if args.log:
        log_path = Path(args.log).expanduser()
        text = log_path.read_text(encoding="utf-8", errors="ignore")[-12000:]
        evidence.setdefault("logs", []).append({"path": str(log_path), "excerpt": text})
    skills = resolve_skills(settings)
    if skills.dev_knowledge:
        query = " ".join([args.question or "", args.log or "", args.evidence or ""])
        snippets = search_knowledge(skills.dev_knowledge, query or "Planning 调试", limit=4)
        if snippets:
            evidence["knowledge"] = [
                {"path": str(path), "excerpt": excerpt}
                for path, excerpt in snippets
            ]
    skill = route(" ".join([args.question or "", args.log or "", args.evidence or ""]))
    try:
        result = explain(settings, evidence, args.question or "")
        mode = "deepseek"
    except DeepSeekUnavailable as exc:
        result = fallback_explain(evidence)
        result["note"] = f"DeepSeek 不可用，已进入规则降级模式：{exc}"
        mode = "fallback"
    result["skill"] = skill
    result["mode"] = mode
    if experiment:
        store = _store(settings)
        experiment["ai"] = result
        for key in ("knowledge", "logs"):
            if evidence.get(key):
                experiment[key] = evidence[key]
        store.save(experiment)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_report_export(settings: Settings, args) -> int:
    store = _store(settings)
    if getattr(args, "experiment", None):
        experiment = store.load(args.experiment)
        experiment_dir = store.experiment_dir(args.experiment)
    elif getattr(args, "evidence", None):
        experiment = _load_evidence(args.evidence)
        experiment_dir = Path(args.evidence).expanduser().resolve().parent
    else:
        experiment = store.latest()
        if not experiment:
            print("没有实验可导出，请先运行 doctor 或传入 --evidence/--experiment", file=sys.stderr)
            return 2
        experiment_dir = store.experiment_dir(experiment["meta"]["experiment_id"])
    report = build_report(experiment, experiment_dir)
    errors = validate_report(report)
    if errors:
        print("报告契约校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    out_dir = Path(args.output_dir).expanduser() if getattr(args, "output_dir", None) else experiment_dir
    json_path, md_path = export_report(report, out_dir)
    print(f"report.json: {json_path}")
    print(f"report.md: {md_path}")
    return 0


def cmd_test_record(settings: Settings, args) -> int:
    experiment = _get_or_create_experiment(settings, args)
    tag = args.tag or experiment["meta"]["task"]
    record_dir = f"{settings.record_root_container}/{experiment['meta']['experiment_id']}"
    record_path = f"{record_dir}/{tag}.record"
    channels = [
        "/apollo/planning", "/apollo/control", "/apollo/localization/pose",
        "/apollo/canbus/chassis", "/apollo/perception/obstacles", "/apollo/prediction",
    ]
    argv = ["timeout", str(args.seconds), "cyber_recorder", "record", "-o", record_path]
    for channel in channels:
        argv.extend(["-c", channel])
    print(" ".join(argv))
    store = _store(settings)
    directory = store.experiment_dir(experiment["meta"]["experiment_id"])
    store.set_section(experiment, "record", {
        "path": record_path,
        "profile": args.profile,
        "duration_sec": args.seconds,
        "channels_requested": channels,
        "channel_count": None,
        "status": "dry-run" if not args.execute else "running",
    })
    if not args.execute:
        store.save(experiment)
        print("dry-run: add --execute to record inside the Apollo container")
        return 0
    experiment["meta"]["mode"] = "real"
    mkdir_argv = ["mkdir", "-p", record_dir]
    mkdir_result = docker_exec(settings, mkdir_argv, timeout=30)
    _save_command(settings, experiment, "test-record-mkdir", mkdir_argv, mkdir_result)
    if not mkdir_result.ok:
        experiment["meta"]["status"] = "record_failed"
        experiment["record"]["status"] = "failed"
        store.save(experiment)
        print(mkdir_result.stderr, file=sys.stderr)
        return mkdir_result.returncode
    result = docker_exec(settings, argv, timeout=args.seconds + 30)
    _save_command(settings, experiment, "test-record", argv, result, add_error_on_failure=False)
    files, total_bytes = _record_artifacts(settings, record_path)
    has_record = bool(files) and total_bytes > 0
    experiment["record"]["status"] = "recorded" if has_record else "failed"
    # cyber_recorder 会生成 <name>.00000.<timestamp>，基名文件并不存在，记录真实文件名
    experiment["record"]["path"] = f"{record_dir}/{files[0].name}" if files else record_path
    experiment["record"]["file_count"] = len(files)
    experiment["record"]["size_bytes"] = total_bytes
    experiment["record"]["stop_reason"] = "timeout" if result.returncode == 124 else "command_exit"
    evidence_path = experiment["record"]["path"] if has_record else record_path
    store.add_evidence(experiment, "record", evidence_path, f"{args.seconds} 秒，6 个核心 channel 请求")
    experiment["meta"]["status"] = "recorded" if has_record else "record_failed"
    if not has_record:
        store.add_error(experiment, "test-record", "record file was not created or is empty", result.stderr)
    store.save(experiment)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0 if has_record else result.returncode


def _resolve_container_script(settings: Settings, script: Optional[str], skill_script: Optional[Path]) -> Optional[str]:
    if script:
        return _host_to_container(settings, script)
    if skill_script and skill_script.exists():
        return _host_to_container(settings, str(skill_script))
    return None


def cmd_test_report(settings: Settings, args) -> int:
    experiment = _get_or_create_experiment(settings, args)
    skills = resolve_skills(settings)
    script = _resolve_container_script(settings, getattr(args, "script", None), skills.test_report_script)
    if not script:
        print("需要指定 --script，或把 apollo-test 放到 APOLLO_CLAW_SKILLS_DIR", file=sys.stderr)
        return 2
    record = _host_to_container(settings, args.record)
    # 允许传入 *.record 基名：cyber_recorder 产出的其实是 <name>.00000.<timestamp>
    if record.rstrip("/").endswith(".record"):
        record = record.rstrip("/").rsplit("/", 1)[0]
    output = args.output or f"{settings.record_root_container}/report/{experiment['meta']['experiment_id']}"
    argv = ["python3", script, record, "-o", output]
    print(" ".join(argv))
    if not args.execute:
        print("dry-run: add --execute to run inside the Apollo container")
        return 0
    experiment["meta"]["mode"] = "real"
    result = docker_exec(settings, argv, timeout=args.timeout, env={"MPLCONFIGDIR": "/tmp/matplotlib", "PYTHONPATH": "/opt/apollo/neo/python"})
    _save_command(settings, experiment, "test-report", argv, result)
    experiment["record"]["report_path"] = output
    summary = _parse_record_report(settings, output)
    experiment["record"]["channel_count"] = summary["channel_count"]
    experiment["record"]["message_count"] = summary["message_count"]
    store = _store(settings)
    store.add_evidence(experiment, "channel_report", output, "channel_summary.csv / record_report.md / plots")
    if result.ok and summary.get("channel_count") == 0:
        experiment["record"]["status"] = "empty"
        experiment["meta"]["status"] = "empty_record"
        store.add_error(experiment, "record", "record contains 0 channels; start a simulation scenario and record again", "")
    else:
        experiment["record"]["status"] = "reported" if result.ok else "report_failed"
        experiment["meta"]["status"] = "reported" if result.ok else "report_failed"
    store.save(experiment)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0 if result.ok else result.returncode


def cmd_eval(settings: Settings, args) -> int:
    experiment = _get_or_create_experiment(settings, args)
    skills = resolve_skills(settings)

    if getattr(args, "comfort", False):
        # 体感评估（apollo-eval/scripts/extract_metrics.py）：只需要一个 record
        script = _resolve_container_script(settings, getattr(args, "script", None), skills.eval_metrics_script)
        if not script:
            print("需要 apollo-eval/scripts/extract_metrics.py，或显式传 --script", file=sys.stderr)
            return 2
        bag = _host_to_container(settings, args.bag) if getattr(args, "bag", None) else experiment.get("record", {}).get("path", "")
        if not bag:
            print("体感评估需要 --bag，或当前实验里已有 record 路径。", file=sys.stderr)
            return 2
        argv = ["python3", script, bag]
        if getattr(args, "interval", None):
            argv.extend(["--interval", str(args.interval)])
        print(" ".join(argv))
        if not args.execute:
            print("dry-run: add --execute to run inside the Apollo container")
            return 0
        experiment["meta"]["mode"] = "real"
        result = docker_exec(settings, argv, timeout=args.timeout)
        _save_command(settings, experiment, "eval-comfort", argv, result)
        experiment.setdefault("score", {})["source"] = "apollo-eval-comfort"
        experiment["score"]["is_official"] = False
        experiment["meta"]["status"] = "evaluated" if result.ok else "eval_failed"
        _store(settings).save(experiment)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return 0 if result.ok else result.returncode

    script = _resolve_container_script(settings, getattr(args, "script", None), skills.eval_grading_script)
    if not script:
        print("需要指定 --script，或把 apollo-eval 放到 APOLLO_CLAW_SKILLS_DIR", file=sys.stderr)
        return 2
    metric = _host_to_container(settings, args.metric) if getattr(args, "metric", None) else ""
    if not metric:
        print(
            "eval 需要 --metric 指向评分配置（grading_metrics*.conf 或同名 JSON）。\n"
            "该文件定义考哪些指标、阈值和扣分方式，缺失时无法评分。",
            file=sys.stderr,
        )
        return 2
    scenario = _host_to_container(settings, args.scenario) if getattr(args, "scenario", None) else ""
    bag = _host_to_container(settings, args.bag) if getattr(args, "bag", None) else experiment.get("record", {}).get("path", "")
    if not bag:
        print("eval 需要 --bag，或当前实验里已有 record 路径。", file=sys.stderr)
        return 2
    argv = ["python3", script, "--config", metric, "--mode", "bag", "--bag_file", bag]
    if scenario:
        argv.extend(["--scenario", scenario])
    print(" ".join(argv))
    if not args.execute:
        print("dry-run: add --execute to run inside the Apollo container")
        return 0
    experiment["meta"]["mode"] = "real"
    result = docker_exec(settings, argv, timeout=args.timeout, env={"PYTHONPATH": "/opt/apollo/neo/python"})
    _save_command(settings, experiment, "eval", argv, result)
    experiment.setdefault("score", {})["source"] = "apollo-eval"
    experiment["score"]["is_official"] = False
    experiment["meta"]["status"] = "evaluated" if result.ok else "eval_failed"
    if not result.ok:
        _store(settings).add_error(experiment, "eval", "evaluation failed", result.stderr)
    _store(settings).save(experiment)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0 if result.ok else result.returncode


DEFAULT_METRIC_NAME = "metrics_selfeval.json"

SUGGESTION_RULES = {
    "ReachEnd": "没到终点：先确认 scenario 与本次运行是否为同一个场景，再看录制是否覆盖到结束；终点判定框为 8×8 m。",
    "TTC": "TTC 低于 3 s：提前减速，检查跟车距离和人行道/停止线前的减速提前量。",
    "SpeedLimit": "超速：检查 profiles/default 下的 speed_limit 配置与地图限速。",
    "AccelerationLimit": "纵向加速度越界：调小 max_acceleration / max_deceleration。",
    "HardBrake": "出现急刹：grep stop_reason，确认是障碍物、红灯还是插件误判。",
    "CentripetalAccelerationLimit": "过弯横向加速度偏大：降低转弯限速或加大曲率约束。",
    "Collision": "发生碰撞：检查 obstacle_avoid 安全距离与感知障碍物尺寸。",
    "TimeLimit": "场景超时：提升平均速度或减少绕行。",
    "OnRoad": "越出道路：检查地图车道宽度与横向控制参数。",
}


def _ensure_default_metric(settings: Settings) -> str:
    """把包内自评评分配置放到容器可见目录，返回容器路径。"""
    source = Path(__file__).resolve().parent / "defaults" / DEFAULT_METRIC_NAME
    if not source.exists():
        return ""
    target_dir = Path(settings.apollo_workspace_host).expanduser() / ".comate" / "metrics"
    target = target_dir / DEFAULT_METRIC_NAME
    try:
        if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    except OSError as exc:
        print(f"无法写入自评评分配置：{exc}", file=sys.stderr)
        return ""
    return _host_to_container(settings, str(target))


def _parse_grading_stdout(text: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"scenario_pass": None, "metrics": [], "events": {}}
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^Scenario:\s*(PASS|FAIL)$", line)
        if m:
            summary["scenario_pass"] = m.group(1) == "PASS"
            continue
        m = re.match(r"^(\w+)\s+(PASS|FAIL)\s+([\d.]+)\s+(\d+)/(\d+)$", line)
        if m:
            summary["metrics"].append({
                "name": m.group(1),
                "pass": m.group(2) == "PASS",
                "score": float(m.group(3)),
                "fail": int(m.group(4)),
                "total": int(m.group(5)),
            })
            continue
        m = re.match(r"^\[FAIL\]\s+t=([\d.]+)s\s+(\w+):\s*(.*)$", line)
        if m:
            summary["events"].setdefault(m.group(2), []).append((float(m.group(1)), m.group(3)))
    return summary


def _build_suggestions(grading: Dict[str, Any], comfort: Dict[str, Any], remaining: Optional[float] = None) -> list:
    tips = []
    for item in grading.get("metrics", []):
        if item["pass"]:
            continue
        tip = SUGGESTION_RULES.get(item["name"])
        if not tip:
            continue
        events = grading.get("events", {}).get(item["name"]) or []
        if item["name"] == "TTC" and events:
            start, end = events[0][0], events[-1][0]
            obj = ""
            m = re.search(r"TTC to (\S+) is", events[0][1])
            if m:
                obj = f"与对象 {m.group(1)} "
            tips.append(f"**TTC**（{item['fail']}/{item['total']} 帧，集中在 t={start:.1f}–{end:.1f}s）："
                        f"{obj}的 TTC 低于 3 s，先查这一段是不是在跟车/礼让，再看减速是否开始得太晚。")
        else:
            if item["name"] == "ReachEnd" and remaining is not None:
                tips.append(f"**ReachEnd**（{item['fail']}/{item['total']} 帧均未到达）：录制结束时距终点还有 {remaining:.1f} m，"
                            "把录制时长延长到车停下来为止（场景超时是 100 s，余量很足）。")
            else:
                tips.append(f"**{item['name']}**（{item['fail']}/{item['total']} 帧未通过）：{tip}")
    if (comfort.get("jerk_violation_count") or 0) > 0:
        peak_t = comfort.get("max_lon_jerk_time")
        phase = "起步阶段" if isinstance(peak_t, (int, float)) and peak_t < 5 else "行驶中"
        detail = f"最大 {comfort.get('max_lon_jerk', 0):.2f} m/s³"
        if isinstance(peak_t, (int, float)):
            detail += f"，出现在 {peak_t:.1f} s（{phase}）"
        if isinstance(comfort.get("jerk_p95"), (int, float)):
            detail += f"，P95 {comfort['jerk_p95']:.2f}"
        tips.append(f"**Jerk**（{detail}，超限 {comfort['jerk_violation_count']} 次）："
                    + ("起步段加速度跳变，检查起步时的加速度爬升率（不要一步给到目标加速度）。"
                       if phase == "起步阶段" else "全程抖动，增大 jerk_limit 约束，或提升速度规划平滑度。"))
    if (comfort.get("lon_accel_violation_count") or 0) > 0:
        tips.append(f"**纵向加速度**（最大 {comfort.get('max_lon_accel', 0):.2f} m/s²，超限 {comfort['lon_accel_violation_count']} 次）：降低加减速幅度。")
    if (comfort.get("lat_accel_violation_count") or 0) > 0:
        tips.append(f"**横向加速度**（最大 {comfort.get('max_lat_accel', 0):.2f} m/s²，超限 {comfort['lat_accel_violation_count']} 次）：降低过弯速度。")
    if (comfort.get("hard_brake_count") or 0) > 0:
        tips.append(f"**急刹**（{comfort['hard_brake_count']} 次）：确认触发原因，必要时提前减速。")
    if not tips:
        tips.append("本轮所有指标均未超限；想继续提升就把下一次运行的指标和这次做差对比。")
    return tips


SCENARIO_KEYWORDS = {
    "人行道": ["人行"],
    "交通灯": ["红绿灯", "交通灯"],
    "自主泊车": ["泊车"],
    "借道": ["借道"],
    "环岛": ["环岛"],
    "S弯": ["S弯"],
    "施工": ["施工"],
    "变道": ["变道"],
    "U形": ["U形"],
}


def _auto_match_scenario(settings: Settings, scenario_name: str) -> str:
    """根据场景名在本地场景集里找一个最像的 scenario.json，返回容器路径。"""
    root = Path.home() / ".apollo" / "resources" / "scenario_sets"
    if not root.exists():
        return ""
    keywords = []
    for key, words in SCENARIO_KEYWORDS.items():
        if key in scenario_name:
            keywords.extend(words)
    if not keywords:
        keywords = [scenario_name[:2]]
    for path in sorted(root.glob("*/scenarios/*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        blob = json.dumps(data.get("descriptionEnTokens", []) + data.get("tags", []), ensure_ascii=False)
        if any(word in blob for word in keywords):
            return _host_to_container(settings, str(path))
    return ""


def _scenario_end_point(scenario_path: str):
    """从 scenario.json 读终点坐标；读不到返回 None。"""
    if not scenario_path:
        return None
    for candidate in (Path(scenario_path), Path("/") / scenario_path.lstrip("/")):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        end = data.get("scenario", {}).get("autoCarInfo", {}).get("end") or {}
        if "x" in end and "y" in end:
            return float(end["x"]), float(end["y"])
    return None


def _remaining_distance(settings: Settings, experiment_id: str, end_point) -> Optional[float]:
    """用通道报告里的定位 CSV 算最后一帧到终点的直线距离。"""
    if not end_point:
        return None
    csv_path = _container_to_host(settings, f"{settings.record_root_container}/report/{experiment_id}") / "csv" / "apollo__localization__pose.csv"
    if not csv_path.exists():
        return None
    try:
        with csv_path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            return None
        last = rows[-1]
        return ((float(last["x"]) - end_point[0]) ** 2 + (float(last["y"]) - end_point[1]) ** 2) ** 0.5
    except (OSError, ValueError, KeyError):
        return None


def cmd_report_build(settings: Settings, args) -> int:
    """自评报告：场景指标 + 体感指标 + 改进建议，合并成一份 Markdown。"""
    experiment = _get_or_create_experiment(settings, args)
    skills = resolve_skills(settings)
    exp_id = experiment["meta"]["experiment_id"]
    record = experiment.get("record", {}).get("path", "")
    if not record:
        print("当前实验没有 record，先跑 test record 再生成报告。", file=sys.stderr)
        return 2
    if not experiment.get("environment"):
        print(
            "警告：当前实验没有 environment 检查数据，报告中的环境段会为空。"
            f"建议先运行 apollo-claw doctor --experiment {exp_id} --json。",
            file=sys.stderr,
        )

    metric = _host_to_container(settings, args.metric) if getattr(args, "metric", None) else _ensure_default_metric(settings)
    if not metric:
        print("找不到自评评分配置（apollo_claw/defaults/metrics_selfeval.json）。", file=sys.stderr)
        return 2
    scenario = _host_to_container(settings, args.scenario) if getattr(args, "scenario", None) else ""
    scenario_note = ""
    if not scenario:
        scenario = _auto_match_scenario(settings, experiment["meta"].get("scenario", ""))
        if scenario:
            scenario_note = f"自动匹配场景：{scenario}（如不对，用 --scenario 指定）"
            print(scenario_note)
    grading_script = _resolve_container_script(settings, None, skills.eval_grading_script)
    comfort_script = _resolve_container_script(settings, None, skills.eval_metrics_script)
    if not grading_script or not comfort_script:
        print("缺少 apollo-eval 脚本，先把技能放进工作区 .comate/skills。", file=sys.stderr)
        return 2

    comfort_json_container = f"{settings.record_root_container}/report/{exp_id}/comfort.json"
    grading_argv = ["python3", grading_script, "--config", metric, "--mode", "bag", "--bag_file", record]
    if scenario:
        grading_argv.extend(["--scenario", scenario])
    comfort_argv = ["python3", comfort_script, record, "--json", comfort_json_container]

    print(" ".join(grading_argv))
    print(" ".join(comfort_argv))
    if not args.execute:
        print("dry-run: add --execute to run inside the Apollo container")
        return 0

    eval_env = {"PYTHONPATH": "/opt/apollo/neo/python"}
    if skills.root:
        scripts_dir = _host_to_container(settings, str(skills.root)) + "/apollo-eval/scripts"
        eval_env["PYTHONPATH"] = "/opt/apollo/neo/python:" + scripts_dir

    grading = docker_exec(settings, grading_argv, timeout=args.timeout, env=eval_env)
    _save_command(settings, experiment, "selfeval-grading", grading_argv, grading)
    comfort = docker_exec(settings, comfort_argv, timeout=args.timeout, env=eval_env)
    _save_command(settings, experiment, "selfeval-comfort", comfort_argv, comfort)

    grading_summary = _parse_grading_stdout(grading.stdout)
    comfort_data: Dict[str, Any] = {}
    comfort_path = _container_to_host(settings, comfort_json_container)
    if comfort_path.exists():
        try:
            comfort_data = json.loads(comfort_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            comfort_data = {}

    experiment.setdefault("score", {})
    _metric_list = grading_summary.get("metrics", [])
    # TTC handler 不写扣分，失败时原始分数仍是 100；在统一报告中不要把失败项显示成满分。
    for metric in _metric_list:
        if isinstance(metric, dict) and metric.get("name") == "TTC" and metric.get("pass") is False and metric.get("score") == 100:
            metric["score"] = None
    _passed = sum(1 for m in _metric_list if m.get("pass"))
    experiment["score"].update({
        "source": "apollo-claw-selfeval",
        "value": None,
        "is_official": False,
        "scenario_pass": grading_summary.get("scenario_pass"),
        "passed_metrics": f"{_passed}/{len(_metric_list)}" if _metric_list else "-",
        "metrics": _metric_list,
    })
    experiment["metrics"] = {
        "max_lon_accel": comfort_data.get("max_lon_accel"),
        "max_jerk": comfort_data.get("max_lon_jerk"),
        "max_lat_accel": comfort_data.get("max_lat_accel"),
        "max_speed_mps": comfort_data.get("max_speed_ms"),
        "avg_speed_mps": comfort_data.get("avg_speed_ms"),
        "hard_brake": comfort_data.get("hard_brake_count"),
    }
    experiment["meta"]["status"] = "evaluated" if grading.ok else "eval_failed"
    if scenario:
        experiment["meta"]["scenario_file"] = scenario

    _store(settings).add_evidence(experiment, "record", record, "本轮被评分的 record")
    end_point = _scenario_end_point(scenario) if scenario else None
    remaining = _remaining_distance(settings, exp_id, end_point)
    if remaining is not None:
        experiment["metrics"]["remaining_to_end_m"] = round(remaining, 1)
    suggestions = _build_suggestions(grading_summary, comfort_data, remaining)
    # 本轮成功就不再保留同来源的旧失败记录，否则模型会把已修复的问题当成现报
    stale = set()
    if grading.ok:
        stale.update({"selfeval-grading", "eval"})
    if comfort.ok:
        stale.add("selfeval-comfort")
    if stale:
        experiment["errors"] = [e for e in (experiment.get("errors") or []) if e.get("source") not in stale]
    ai_evidence = _build_ai_evidence(settings, experiment, grading_summary, comfort_data, remaining)
    ai_result = _ai_analyze(settings, ai_evidence, experiment["meta"].get("scenario", ""))
    experiment["ai"] = ai_result
    report_path = _write_selfeval_report(settings, experiment, grading_summary, comfort_data, suggestions, remaining, ai_result)
    _store(settings).add_evidence(experiment, "selfeval_report", str(report_path), "自评报告（评分 + 体感 + 建议）")
    _store(settings).save(experiment)

    # 自评完成后同步刷新统一报告，避免 report.json 停在旧状态
    report = build_report(experiment, _store(settings).experiment_dir(exp_id))
    errors = validate_report(report)
    if errors:
        print("报告契约校验失败：" + "；".join(errors), file=sys.stderr)
    else:
        json_path, md_path = export_report(report, _store(settings).experiment_dir(exp_id))
        print(f"report.json: {json_path}")
        print(f"report.md: {md_path}")

    if grading.stdout:
        print(grading.stdout[-4000:])
    if grading.stderr:
        print(grading.stderr[-2000:], file=sys.stderr)
    print(f"\n自评报告：{report_path}")
    if ai_result.get("mode") == "deepseek":
        print(f"分析来源：模型 {ai_result.get('model', settings.deepseek_model)}")
    else:
        print(f"分析来源：规则降级（{ai_result.get('note', '')}）")
    for item in (ai_result.get("suggestions") or [])[:3]:
        print(f"  - {item}")
    return 0 if grading.ok else grading.returncode


def _build_ai_evidence(settings, experiment, grading, comfort, remaining):
    """裁剪后交给模型的证据：只有事实，不包含命令原文和路径细节。"""
    metrics = grading.get("metrics", [])
    events = {}
    for name, items in (grading.get("events") or {}).items():
        if not items:
            continue
        times = [t for t, _ in items]
        events[name] = {
            "count": len(items),
            "first_t": round(min(times), 2),
            "last_t": round(max(times), 2),
            "sample": items[0][1][:120],
        }
    evidence = {
        "meta": {
            "scenario": experiment["meta"].get("scenario"),
            "record_duration_sec": experiment.get("record", {}).get("duration_sec"),
            "record_messages": experiment.get("record", {}).get("message_count"),
            "record_channels": experiment.get("record", {}).get("channel_count"),
        },
        "score": {
            "scenario_pass": grading.get("scenario_pass"),
            "passed_metrics": experiment.get("score", {}).get("passed_metrics"),
            "metrics": [
                {"name": m["name"], "pass": m["pass"], "fail": m["fail"], "total": m["total"]}
                for m in metrics
            ],
        },
        "events": events,
        "metrics": {
            "max_lon_accel": comfort.get("max_lon_accel"),
            "max_jerk": comfort.get("max_lon_jerk"),
            "max_jerk_time": comfort.get("max_lon_jerk_time"),
            "jerk_p95": comfort.get("jerk_p95"),
            "max_lat_accel": comfort.get("max_lat_accel"),
            "hard_brake": comfort.get("hard_brake_count"),
            "max_speed": comfort.get("max_speed_ms"),
            "avg_speed": comfort.get("avg_speed_ms"),
            "remaining_to_end_m": None if remaining is None else round(remaining, 1),
        },
    }
    skills = resolve_skills(settings)
    if skills.dev_knowledge:
        query = " ".join([experiment["meta"].get("scenario", "")]
                          + [m["name"] for m in metrics if not m["pass"]])
        snippets = search_knowledge(skills.dev_knowledge, query or "Planning 调试", limit=4)
        if snippets:
            evidence["knowledge"] = [
                {"path": str(path.name), "excerpt": excerpt[:600]} for path, excerpt in snippets
            ]
    errors = experiment.get("errors") or []
    if errors:
        evidence["errors"] = [{"source": e.get("source"), "message": e.get("message")} for e in errors[-2:]]
    return evidence


def _ai_analyze(settings, evidence, scenario_name):
    """模型分析为主，规则降级为辅。返回带 mode 字段的结果。"""
    question = (
        f"这是「{scenario_name}」的一次仿真自评。请先给一句总结判断，"
        "再指出最值得改的一件事，并说明依据哪项指标；不确定的地方放进 hypotheses。"
        "引用知识库时只能用 evidence.knowledge 里给出的文件名，不要引用其它文档。"
    )
    try:
        result = explain(settings, evidence, question)
        result["mode"] = "deepseek"
        result.setdefault("model", settings.deepseek_model)
        return result
    except DeepSeekUnavailable as exc:
        result = fallback_explain(evidence)
        result["mode"] = "fallback"
        result["note"] = f"未使用模型：{exc}"
        return result


def _write_selfeval_report(settings, experiment, grading, comfort, suggestions, remaining=None, ai=None) -> Path:
    exp_id = experiment["meta"]["experiment_id"]
    directory = _store(settings).experiment_dir(exp_id)
    lines = []
    verdict = "PASS" if grading.get("scenario_pass") else "FAIL"
    lines.append(f"# 自评报告 · {experiment['meta'].get('scenario', '')}")
    lines.append("")
    lines.append("> 本报告由 apollo-claw 自动生成，属**自评**，不是赛事官方评分。")
    lines.append("> 指标阈值来自技能自带示例与知识库推荐值，只保证横向可比，不代表官方口径。")
    lines.append("")
    lines.append(f"- 实验编号：`{exp_id}`")
    lines.append(f"- 场景判定：**{verdict}**（通过 {experiment.get('score', {}).get('passed_metrics', '-')} 项）")
    if experiment["meta"].get("scenario_file"):
        lines.append(f"- 判定所用场景：`{experiment['meta']['scenario_file']}`")
    lines.append(f"- record：`{experiment.get('record', {}).get('path', '')}`")
    if remaining is not None:
        lines.append(f"- 录制结束时距终点：**{remaining:.1f} m**")
    lines.append("")

    # ── 模型分析：报告主体 ──
    ai = ai or {}
    mode = ai.get("mode", "fallback")
    lines.append("## 分析")
    lines.append("")
    if mode == "deepseek":
        lines.append(f"> 本节由模型（{ai.get('model', settings.deepseek_model)}）基于下方数据生成；数字与判定来自脚本，模型不改写。")
    else:
        lines.append(f"> {ai.get('note', '未配置模型，使用规则模板')}")
    lines.append("")

    facts = ai.get("facts") or []
    hypotheses = ai.get("hypotheses") or []
    ai_suggestions = ai.get("suggestions") or []
    confirm = ai.get("need_student_confirm")
    refs = ai.get("source_refs") or []

    if facts:
        lines.append("**事实**")
        lines.append("")
        for item in facts:
            lines.append(f"- {item}")
        lines.append("")
    if hypotheses:
        lines.append("**推测**")
        lines.append("")
        for item in hypotheses:
            lines.append(f"- {item}")
        lines.append("")
    if ai_suggestions:
        lines.append("**建议**")
        lines.append("")
        for idx, item in enumerate(ai_suggestions, 1):
            lines.append(f"{idx}. {item}")
        lines.append("")
    if confirm and (ai_suggestions or mode == "deepseek"):
        lines.append("**需要你确认的操作**：模型不执行命令，下列动作需你自己决定是否执行。")
        lines.append("")
    if refs:
        lines.append(f"<sub>引用：{'、'.join(str(r) for r in refs)}</sub>")
        lines.append("")

    lines.append("## 关键数据")
    lines.append("")
    lines.append("### 场景指标")
    lines.append("")
    lines.append("| 指标 | 结果 | 得分 | 未通过帧 |")
    lines.append("|---|---|---:|---:|")
    for item in grading.get("metrics", []):
        mark = "✅" if item["pass"] else "❌"
        # TTC 这类指标只判通过/不通过、不计算扣分，得分恒为 100，显示 — 更诚实
        score_text = f"{item['score']:.0f}" if (item["pass"] or item["score"] < 100) else "—"
        lines.append(f"| {item['name']} | {mark} | {score_text} | {item['fail']}/{item['total']} |")
    lines.append("")

    if comfort:
        lines.append("### 体感指标")
        lines.append("")
        lines.append("| 指标 | 实测 | 参考阈值 |")
        lines.append("|---|---:|---:|")
        lines.append(f"| 纵向加速度 | {comfort.get('max_lon_accel', 0):.2f} m/s² | ≤ 3.0 |")
        lines.append(f"| 纵向 Jerk | {comfort.get('max_lon_jerk', 0):.2f} m/s³ | ≤ 4.0 |")
        if isinstance(comfort.get("max_lon_jerk_time"), (int, float)):
            lines.append(f"| └ 峰值时刻 | {comfort['max_lon_jerk_time']:.1f} s | — |")
        if isinstance(comfort.get("jerk_p95"), (int, float)):
            lines.append(f"| └ Jerk P95 | {comfort['jerk_p95']:.2f} m/s³ | — |")
        lines.append(f"| 横向加速度 | {comfort.get('max_lat_accel', 0):.2f} m/s² | ≤ 2.0 |")
        lines.append(f"| 急刹次数 | {comfort.get('hard_brake_count', 0)} | 0 |")
        lines.append(f"| 速度 | 最大 {comfort.get('max_speed_ms', 0):.2f} / 均值 {comfort.get('avg_speed_ms', 0):.2f} m/s | — |")
        lines.append("")

    lines.append("## 规则检查（脚本生成）")
    lines.append("")
    for tip in suggestions:
        lines.append(f"- {tip}")
    lines.append("")
    lines.append("## 证据")
    lines.append("")
    for item in experiment.get("evidence", []):
        lines.append(f"- `{item.get('type')}`：{item.get('path')}")
    lines.append("")

    path = directory / "selfeval.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def cmd_experiment(settings: Settings, args) -> int:
    store = _store(settings)
    if args.experiment_command == "list":
        for item in store.list():
            meta = item.get("meta", {})
            print(f"{meta.get('experiment_id')}  {meta.get('status')}  {meta.get('scenario')}")
        return 0
    if args.experiment_command == "show":
        print(json.dumps(store.load(args.id), ensure_ascii=False, indent=2))
        return 0
    return 2


def cmd_serve(settings: Settings, args) -> int:
    from .server import serve
    serve(settings, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apollo-claw", description="Apollo Claw Harness")
    parser.add_argument("--version", action="version", version=f"apollo-claw {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="检查本地 Apollo 环境")
    p.add_argument("--json", action="store_true")
    p.add_argument("--experiment")
    p.add_argument("--task", default="crosswalk")
    p.add_argument("--scenario", default="人行道避让")
    p.add_argument("--output")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("explain", help="解释证据或日志")
    p.add_argument("--evidence")
    p.add_argument("--log")
    p.add_argument("--experiment")
    p.add_argument("--question", default="")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("advise", help="根据证据给出优化建议")
    p.add_argument("--evidence", required=True)
    p.add_argument("--experiment")
    p.add_argument("--question", default="")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("report", help="报告导出")
    rsub = p.add_subparsers(dest="report_command", required=True)
    q = rsub.add_parser("export", help="导出 report.json 和 report.md")
    q.add_argument("--evidence")
    q.add_argument("--experiment")
    q.add_argument("--output-dir")
    q.set_defaults(func=cmd_report_export)

    q = rsub.add_parser("build", help="自评报告：场景评分 + 体感 + 改进建议")
    q.add_argument("--experiment")
    q.add_argument("--metric", help="评分配置，省略则用包内自评配置")
    q.add_argument("--scenario", help="scenario.json，用于填 ReachEnd 终点")
    q.add_argument("--timeout", type=int, default=300)
    q.add_argument("--execute", action="store_true")
    q.set_defaults(func=cmd_report_build)

    p = sub.add_parser("test", help="测试与数据命令")
    tsub = p.add_subparsers(dest="test_command", required=True)
    q = tsub.add_parser("record", help="录制 record")
    q.add_argument("--experiment")
    q.add_argument("--task", default="crosswalk")
    q.add_argument("--scenario", default="人行道避让")
    q.add_argument("--tag", default="crosswalk")
    q.add_argument("--profile", default="pnc")
    q.add_argument("--seconds", type=int, default=25)
    q.add_argument("--execute", action="store_true")
    q.set_defaults(func=cmd_test_record)
    q = tsub.add_parser("report", help="生成 channel 报告")
    q.add_argument("--experiment")
    q.add_argument("--task", default="crosswalk")
    q.add_argument("--scenario", default="人行道避让")
    q.add_argument("--record", required=True)
    q.add_argument("--script")
    q.add_argument("--output")
    q.add_argument("--timeout", type=int, default=300)
    q.add_argument("--execute", action="store_true")
    q.set_defaults(func=cmd_test_report)

    p = sub.add_parser("eval", help="运行评分脚本")
    p.add_argument("--experiment")
    p.add_argument("--task", default="crosswalk")
    p.add_argument("--metric", help="评分配置路径（grading_metrics*.conf 或 .json）")
    p.add_argument("--comfort", action="store_true", help="只跑体感指标评估（extract_metrics.py）")
    p.add_argument("--interval", type=float, help="体感评估重采样间隔，默认 0.1s")
    p.add_argument("--scenario", help="scenario.json 路径，只用于填 ReachEnd 终点")
    p.add_argument("--scenario-name", default="人行道避让")
    p.add_argument("--script")
    p.add_argument("--bag", help="被评分的 record/bag，默认取当前实验的 record")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("experiment", help="查看实验记录")
    esub = p.add_subparsers(dest="experiment_command", required=True)
    q = esub.add_parser("list", help="列出实验")
    q.set_defaults(func=cmd_experiment)
    q = esub.add_parser("show", help="显示实验 manifest")
    q.add_argument("--id", required=True)
    q.set_defaults(func=cmd_experiment)

    p = sub.add_parser("serve", help="启动本地实验面板")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.load()
    return args.func(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())
