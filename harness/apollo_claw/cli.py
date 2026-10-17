"""CLI entry point for Apollo Claw Harness."""
from __future__ import annotations

import argparse
import json
import platform
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
    experiment["record"]["path"] = record_path
    experiment["record"]["file_count"] = len(files)
    experiment["record"]["size_bytes"] = total_bytes
    experiment["record"]["stop_reason"] = "timeout" if result.returncode == 124 else "command_exit"
    store.add_evidence(experiment, "record", record_path, f"{args.seconds} 秒，6 个核心 channel 请求")
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
    script = _resolve_container_script(settings, getattr(args, "script", None), skills.eval_grading_script)
    if not script:
        print("需要指定 --script，或把 apollo-eval 放到 APOLLO_CLAW_SKILLS_DIR", file=sys.stderr)
        return 2
    scenario = _host_to_container(settings, args.scenario)
    bag = _host_to_container(settings, args.bag)
    argv = ["python3", script, "--config", scenario, "--mode", "bag", "--bag_file", bag]
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
    p.add_argument("--scenario", required=True, help="scenario.json 路径")
    p.add_argument("--scenario-name", default="人行道避让")
    p.add_argument("--script")
    p.add_argument("--bag", required=True)
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
