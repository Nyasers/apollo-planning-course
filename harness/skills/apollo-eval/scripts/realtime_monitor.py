#!/usr/bin/env python3
"""
realtime_monitor.py — Apollo EDU PnC 赛道体感指标实时监控

订阅 /apollo/planning/trajectory，逐帧计算体感指标并在终端实时告警。
按 Ctrl+C 退出，退出后输出完整统计报告。

对应 SKILL.md 流程A 技术实现：
  - 纵向加速度 aₓ（阈值 3.0 m/s²）
  - 纵向 Jerk  jₓ（阈值 4.0 m/s³）
  - 急刹车检测（a < -4.0 m/s²）
  - 横向加速度 aᵧ = v² × κ（阈值 2.0 m/s²）

用法:
  python3 realtime_monitor.py
  python3 realtime_monitor.py --lon-accel-max 2.5 --jerk-max 3.0
"""

import sys
import math
import signal
import argparse
import threading
from dataclasses import dataclass, field
from typing import Optional, List

# ── 依赖检查 ──────────────────────────────────────────────────────────────

try:
    import cyber_init  # noqa: F401 — side-effect import that must come first
    from cyber.python.cyber_py3 import cyber
    _HAS_CYBER = True
except ImportError:
    _HAS_CYBER = False

try:
    from modules.planning.proto.planning_pb2 import ADCTrajectory
    _HAS_PROTO = True
except ImportError:
    _HAS_PROTO = False

# ── ANSI 颜色 ──────────────────────────────────────────────────────────────

_RED    = "\033[31m"
_YELLOW = "\033[33m"
_GREEN  = "\033[32m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


def _red(s: str) -> str:    return f"{_RED}{s}{_RESET}"
def _yellow(s: str) -> str: return f"{_YELLOW}{s}{_RESET}"
def _green(s: str) -> str:  return f"{_GREEN}{s}{_RESET}"
def _bold(s: str) -> str:   return f"{_BOLD}{s}{_RESET}"


# ── 默认阈值 ──────────────────────────────────────────────────────────────

DEFAULT_LON_ACCEL_MAX = 3.0   # m/s²
DEFAULT_LON_JERK_MAX  = 4.0   # m/s³
DEFAULT_LAT_ACCEL_MAX = 2.0   # m/s²
DEFAULT_HARD_BRAKE    = 4.0   # m/s²（减速度绝对值）

PLANNING_CHANNEL = "/apollo/planning/trajectory"

# ── 数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class MonitorStats:
    """累计统计，对应 SKILL.md 流程A Step2 实时统计区块"""
    start_time:        float = 0.0
    last_time:         float = 0.0
    total_msgs:        int   = 0
    lon_accel_alerts:  int   = 0
    jerk_alerts:       int   = 0
    lat_accel_alerts:  int   = 0
    hard_brake_alerts: int   = 0
    max_lon_accel:     float = 0.0
    max_lon_jerk:      float = 0.0
    max_lat_accel:     float = 0.0
    # 用于跨消息计算 jerk 的上一帧数值
    prev_accel:        Optional[float] = None
    prev_time:         Optional[float] = None
    # 急刹车状态机（防重复计数）
    in_hard_brake:     bool  = False


# ── 核心回调 ──────────────────────────────────────────────────────────────

