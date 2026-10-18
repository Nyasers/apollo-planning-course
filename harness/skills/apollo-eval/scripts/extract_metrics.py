#!/usr/bin/env python3
"""
extract_metrics.py — Apollo EDU PnC 赛道体感指标评估脚本

从 cyber record 中读取定位数据，复现 replay-engine/grading_system/condition
的核心评估逻辑，输出体感指标报告。

对应 C++ Condition Handlers:
  AccelerationConditionHandler       → 纵向加速度检测（扣分制）
  JerkConditionHandler               → 纵向 Jerk 检测
  CentripetalAccelerationConditionHandler → 横向加速度（speed × spin）
  SpeedConditionHandler              → 速度合规检测
  SpinConditionHandler               → 角速度检测
  BrakeTapConditionHandler           → 急刹车检测（简化版，不依赖地图）
  TimeLimitConditionHandler          → 场景时长

数据来源：/apollo/localization/pose
  speed     = sqrt(vx² + vy²)         ← Object.speed
  lon_accel = Δspeed / Δt             ← Object.speed_acceleration
  lon_jerk  = Δlon_accel / Δt         ← Object.speed_jerk
  lat_accel = speed × |spin_z|        ← centripetal_acceleration = speed * spin
  spin_z    = angular_velocity.z      ← Object.spin (yaw rate rad/s)

用法:
  python3 extract_metrics.py <record>
  python3 extract_metrics.py <record> --json report.json
  python3 extract_metrics.py <record> --lon-accel-max 2.5 --jerk-max 3.0
"""

import sys
import math
import json
import argparse
from dataclasses import dataclass, field
from typing import List

# 容器里的 locale 常是 POSIX/ASCII，中文输出会直接抛 UnicodeEncodeError，先把 stdout 换成容错编码。
try:
    sys.stdout.reconfigure(errors="replace")  # Python 3.7+
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 依赖检查 ──────────────────────────────────────────────────────────────

try:
    from cyber_record.record import Record
except ImportError:
    # 容器里通常没有 pip 包 cyber_record，但 Apollo 自带 cyber_py3，
    # 这里做一个最小适配，把 RecordReader 包装成同样的 read_messages() 接口。
    sys.path.insert(0, "/opt/apollo/neo/python")
    try:
        from cyber.python.cyber_py3 import record as _cyber
    except ImportError:
        _msg = "[ERROR] \u8bf7\u5728 Apollo \u5bb9\u5668\u5185\u6267\u884c\uff0c\u786e\u8ba4 cyber_py3 \u53ef\u7528\u3002"
        try:
            print(_msg)
        except UnicodeEncodeError:
            print(_msg.encode("ascii", "replace").decode("ascii"))
        sys.exit(1)

    class Record(object):
        """cyber_record.Record 的替代实现，统一产出 (topic, payload_bytes, timestamp_ns)。"""

        def __init__(self, path):
            self._reader = _cyber.RecordReader(str(path))

        def read_messages(self):
            for item in self._reader.read_messages():
                topic = getattr(item, "topic", item[0])
                payload = getattr(item, "message", item[1])
                timestamp = getattr(item, "timestamp", item[2] if len(item) > 2 else 0)
                if hasattr(payload, "SerializeToString"):
                    payload = payload.SerializeToString()
                yield topic, payload, timestamp

try:
    from modules.common_msgs.localization_msgs.localization_pb2 import LocalizationEstimate
    _HAS_PROTO = True
except ImportError:
    _HAS_PROTO = False
    print("[WARN] localization proto 不可用，将尝试 raw bytes 解析（可能失败）。")

# ── 默认阈值（与 config.yaml 对齐）────────────────────────────────────────

