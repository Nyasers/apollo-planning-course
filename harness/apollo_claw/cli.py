"""CLI entry point for Apollo Claw Harness."""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import Settings
from .deepseek import DeepSeekUnavailable, explain, fallback_explain
from .evidence import read_json, write_json
from .report import export_report
from .router import route
from .runner import docker_exec, run_host


def _which(name: str) -> str:
    return shutil.which(name) or ""


def _host_probe(argv):
    try:
        result = run_host(argv, timeout=20)
        return {"ok": result.ok, "returncode": result.returncode, "stdout": result.stdout.strip()[:2000], "stderr": result.stderr.strip()[:1000]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def cmd_doctor(settings: Settings, args) -> int:
    workspace = Path(settings.apollo_workspace_host).expanduser()
    data = {
        "meta": {"version": __version__, "skill": "apollo-env"},
        "host": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(Path.cwd()),
            "docker": _which("docker"),
            "aem": _which("aem"),
            "workspace": str(workspace),
            "workspace_exists": workspace.exists(),
        },
        "checks": {
            "docker_version": _host_probe(["docker", "--version"]),
            "docker_info": _host_probe(["docker", "info", "--format", "{{.ServerVersion}}"]),
            "aem_version": _host_probe(["aem", "--version"]),
        },
    }
    try:
        ps = run_host(["docker", "ps", "--format", "{{.Names}}"], timeout=20)
        names = [n for n in ps.stdout.splitlines() if n.strip()]
        data["apollo"] = {
            "containers": names,
            "container_running": settings.apollo_container_name in names,
        }
    except Exception as exc:
        data["apollo"] = {"containers": [], "container_running": False, "error": str(exc)}
    out = Path(args.output).expanduser() if args.output else Path(settings.output_dir) / "latest" / "doctor.json"
    write_json(out, data)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("Apollo Claw doctor")
        print(f"workspace: {data['host']['workspace']} ({data['host']['workspace_exists']})")
        print(f"docker: {data['host']['docker'] or 'not found'}")
        print(f"aem: {data['host']['aem'] or 'not found'}")
        print(f"Apollo container running: {data['apollo']['container_running']}")
        print(f"saved: {out}")
    return 0


def _load_evidence(path: str | None):
    if path:
        return read_json(Path(path).expanduser())
    return {"meta": {"task": "unknown"}, "metrics": {}, "evidence": []}


def cmd_explain(settings: Settings, args) -> int:
    evidence = _load_evidence(args.evidence)
    if args.log:
        log_path = Path(args.log).expanduser()
        text = log_path.read_text(encoding="utf-8", errors="ignore")[-12000:]
        evidence.setdefault("logs", []).append({"path": str(log_path), "excerpt": text})
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
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_report_export(settings: Settings, args) -> int:
    evidence = _load_evidence(args.evidence)
    out_dir = Path(args.output_dir).expanduser() if args.output_dir else Path(settings.output_dir) / evidence.get("meta", {}).get("experiment_id", "latest")
    json_path, md_path = export_report(evidence, out_dir)
    print(f"report.json: {json_path}")
    print(f"report.md: {md_path}")
    return 0


def cmd_test_record(settings: Settings, args) -> int:
    out = f"{settings.apollo_workspace_container}/data/record/{args.tag}.record"
    channels = [
        "/apollo/planning",
        "/apollo/control",
        "/apollo/localization/pose",
        "/apollo/canbus/chassis",
        "/apollo/perception/obstacles",
        "/apollo/prediction",
    ]
    channel_args = " ".join(f"-c {c}" for c in channels)
    command = f"mkdir -p {settings.apollo_workspace_container}/data/record && timeout {args.seconds} cyber_recorder record -o {out} {channel_args}"
    print(command)
    if not args.execute:
        print("dry-run: add --execute to run inside the Apollo container")
        return 0
    result = docker_exec(settings, command, timeout=args.seconds + 30)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0 if result.ok else result.returncode


def cmd_test_report(settings: Settings, args) -> int:
    if not args.script:
        print("需要指定 --script 指向 apollo-test/scripts/record_channel_report.py")
        return 2
    command = f"PYTHONPATH=/opt/apollo/neo/python MPLCONFIGDIR=/tmp/matplotlib python3 {args.script} {args.record} -o {args.output or (settings.apollo_workspace_container + '/data/record/report')}"
    print(command)
    if not args.execute:
        print("dry-run: add --execute to run inside the Apollo container")
        return 0
    result = docker_exec(settings, command, timeout=args.timeout)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0 if result.ok else result.returncode


def cmd_eval(settings: Settings, args) -> int:
    if not args.script:
        print("需要指定 --script 指向 apollo-eval/scripts/grading_system_py/main.py")
        return 2
    command = f"PYTHONPATH=/opt/apollo/neo/python python3 {args.script} --config {args.scenario} --mode bag --bag_file {args.bag}"
    print(command)
    if not args.execute:
        print("dry-run: add --execute to run inside the Apollo container")
        return 0
    result = docker_exec(settings, command, timeout=args.timeout)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0 if result.ok else result.returncode


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
    p.add_argument("--output")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("explain", help="解释证据或日志")
    p.add_argument("--evidence")
    p.add_argument("--log")
    p.add_argument("--question", default="")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("advise", help="根据证据给出优化建议")
    p.add_argument("--evidence", required=True)
    p.add_argument("--question", default="")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("report", help="报告导出")
    rsub = p.add_subparsers(dest="report_command", required=True)
    q = rsub.add_parser("export", help="导出 report.json 和 report.md")
    q.add_argument("--evidence", required=True)
    q.add_argument("--output-dir")
    q.set_defaults(func=cmd_report_export)

    p = sub.add_parser("test", help="测试与数据命令")
    tsub = p.add_subparsers(dest="test_command", required=True)
    q = tsub.add_parser("record", help="录制 record")
    q.add_argument("--tag", default="crosswalk")
    q.add_argument("--seconds", type=int, default=25)
    q.add_argument("--execute", action="store_true")
    q.set_defaults(func=cmd_test_record)
    q = tsub.add_parser("report", help="生成 channel 报告")
    q.add_argument("--record", required=True)
    q.add_argument("--script")
    q.add_argument("--output")
    q.add_argument("--timeout", type=int, default=300)
    q.add_argument("--execute", action="store_true")
    q.set_defaults(func=cmd_test_report)

    p = sub.add_parser("eval", help="运行评分脚本")
    p.add_argument("--script")
    p.add_argument("--scenario", required=True)
    p.add_argument("--bag", required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_eval)

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