class TrajectoryMonitor:
    """订阅 ADCTrajectory，逐帧打印体感指标。"""

    def __init__(self, args):
        self.args  = args
        self.stats = MonitorStats()
        self._lock = threading.Lock()

    def _extract_traj_point(self, traj_msg) -> Optional[tuple]:
        """
        从 ADCTrajectory 取第一个轨迹点的速度、加速度、曲率。
        返回 (timestamp, v, a, kappa) 或 None。
        """
        if not traj_msg.trajectory_point:
            return None
        pt    = traj_msg.trajectory_point[0]
        t     = traj_msg.header.timestamp_sec
        v     = pt.v
        a     = pt.a
        kappa = getattr(pt.path_point, "kappa", 0.0)
        return (t, v, a, kappa)

    def on_trajectory(self, raw_bytes: bytes):
        if not _HAS_PROTO:
            return
        msg = ADCTrajectory()
        msg.ParseFromString(raw_bytes)

        point = self._extract_traj_point(msg)
        if point is None:
            return
        t, v, a, kappa = point

        with self._lock:
            stats = self.stats
            if stats.total_msgs == 0:
                stats.start_time = t
            stats.last_time  = t
            stats.total_msgs += 1

            abs_a   = abs(a)
            lat_a   = v * v * abs(kappa)   # 向心加速度 v² × κ
            elapsed = t - stats.start_time

            # 跨消息计算纵向 Jerk
            if stats.prev_accel is not None and stats.prev_time is not None:
                dt       = t - stats.prev_time
                lon_jerk = (a - stats.prev_accel) / dt if dt > 1e-6 else 0.0
            else:
                lon_jerk = 0.0
            stats.prev_accel = a
            stats.prev_time  = t

            # 更新峰值
            stats.max_lon_accel = max(stats.max_lon_accel, abs_a)
            stats.max_lon_jerk  = max(stats.max_lon_jerk, abs(lon_jerk))
            stats.max_lat_accel = max(stats.max_lat_accel, lat_a)

            # 构建行内容
            parts: List[str] = [
                f"[{elapsed:>6.1f}s]",
                f"v={v:>5.2f}m/s",
                f"a={a:>+6.2f}m/s²",
                f"j={lon_jerk:>+6.2f}m/s³",
                f"ay={lat_a:>5.2f}m/s²",
            ]
            alerts: List[str] = []

            if abs_a > self.args.lon_accel_max:
                stats.lon_accel_alerts += 1
                alerts.append(_red(f"纵向加速度超限({abs_a:.2f}>{self.args.lon_accel_max})"))

            if abs(lon_jerk) > self.args.jerk_max:
                stats.jerk_alerts += 1
                alerts.append(_yellow(f"Jerk超限({lon_jerk:+.2f}>{self.args.jerk_max})"))

            if lat_a > self.args.lat_accel_max:
                stats.lat_accel_alerts += 1
                alerts.append(_yellow(f"横向加速度超限({lat_a:.2f}>{self.args.lat_accel_max})"))

            # 急刹车状态机
            if v > 0.5 and a < -self.args.hard_brake:
                if not stats.in_hard_brake:
                    stats.in_hard_brake = True
                    stats.hard_brake_alerts += 1
                    alerts.append(_red(f"急刹车！({a:.2f}<-{self.args.hard_brake})"))
            else:
                stats.in_hard_brake = False

            status = "  ".join(alerts) if alerts else _green("✅")
            print("  ".join(parts) + "  " + status, flush=True)

    def print_summary(self):
        stats    = self.stats
        duration = stats.last_time - stats.start_time if stats.total_msgs > 0 else 0.0
        total    = (stats.lon_accel_alerts + stats.jerk_alerts
                    + stats.lat_accel_alerts + stats.hard_brake_alerts)

        print()
        print(_bold("=" * 56))
        print(_bold("  实时监控统计报告"))
        print(_bold("=" * 56))
        print(f"  运行时长      : {duration:.1f} s")
        print(f"  处理消息数    : {stats.total_msgs}")
        print(f"  纵向加速度超限: {stats.lon_accel_alerts} 次  "
              f"(峰值 {stats.max_lon_accel:.2f} m/s²)")
        print(f"  纵向 Jerk 超限: {stats.jerk_alerts} 次  "
              f"(峰值 {stats.max_lon_jerk:.2f} m/s³)")
        print(f"  横向加速度超限: {stats.lat_accel_alerts} 次  "
              f"(峰值 {stats.max_lat_accel:.2f} m/s²)")
        print(f"  急刹车次数    : {stats.hard_brake_alerts} 次")
        print()
        if total == 0:
            print(_green("  ✅ 体感指标全部正常"))
        else:
            print(_red(f"  ⚠️  共 {total} 次超限，建议优化以下参数："))
            if stats.lon_accel_alerts:
                print("    • 纵向加速度超限 → 调低 max_acceleration / max_deceleration")
            if stats.jerk_alerts:
                print("    • Jerk 超限 → 增大 jerk_limit 约束或提升规划平滑度")
            if stats.lat_accel_alerts:
                print("    • 横向加速度超限 → 降低过弯速度限制或增大转向平滑约束")
            if stats.hard_brake_alerts:
                print("    • 急刹车 → grep stop_reason 日志确认 TrafficRule 触发是否合理")
        print(_bold("=" * 56))


# ── 入口 ──────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Apollo EDU PnC 体感指标实时监控",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python3 realtime_monitor.py\n"
            "  python3 realtime_monitor.py --lon-accel-max 2.5\n"
        ),
    )
    p.add_argument("--lon-accel-max", type=float, default=DEFAULT_LON_ACCEL_MAX,
                   metavar="N", help=f"纵向加速度告警阈值 m/s²（默认 {DEFAULT_LON_ACCEL_MAX}）")
    p.add_argument("--jerk-max", type=float, default=DEFAULT_LON_JERK_MAX,
                   metavar="N", help=f"纵向 Jerk 告警阈值 m/s³（默认 {DEFAULT_LON_JERK_MAX}）")
    p.add_argument("--lat-accel-max", type=float, default=DEFAULT_LAT_ACCEL_MAX,
                   metavar="N", help=f"横向加速度告警阈值 m/s²（默认 {DEFAULT_LAT_ACCEL_MAX}）")
    p.add_argument("--hard-brake", type=float, default=DEFAULT_HARD_BRAKE,
                   metavar="N", help=f"急刹车减速度阈值 m/s²（默认 {DEFAULT_HARD_BRAKE}）")
    return p


def main():
    if not _HAS_CYBER:
        print("[ERROR] 请在 Apollo 容器内执行（aem enter），确认 cyber_py3 可用。")
        sys.exit(1)
    if not _HAS_PROTO:
        print("[ERROR] planning proto 不可用，请确认 Apollo 环境已正确初始化。")
        sys.exit(1)

    args    = _build_parser().parse_args()
    monitor = TrajectoryMonitor(args)

    node   = cyber.Node("realtime_monitor")
    reader = node.create_reader(  # noqa: F841
        PLANNING_CHANNEL,
        ADCTrajectory,
        monitor.on_trajectory,
    )

    print(_bold("===== Apollo 体感指标实时监控 ====="))
    print(f"已连接 {PLANNING_CHANNEL}")
    print(f"阈值：aₓ≤{args.lon_accel_max} m/s²  "
          f"jₓ≤{args.jerk_max} m/s³  "
          f"aᵧ≤{args.lat_accel_max} m/s²  "
          f"急刹车>{args.hard_brake} m/s²")
    print("按 Ctrl+C 停止监控")
    print()

    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

    try:
        cyber.waitforshutdown()
    except KeyboardInterrupt:
        pass
    finally:
        monitor.print_summary()


if __name__ == "__main__":
    main()