DEFAULT_LON_ACCEL_MAX = 3.0   # 纵向加速度上限 m/s²   ← eval_lon_accel_max
DEFAULT_LON_JERK_MAX  = 4.0   # 纵向 Jerk 上限 m/s³   ← eval_lon_jerk_max
DEFAULT_LAT_ACCEL_MAX = 2.0   # 横向加速度上限 m/s²   ← eval_lat_accel_max
DEFAULT_HARD_BRAKE    = 4.0   # 急刹车减速度阈值 m/s² ← eval_hard_brake_threshold
DEFAULT_SPIN_MAX      = 45.0  # 角速度上限 deg/s

# 扣分参数（对应 C++ ScoreDeductedByUnit）
ACCEL_DEDUCTION_UNIT   = 1.0   # 每超 1 m/s² 扣一档
ACCEL_SINGLE_DEDUCTION = 5.0   # 每档扣 5 分
LAT_DEDUCTION_UNIT     = 0.5   # 每超 0.5 m/s² 扣一档
LAT_SINGLE_DEDUCTION   = 3.0   # 每档扣 3 分
HARD_BRAKE_DEDUCTION   = 10.0  # 每次急刹车扣 10 分

LOCALIZATION_CHANNEL = "/apollo/localization/pose"

# ── 数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class Frame:
    """一帧车辆状态，对应 C++ GradingWorld.auto_driving_car"""
    timestamp:  float
    x:          float
    y:          float
    heading:    float   # rad
    speed:      float   # m/s         ← Object.speed
    lon_accel:  float   # m/s²        ← Object.speed_acceleration
    lon_jerk:   float   # m/s³        ← Object.speed_jerk
    lat_accel:  float   # m/s²        ← centripetal_acceleration = speed * spin
    spin:       float   # rad/s       ← Object.spin


@dataclass
class ViolationEvent:
    timestamp:  float
    metric:     str
    value:      float
    threshold:  float


@dataclass
class EvalResult:
    """对应 C++ DetailedResult 汇总"""
    total_frames:         int   = 0
    duration_sec:         float = 0.0
    max_speed:            float = 0.0
    avg_speed:            float = 0.0
    # AccelerationConditionHandler
    max_lon_accel:        float = 0.0
    lon_accel_violations: List[ViolationEvent] = field(default_factory=list)
    # JerkConditionHandler
    max_lon_jerk:         float = 0.0
    max_lon_jerk_time:    float = 0.0   # 相对开头的秒数
    jerk_p95:             float = 0.0
    jerk_violations:      List[ViolationEvent] = field(default_factory=list)
    # CentripetalAccelerationConditionHandler
    max_lat_accel:        float = 0.0
    lat_accel_violations: List[ViolationEvent] = field(default_factory=list)
    # BrakeTapConditionHandler（简化）
    hard_brake_count:     int   = 0
    hard_brake_events:    List[ViolationEvent] = field(default_factory=list)
    # SpinConditionHandler
    max_spin_deg:         float = 0.0
    # 扣分估算
    score_deduction:      float = 0.0


# ── 工具 ──────────────────────────────────────────────────────────────────

def _score_deducted_by_unit(delta: float, unit: float, single: float) -> float:
    """
    对应 C++ ConditionEvaluatorUtil::ScoreDeductedByUnit
    超出阈值越多扣分越多：每超 unit 扣 single 分。
    """
    if unit <= 0:
        return single
    return math.ceil(delta / unit) * single


# ── cyber record 读取 ─────────────────────────────────────────────────────

def _read_localization(record_path: str) -> List[dict]:
    """从 cyber record 读取定位 channel，返回按时间排序的原始帧列表。"""
    raw = []
    record = Record(record_path)
    for topic, message, _ in record.read_messages():
        if topic != LOCALIZATION_CHANNEL:
            continue
        if not _HAS_PROTO:
            continue
        msg = LocalizationEstimate()
        msg.ParseFromString(message)
        pose = msg.pose
        raw.append({
            "timestamp": msg.header.timestamp_sec,
            "x":         pose.position.x,
            "y":         pose.position.y,
            "heading":   pose.heading,
            "vx":        pose.linear_velocity.x,
            "vy":        pose.linear_velocity.y,
            "spin_z":    pose.angular_velocity.z,  # yaw rate rad/s
        })
    return sorted(raw, key=lambda f: f["timestamp"])


def _resample(raw: List[dict], interval: float = 0.1) -> List[dict]:
    """把定位帧重采样到固定间隔（线性插值）。

    定位 channel 常常是 100Hz，直接在原始帧上做差分会把噪声放大；
    官方评分引擎是按 0.1s 一帧推进的，这里对齐到同样的采样率。
    注意必须**插值**到等间隔网格，而不是挑最近的原始帧：
    数据有断档时，挑帧会让相邻采样点间隔忽大忽小（实测 0.05s / 0.14s），
    求导后 Jerk 会被放大到几十 m/s³，看起来像车在抽搠。
    """
    if not raw or interval <= 0:
        return raw

    # 同时间戳去重，保留最后一条
    clean = []
    for item in raw:
        if clean and abs(item["timestamp"] - clean[-1]["timestamp"]) < 1e-9:
            clean[-1] = item
        else:
            clean.append(item)
    if len(clean) < 2:
        return clean

    fields = ("x", "y", "vx", "vy", "spin_z", "heading")
    start = clean[0]["timestamp"]
    end = clean[-1]["timestamp"]
    count = int((end - start) / interval) + 1
    out = []
    idx = 0
    for k in range(count):
        target = start + k * interval
        while idx + 1 < len(clean) and clean[idx + 1]["timestamp"] <= target:
            idx += 1
        left = clean[idx]
        right = clean[idx + 1] if idx + 1 < len(clean) else left
        span = right["timestamp"] - left["timestamp"]
        ratio = (target - left["timestamp"]) / span if span > 1e-9 else 0.0
        ratio = min(max(ratio, 0.0), 1.0)
        frame = {"timestamp": target}
        for key in fields:
            a = left.get(key, 0.0)
            b = right.get(key, a)
            frame[key] = a + (b - a) * ratio
        out.append(frame)
    return out


def _compute_frames(raw: List[dict]) -> List[Frame]:
    """
    将原始定位帧转换为带体感指标的 Frame 列表。

    纵向加速度 = Δspeed / Δt
    纵向 Jerk  = Δlon_accel / Δt
    横向加速度 = speed × |spin_z|  (离心加速度 = v × ω)
    """
    frames = []
    prev_speed = None
    prev_accel = None
    prev_t     = None

    for r in raw:
        speed = math.hypot(r["vx"], r["vy"])

        if prev_speed is not None and prev_t is not None:
            dt        = r["timestamp"] - prev_t
            lon_accel = (speed - prev_speed) / dt if dt > 1e-6 else 0.0
        else:
            lon_accel = 0.0

        if prev_accel is not None and prev_t is not None:
            dt       = r["timestamp"] - prev_t
            lon_jerk = (lon_accel - prev_accel) / dt if dt > 1e-6 else 0.0
        else:
            lon_jerk = 0.0

        lat_accel = abs(speed * r["spin_z"])

        frames.append(Frame(
            timestamp=r["timestamp"],
            x=r["x"],
            y=r["y"],
            heading=r["heading"],
            speed=speed,
            lon_accel=lon_accel,
            lon_jerk=lon_jerk,
            lat_accel=lat_accel,
            spin=r["spin_z"],
        ))
        prev_speed = speed
        prev_accel = lon_accel
        prev_t     = r["timestamp"]

    return frames


# ── 指标评估 ──────────────────────────────────────────────────────────────

def evaluate(frames: List[Frame], args) -> EvalResult:
    """逐帧评估，对应各 C++ ConditionHandler.Evaluate()"""
    result = EvalResult()
    if not frames:
        return result

    result.total_frames = len(frames)
    result.duration_sec = frames[-1].timestamp - frames[0].timestamp
    speeds = [f.speed for f in frames]
    result.max_speed = max(speeds)
    result.avg_speed = sum(speeds) / len(speeds)

    # 急刹车状态机：防止同一制动过程被重复计数
    # 对应 C++ BrakeTapConditionHandler.triggered_count_
    in_hard_brake = False
    start_time = frames[0].timestamp
    jerks = []

    for f in frames:

        # ── AccelerationConditionHandler ──────────────────────────────────
        abs_accel = abs(f.lon_accel)
        result.max_lon_accel = max(result.max_lon_accel, abs_accel)
        if abs_accel > args.lon_accel_max:
            result.lon_accel_violations.append(ViolationEvent(
                timestamp=f.timestamp, metric="lon_accel",
                value=f.lon_accel, threshold=args.lon_accel_max,
            ))
            result.score_deduction += _score_deducted_by_unit(
                abs_accel - args.lon_accel_max,
                ACCEL_DEDUCTION_UNIT, ACCEL_SINGLE_DEDUCTION,
            )

        # ── JerkConditionHandler ──────────────────────────────────────────
        abs_jerk = abs(f.lon_jerk)
        jerks.append(abs_jerk)
        if abs_jerk > result.max_lon_jerk:
            result.max_lon_jerk = abs_jerk
            result.max_lon_jerk_time = f.timestamp - start_time
        if abs_jerk > args.jerk_max:
            result.jerk_violations.append(ViolationEvent(
                timestamp=f.timestamp, metric="jerk",
                value=f.lon_jerk, threshold=args.jerk_max,
            ))

        # ── CentripetalAccelerationConditionHandler ───────────────────────
        result.max_lat_accel = max(result.max_lat_accel, f.lat_accel)
        if f.lat_accel > args.lat_accel_max:
            result.lat_accel_violations.append(ViolationEvent(
                timestamp=f.timestamp, metric="lat_accel",
                value=f.lat_accel, threshold=args.lat_accel_max,
            ))
            result.score_deduction += _score_deducted_by_unit(
                f.lat_accel - args.lat_accel_max,
                LAT_DEDUCTION_UNIT, LAT_SINGLE_DEDUCTION,
            )

        # ── BrakeTapConditionHandler（简化：仅减速度阈值，不依赖地图/障碍物）──
        # 原版会排除红灯/转弯/障碍物挡路等合理减速；本版保守统计
        if f.speed > 1.0 and f.lon_accel < -args.hard_brake:
            if not in_hard_brake:
                in_hard_brake = True
                result.hard_brake_count += 1
                result.hard_brake_events.append(ViolationEvent(
                    timestamp=f.timestamp, metric="hard_brake",
                    value=f.lon_accel, threshold=-args.hard_brake,
                ))
                result.score_deduction += HARD_BRAKE_DEDUCTION
        else:
            in_hard_brake = False

        # ── SpinConditionHandler ──────────────────────────────────────────
        spin_deg = abs(f.spin) * 180.0 / math.pi
        result.max_spin_deg = max(result.max_spin_deg, spin_deg)

    if jerks:
        ordered = sorted(jerks)
        result.jerk_p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]

    return result


# ── 报告输出 ──────────────────────────────────────────────────────────────

def _pass_fail(violations, count=None) -> str:
    n = count if count is not None else len(violations)
    return "✅ 通过" if n == 0 else f"⚠️  超限 {n} 次"


def print_report(result: EvalResult, args, record_path: str):
    print()
    print("=" * 62)
    print("   Apollo EDU PnC 体感指标评估报告")
    print("=" * 62)
    print(f"  录包  : {record_path}")
    print(f"  帧数  : {result.total_frames}  时长: {result.duration_sec:.1f} s"
          f"  采样: {getattr(args, 'interval', 0.1):.2f} s")
    print(f"  速度  : 最大 {result.max_speed:.2f} m/s "
          f"({result.max_speed * 3.6:.1f} km/h)  "
          f"均值 {result.avg_speed:.2f} m/s")
    print()
    print("┌────────────────────────────────────────────────────────────┐")
    print("│  指标              实测最大值    阈值       结论            │")
    print("├────────────────────────────────────────────────────────────┤")
    print(f"│  纵向加速度 aₓ   {result.max_lon_accel:>9.2f} m/s²  "
          f"≤{args.lon_accel_max:.1f}    {_pass_fail(result.lon_accel_violations):<14}│")
    print(f"│  纵向 Jerk jₓ   {result.max_lon_jerk:>9.2f} m/s³  "
          f"≤{args.jerk_max:.1f}    {_pass_fail(result.jerk_violations):<14}│")
    print(f"│  横向加速度 aᵧ   {result.max_lat_accel:>9.2f} m/s²  "
          f"≤{args.lat_accel_max:.1f}    {_pass_fail(result.lat_accel_violations):<14}│")
    print(f"│  急刹车次数      {result.hard_brake_count:>9d} 次    "
          f"=0      {_pass_fail([], result.hard_brake_count):<14}│")
    print(f"│  角速度 (最大)   {result.max_spin_deg:>9.1f} °/s   "
          f"≤{args.spin_max:.0f}    "
          f"{'✅ 通过' if result.max_spin_deg <= args.spin_max else '⚠️  超限':<14}│")
    print("└────────────────────────────────────────────────────────────┘")
    print()
    if result.jerk_violations:
        phase = "起步阶段" if result.max_lon_jerk_time < 5.0 else "行驶中"
        print(f"  Jerk 峰值出现在 {result.max_lon_jerk_time:.1f} s（{phase}），P95 = {result.jerk_p95:.2f} m/s³")
        print()

    if result.score_deduction > 0:
        print(f"  ⚠️  估算体感扣分：{result.score_deduction:.0f} 分（不含场景通过率）")
    elif (result.lon_accel_violations or result.jerk_violations
          or result.lat_accel_violations or result.hard_brake_count):
        # Jerk/角速度这类指标只报超限、不单独扣分，不能因此写成“全部通过”
        total = (len(result.lon_accel_violations) + len(result.jerk_violations)
                 + len(result.lat_accel_violations) + result.hard_brake_count)
        print(f"  ⚠️  有 {total} 次超限（未计入扣分），需逐项看表。")
    else:
        print("  ✅ 体感指标全部通过，无扣分。")

    # 超限事件明细
    all_violations = sorted(
        result.lon_accel_violations + result.jerk_violations +
        result.lat_accel_violations + result.hard_brake_events,
        key=lambda v: v.timestamp,
    )
    if all_violations:
        print()
        print(f"  超限事件明细（共 {len(all_violations)} 条，显示前 10）：")
        for ev in all_violations[:10]:
            sign = "+" if ev.value >= 0 else ""
            print(f"    [{ev.timestamp:.1f}s] {ev.metric:<13} "
                  f"实测={sign}{ev.value:.3f}  阈值={ev.threshold:+.1f}")
    print()
    print("  优化建议：")
    if result.lon_accel_violations:
        print("    • 纵向加速度超限 → 调低 max_acceleration / max_deceleration 参数")
    if result.jerk_violations:
        print("    • Jerk 超限 → 增大 jerk_limit 约束，或提升速度规划平滑度")
    if result.lat_accel_violations:
        print("    • 横向加速度超限 → 降低过弯速度限制，或增大转向平滑约束")
    if result.hard_brake_count > 0:
        print("    • 急刹车 → grep stop_reason 日志，确认 TrafficRule 触发是否合理")
    if not (result.lon_accel_violations or result.jerk_violations
            or result.lat_accel_violations or result.hard_brake_count):
        print("    • 所有体感指标正常，建议重点关注场景通过率（性能指标）")
    print("=" * 62)


def save_json(result: EvalResult, path: str):
    all_violations = sorted(
        result.lon_accel_violations + result.jerk_violations +
        result.lat_accel_violations + result.hard_brake_events,
        key=lambda v: v.timestamp,
    )
    data = {
        "duration_sec":               result.duration_sec,
        "total_frames":               result.total_frames,
        "max_speed_ms":               result.max_speed,
        "avg_speed_ms":               result.avg_speed,
        "max_lon_accel":              result.max_lon_accel,
        "lon_accel_violation_count":  len(result.lon_accel_violations),
        "max_lon_jerk":               result.max_lon_jerk,
        "max_lon_jerk_time":          round(result.max_lon_jerk_time, 3),
        "jerk_p95":                   result.jerk_p95,
        "jerk_violation_count":       len(result.jerk_violations),
        "max_lat_accel":              result.max_lat_accel,
        "lat_accel_violation_count":  len(result.lat_accel_violations),
        "hard_brake_count":           result.hard_brake_count,
        "max_spin_deg":               result.max_spin_deg,
        "score_deduction_estimate":   result.score_deduction,
        "violation_events": [
            {
                "timestamp": v.timestamp,
                "metric":    v.metric,
                "value":     round(v.value, 4),
                "threshold": v.threshold,
            }
            for v in all_violations
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  JSON 已保存: {path}")


# ── 入口 ──────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Apollo EDU PnC 体感指标评估（cyber record）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python3 extract_metrics.py data/bag/test.record\n"
            "  python3 extract_metrics.py data/bag/test.record --json report.json\n"
            "  python3 extract_metrics.py data/bag/test.record --lon-accel-max 2.5\n"
        ),
    )
    p.add_argument("record",
                   help="cyber record 文件路径")
    p.add_argument("--lon-accel-max", type=float, default=DEFAULT_LON_ACCEL_MAX,
                   metavar="N",
                   help=f"纵向加速度上限 m/s²（默认 {DEFAULT_LON_ACCEL_MAX}）")
    p.add_argument("--jerk-max", type=float, default=DEFAULT_LON_JERK_MAX,
                   metavar="N",
                   help=f"纵向 Jerk 上限 m/s³（默认 {DEFAULT_LON_JERK_MAX}）")
    p.add_argument("--lat-accel-max", type=float, default=DEFAULT_LAT_ACCEL_MAX,
                   metavar="N",
                   help=f"横向加速度上限 m/s²（默认 {DEFAULT_LAT_ACCEL_MAX}）")
    p.add_argument("--hard-brake", type=float, default=DEFAULT_HARD_BRAKE,
                   metavar="N",
                   help=f"急刹车减速度阈值 m/s²（默认 {DEFAULT_HARD_BRAKE}）")
    p.add_argument("--spin-max", type=float, default=DEFAULT_SPIN_MAX,
                   metavar="N",
                   help=f"角速度上限 deg/s（默认 {DEFAULT_SPIN_MAX}）")
    p.add_argument("--interval", type=float, default=0.1,
                   metavar="SEC",
                   help="重采样间隔（默认 0.1，与官方评分引擎对齐；0 表示不重采样）")
    p.add_argument("--json", metavar="FILE",
                   help="同时输出 JSON 报告（如 report.json）")
    return p


def main():
    args = _build_parser().parse_args()

    print(f"[extract_metrics] 读取 record: {args.record}")
    raw = _read_localization(args.record)
    if not raw:
        print(f"[ERROR] 未读取到 {LOCALIZATION_CHANNEL} 数据，"
              "请确认 record 文件包含定位 channel。")
        sys.exit(1)

    print(f"[extract_metrics] 共 {len(raw)} 帧定位数据，重采样到 {args.interval:.2f}s ...")
    frames = _compute_frames(_resample(raw, args.interval))
    result = evaluate(frames, args)
    print_report(result, args, args.record)

    if args.json:
        save_json(result, args.json)


if __name__ == "__main__":
    main()
