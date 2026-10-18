#!/usr/bin/env python3
"""Generate Apollo record inventory, parsed CSV signals, plots, and a report."""

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
sys.path.insert(0, "/opt/apollo/neo/python")

from cyber.python.cyber_py3 import record
from google.protobuf.message import DecodeError

from modules.common_msgs.chassis_msgs import chassis_pb2
from modules.common_msgs.control_msgs import control_cmd_pb2
from modules.common_msgs.control_msgs import control_interactive_msg_pb2
from modules.common_msgs.guardian_msgs import guardian_pb2
from modules.common_msgs.localization_msgs import imu_pb2 as localization_imu_pb2
from modules.common_msgs.localization_msgs import localization_pb2
from modules.common_msgs.perception_msgs import perception_obstacle_pb2
from modules.common_msgs.planning_msgs import planning_pb2
from modules.common_msgs.prediction_msgs import prediction_obstacle_pb2
from modules.common_msgs.sensor_msgs import gnss_best_pose_pb2
from modules.common_msgs.sensor_msgs import imu_pb2 as sensor_imu_pb2
from modules.common_msgs.sensor_msgs import ins_pb2


PARSERS = {
    "/apollo/canbus/chassis": chassis_pb2.Chassis,
    "/apollo/control": control_cmd_pb2.ControlCommand,
    "/apollo/control/interactive": control_interactive_msg_pb2.ControlInteractiveMsg,
    "/apollo/guardian": guardian_pb2.GuardianCommand,
    "/apollo/localization/pose": localization_pb2.LocalizationEstimate,
    "/apollo/perception/obstacles": perception_obstacle_pb2.PerceptionObstacles,
    "/apollo/planning": planning_pb2.ADCTrajectory,
    "/apollo/prediction": prediction_obstacle_pb2.PredictionObstacles,
    "/apollo/sensor/gnss/best_pose": gnss_best_pose_pb2.GnssBestPose,
    "/apollo/sensor/gnss/corrected_imu": localization_imu_pb2.CorrectedImu,
    "/apollo/sensor/gnss/imu": sensor_imu_pb2.Imu,
    "/apollo/sensor/gnss/ins_stat": ins_pb2.InsStat,
}

DEFAULT_CHANNELS = (
    "/apollo/canbus/chassis",
    "/apollo/control",
    "/apollo/control/interactive",
    "/apollo/guardian",
    "/apollo/localization/pose",
    "/apollo/perception/obstacles",
    "/apollo/planning",
    "/apollo/prediction",
    "/apollo/sensor/gnss/best_pose",
    "/apollo/sensor/gnss/corrected_imu",
    "/apollo/sensor/gnss/imu",
    "/apollo/sensor/gnss/ins_stat",
)

MODULE_PATTERNS = (
    ("planning", "/apollo/planning"),
    ("control", "/apollo/control"),
    ("canbus", "/apollo/canbus"),
    ("localization", "/apollo/localization"),
    ("perception", "/apollo/perception"),
    ("prediction", "/apollo/prediction"),
    ("guardian", "/apollo/guardian"),
    ("safety", "/apollo/safety"),
    ("gnss", "/apollo/sensor/gnss"),
    ("lidar", "/apollo/sensor/lidar"),
    ("hesai", "/apollo/sensor/hesai"),
    ("monitor", "/apollo/monitor"),
    ("statistics", "/apollo/statistics"),
    ("tf", "/tf"),
)


def discover_records(inputs):
    paths = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and (".record" in child.name or child.suffix == ".bag"):
                    paths.append(child)
        elif path.is_file():
            paths.append(path)
        else:
            raise FileNotFoundError(str(path))

    seen = set()
    deduped = []
    for path in paths:
        # Use absolute() instead of resolve() to avoid following symlinks
        # back to paths with non-ASCII characters that break Cyber RecordReader.
        resolved = str(path.absolute())
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path.absolute())
    return deduped


def module_for_channel(channel):
    for module, prefix in MODULE_PATTERNS:
        if channel == prefix or channel.startswith(prefix + "/"):
            return module
    return "other"


def new_channel_stats(channel):
    return {
        "channel": channel,
        "module": module_for_channel(channel),
        "message_type": "",
        "messages": 0,
        "first_time": None,
        "last_time": None,
        "records": set(),
    }


def get_ts(message):
    return int(getattr(message, "timestamp", message[2] if len(message) > 2 else 0))


def get_topic(message):
    return getattr(message, "topic", message[0])


def get_payload(message):
    return getattr(message, "message", message[1])


def enum_name(enum_type, value):
    if enum_type is None:
        return value
    try:
        return enum_type.values_by_number[int(value)].name
    except Exception:
        return value


def safe_float(value):
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except Exception:
        return None


def append_numeric(row, key, value):
    number = safe_float(value)
    if number is not None:
        row[key] = number


def parse_message(channel, payload):
    proto_cls = PARSERS.get(channel)
    if proto_cls is None:
        return None
    message = proto_cls()
    try:
        message.ParseFromString(payload)
    except DecodeError:
        return None
    return message


def row_from_message(channel, message, vehicle_position=None):
    row = {}
    if channel == "/apollo/canbus/chassis":
        append_numeric(row, "speed_mps", message.speed_mps)
        append_numeric(row, "throttle_pct", message.throttle_percentage)
        append_numeric(row, "brake_pct", message.brake_percentage)
        append_numeric(row, "steering_pct", message.steering_percentage)
        append_numeric(row, "steering_torque_nm", message.steering_torque_nm)
        row["driving_mode"] = enum_name(
            message.DESCRIPTOR.fields_by_name["driving_mode"].enum_type,
            message.driving_mode,
        )
        row["gear_location"] = enum_name(
            message.DESCRIPTOR.fields_by_name["gear_location"].enum_type,
            message.gear_location,
        )
        row["error_code"] = enum_name(
            message.DESCRIPTOR.fields_by_name["error_code"].enum_type,
            message.error_code,
        )
    elif channel == "/apollo/control":
        append_numeric(row, "throttle_cmd", message.throttle)
        append_numeric(row, "brake_cmd", message.brake)
        append_numeric(row, "steering_target", message.steering_target)
        append_numeric(row, "steering_rate", message.steering_rate)
        append_numeric(row, "speed_cmd", message.speed)
        append_numeric(row, "acceleration_cmd", message.acceleration)
        row["driving_mode"] = enum_name(
            message.DESCRIPTOR.fields_by_name["driving_mode"].enum_type,
            message.driving_mode,
        )
        row["gear_location"] = enum_name(
            message.DESCRIPTOR.fields_by_name["gear_location"].enum_type,
            message.gear_location,
        )
        row["is_in_safe_mode"] = bool(message.is_in_safe_mode)
    elif channel == "/apollo/control/interactive":
        row["replan_request"] = bool(message.replan_request)
        row["is_need_safety_check"] = bool(message.is_need_safety_check)
        row["replan_req_reason_code"] = enum_name(
            message.DESCRIPTOR.fields_by_name["replan_req_reason_code"].enum_type,
            message.replan_req_reason_code,
        )
        if message.replan_request_reason:
            row["replan_request_reason"] = message.replan_request_reason
    elif channel == "/apollo/guardian":
        if message.HasField("control_command"):
            command = message.control_command
            append_numeric(row, "throttle_cmd", command.throttle)
            append_numeric(row, "brake_cmd", command.brake)
            append_numeric(row, "steering_target", command.steering_target)
            append_numeric(row, "speed_cmd", command.speed)
            row["is_in_safe_mode"] = bool(command.is_in_safe_mode)
    elif channel == "/apollo/localization/pose":
        pose = message.pose
        append_numeric(row, "x", pose.position.x)
        append_numeric(row, "y", pose.position.y)
        append_numeric(row, "z", pose.position.z)
        append_numeric(row, "heading", pose.heading)
        if pose.HasField("linear_velocity"):
            append_numeric(row, "velocity_x", pose.linear_velocity.x)
            append_numeric(row, "velocity_y", pose.linear_velocity.y)
            append_numeric(row, "speed_mps", math.hypot(pose.linear_velocity.x, pose.linear_velocity.y))
        if pose.HasField("linear_acceleration"):
            append_numeric(row, "accel_x", pose.linear_acceleration.x)
            append_numeric(row, "accel_y", pose.linear_acceleration.y)
        if pose.HasField("angular_velocity"):
            append_numeric(row, "angular_velocity_z", pose.angular_velocity.z)
    elif channel == "/apollo/planning":
        append_numeric(row, "total_path_length", message.total_path_length)
        append_numeric(row, "total_path_time", message.total_path_time)
        row["trajectory_points"] = len(message.trajectory_point)
        row["is_replan"] = bool(message.is_replan)
        row["is_collision"] = bool(message.is_collision)
        row["trajectory_type"] = enum_name(
            message.DESCRIPTOR.fields_by_name["trajectory_type"].enum_type,
            message.trajectory_type,
        )
        row["estop"] = bool(message.HasField("estop") and message.estop.is_estop)
        if message.trajectory_point:
            first_point = message.trajectory_point[0]
            append_numeric(row, "first_v", first_point.v)
            append_numeric(row, "first_a", first_point.a)
            if first_point.HasField("path_point"):
                append_numeric(row, "first_kappa", first_point.path_point.kappa)
                append_numeric(row, "first_x", first_point.path_point.x)
                append_numeric(row, "first_y", first_point.path_point.y)
    elif channel == "/apollo/perception/obstacles":
        row["obstacle_count"] = len(message.perception_obstacle)
        moving_count = 0
        min_distance = None
        for obstacle in message.perception_obstacle:
            speed = math.hypot(obstacle.velocity.x, obstacle.velocity.y) if obstacle.HasField("velocity") else 0.0
            if speed > 0.3:
                moving_count += 1
            if obstacle.HasField("position") and vehicle_position is not None:
                distance = math.hypot(
                    obstacle.position.x - vehicle_position[0],
                    obstacle.position.y - vehicle_position[1],
                )
                min_distance = distance if min_distance is None else min(min_distance, distance)
        row["moving_obstacle_count"] = moving_count
        append_numeric(row, "nearest_obstacle_dist", min_distance)
    elif channel == "/apollo/prediction":
        row["prediction_obstacle_count"] = len(message.prediction_obstacle)
    elif channel == "/apollo/sensor/gnss/corrected_imu":
        if message.HasField("imu"):
            pose = message.imu
            if pose.HasField("linear_acceleration"):
                append_numeric(row, "linear_accel_x", pose.linear_acceleration.x)
                append_numeric(row, "linear_accel_y", pose.linear_acceleration.y)
                append_numeric(row, "linear_accel_z", pose.linear_acceleration.z)
            if pose.HasField("angular_velocity"):
                append_numeric(row, "angular_velocity_x", pose.angular_velocity.x)
                append_numeric(row, "angular_velocity_y", pose.angular_velocity.y)
                append_numeric(row, "angular_velocity_z", pose.angular_velocity.z)
            if pose.HasField("linear_acceleration_vrf"):
                append_numeric(row, "linear_accel_vrf_x", pose.linear_acceleration_vrf.x)
                append_numeric(row, "linear_accel_vrf_y", pose.linear_acceleration_vrf.y)
                append_numeric(row, "linear_accel_vrf_z", pose.linear_acceleration_vrf.z)
            if pose.HasField("angular_velocity_vrf"):
                append_numeric(row, "angular_velocity_vrf_x", pose.angular_velocity_vrf.x)
                append_numeric(row, "angular_velocity_vrf_y", pose.angular_velocity_vrf.y)
                append_numeric(row, "angular_velocity_vrf_z", pose.angular_velocity_vrf.z)
    elif channel == "/apollo/sensor/gnss/imu":
        append_numeric(row, "linear_accel_x", message.linear_acceleration.x)
        append_numeric(row, "linear_accel_y", message.linear_acceleration.y)
        append_numeric(row, "linear_accel_z", message.linear_acceleration.z)
        append_numeric(row, "angular_velocity_x", message.angular_velocity.x)
        append_numeric(row, "angular_velocity_y", message.angular_velocity.y)
        append_numeric(row, "angular_velocity_z", message.angular_velocity.z)
    elif channel == "/apollo/sensor/gnss/best_pose":
        append_numeric(row, "latitude", message.latitude)
        append_numeric(row, "longitude", message.longitude)
        append_numeric(row, "height_msl", message.height_msl)
        append_numeric(row, "num_sats_tracked", message.num_sats_tracked)
        append_numeric(row, "num_sats_in_solution", message.num_sats_in_solution)
        row["sol_status"] = enum_name(
            message.DESCRIPTOR.fields_by_name["sol_status"].enum_type,
            message.sol_status,
        )
        row["sol_type"] = enum_name(
            message.DESCRIPTOR.fields_by_name["sol_type"].enum_type,
            message.sol_type,
        )
    elif channel == "/apollo/sensor/gnss/ins_stat":
        append_numeric(row, "ins_status", message.ins_status)
        append_numeric(row, "pos_type", message.pos_type)
    return row


def collect(records, target_channels, max_points_per_channel, inventory_only=False, full_scan=False):
    channel_stats = {}
    selected = set(target_channels)
    series = defaultdict(list)

    for record_path in records:
        reader = record.RecordReader(str(record_path))
        for channel in reader.get_channellist():
            stats = channel_stats.setdefault(channel, new_channel_stats(channel))
            try:
                stats["messages"] += int(reader.get_messagenumber(channel))
            except Exception:
                pass
            try:
                stats["message_type"] = reader.get_messagetype(channel)
            except Exception:
                pass
            stats["records"].add(record_path.name)

    if inventory_only:
        return channel_stats, series

    vehicle_position = None
    for record_path in records:
        reader = record.RecordReader(str(record_path))
        for item in reader.read_messages():
            channel = get_topic(item)
            if not full_scan and channel not in selected:
                continue

            stats = channel_stats.setdefault(channel, new_channel_stats(channel))
            timestamp = get_ts(item) / 1e9
            stats["first_time"] = timestamp if stats["first_time"] is None else min(stats["first_time"], timestamp)
            stats["last_time"] = timestamp if stats["last_time"] is None else max(stats["last_time"], timestamp)

            if channel not in selected or channel not in PARSERS:
                continue
            if max_points_per_channel and len(series[channel]) >= max_points_per_channel:
                continue

            parsed = parse_message(channel, get_payload(item))
            if parsed is None:
                continue
            row = row_from_message(channel, parsed, vehicle_position)
            if not row:
                continue
            if channel == "/apollo/localization/pose":
                vehicle_position = (parsed.pose.position.x, parsed.pose.position.y)
            row["time_sec"] = timestamp
            row["record_file"] = record_path.name
            series[channel].append(row)

    return channel_stats, series


def normalize_times(series):
    first_time = None
    for rows in series.values():
        for row in rows:
            first_time = row["time_sec"] if first_time is None else min(first_time, row["time_sec"])
    if first_time is None:
        return
    for rows in series.values():
        for row in rows:
            row["t"] = row["time_sec"] - first_time


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fields = set()
        for row in rows:
            fields.update(row.keys())
        leading = [key for key in ("t", "time_sec", "record_file") if key in fields]
        fieldnames = leading + sorted(field for field in fields if field not in leading)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def channel_filename(channel):
    return channel.strip("/").replace("/", "__") or "root"


def build_channel_rows(channel_stats, selected, series):
    rows = []
    for channel, stats in sorted(channel_stats.items()):
        duration = None
        hz = None
        if stats["first_time"] is not None and stats["last_time"] is not None:
            duration = max(0.0, stats["last_time"] - stats["first_time"])
            if duration > 0:
                hz = stats["messages"] / duration
        rows.append({
            "module": stats["module"],
            "channel": channel,
            "message_type": stats["message_type"],
            "messages": stats["messages"],
            "duration_sec": "" if duration is None else f"{duration:.3f}",
            "hz": "" if hz is None else f"{hz:.3f}",
            "has_parser": channel in PARSERS,
            "selected": channel in selected,
            "parsed_rows": len(series.get(channel, [])),
            "record_files": ";".join(sorted(stats["records"])),
        })
    return rows


def build_module_rows(channel_rows):
    totals = defaultdict(int)
    channels = defaultdict(int)
    for row in channel_rows:
        totals[row["module"]] += int(row["messages"])
        channels[row["module"]] += 1
    return [
        {"module": module, "channels": channels[module], "messages": messages}
        for module, messages in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    ]


def numeric_series(rows, key):
    xs, ys = [], []
    for row in rows:
        value = safe_float(row.get(key))
        if "t" in row and value is not None:
            xs.append(row["t"])
            ys.append(value)
    return xs, ys


def plot_lines(plot_path, title, lines):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(12, 5))
    plotted = False
    for label, xs, ys in lines:
        if xs and ys:
            axis.plot(xs, ys, label=label, linewidth=1.2)
            plotted = True
    if not plotted:
        plt.close(fig)
        return False
    axis.set_title(title)
    axis.set_xlabel("time (s)")
    axis.grid(True, alpha=0.3)
    axis.legend(loc="best")
    fig.tight_layout()
    fig.savefig(plot_path, dpi=140)
    plt.close(fig)
    return True


def create_plots(plot_dir, series):
    plot_dir.mkdir(parents=True, exist_ok=True)
    chassis = series.get("/apollo/canbus/chassis", [])
    control = series.get("/apollo/control", [])
    planning = series.get("/apollo/planning", [])
    localization = series.get("/apollo/localization/pose", [])
    perception = series.get("/apollo/perception/obstacles", [])
    imu = series.get("/apollo/sensor/gnss/imu", [])
    corrected_imu = series.get("/apollo/sensor/gnss/corrected_imu", [])
    best_pose = series.get("/apollo/sensor/gnss/best_pose", [])

    specs = (
        ("vehicle_speed.png", "Vehicle Speed", (
            ("chassis speed", *numeric_series(chassis, "speed_mps")),
            ("localization speed", *numeric_series(localization, "speed_mps")),
            ("planning first_v", *numeric_series(planning, "first_v")),
        )),
        ("control_commands.png", "Control Commands", (
            ("throttle cmd", *numeric_series(control, "throttle_cmd")),
            ("brake cmd", *numeric_series(control, "brake_cmd")),
            ("steering target", *numeric_series(control, "steering_target")),
        )),
        ("planning_overview.png", "Planning Overview", (
            ("trajectory points", *numeric_series(planning, "trajectory_points")),
            ("total path time", *numeric_series(planning, "total_path_time")),
            ("first acceleration", *numeric_series(planning, "first_a")),
        )),
        ("obstacles.png", "Perception Obstacles", (
            ("obstacle count", *numeric_series(perception, "obstacle_count")),
            ("moving obstacle count", *numeric_series(perception, "moving_obstacle_count")),
            ("nearest obstacle dist", *numeric_series(perception, "nearest_obstacle_dist")),
        )),
        ("imu.png", "GNSS IMU", (
            ("imu angular z", *numeric_series(imu, "angular_velocity_z")),
            ("corrected imu angular z", *numeric_series(corrected_imu, "angular_velocity_z")),
            ("imu accel x", *numeric_series(imu, "linear_accel_x")),
        )),
        ("gnss_quality.png", "GNSS Quality", (
            ("sats tracked", *numeric_series(best_pose, "num_sats_tracked")),
            ("sats in solution", *numeric_series(best_pose, "num_sats_in_solution")),
        )),
    )

    plots = []
    for filename, title, lines in specs:
        path = plot_dir / filename
        if plot_lines(path, title, lines):
            plots.append(path)
    return plots


def sample_value(rows, key):
    values = []
    for row in rows:
        value = safe_float(row.get(key))
        if value is not None:
            values.append(value)
    if not values:
        return ""
    return f"min={min(values):.3f}, max={max(values):.3f}, avg={sum(values) / len(values):.3f}"


def write_markdown(path, records, channel_rows, module_rows, series, plots, selected):
    parsed_channels = sorted(series.keys())
    total_messages = sum(int(row["messages"]) for row in channel_rows)
    lines = [
        "# Apollo Record Channel Report\n",
        "\n",
        "## Inputs\n",
        "\n",
    ]
    lines.extend(f"- `{record_path}`\n" for record_path in records)
    lines.extend([
        "\n",
        "## Summary\n",
        "\n",
        f"- Record files: {len(records)}\n",
        f"- Total channels: {len(channel_rows)}\n",
        f"- Total indexed messages: {total_messages}\n",
        f"- Selected channels: {len(selected)}\n",
        f"- Parsed channels: {len(parsed_channels)}\n",
        "\n",
        "## Module Inventory\n",
        "\n",
        "| Module | Channels | Messages |\n",
        "|-|-:|-:|\n",
    ])
    for row in module_rows:
        lines.append(f"| {row['module']} | {row['channels']} | {row['messages']} |\n")

    lines.extend([
        "\n",
        "## Parsed Signals\n",
        "\n",
    ])
    if not parsed_channels:
        lines.append("No parsed signal rows were generated. Check selected channels or use `--all-parsed-channels`.\n")
    for channel in parsed_channels:
        rows = series[channel]
        keys = sorted({key for row in rows for key in row if key not in ("t", "time_sec", "record_file")})
        lines.extend([
            f"### `{channel}`\n",
            "\n",
            f"- rows: {len(rows)}\n",
        ])
        summaries = []
        for key in keys:
            summary = sample_value(rows, key)
            if summary:
                summaries.append(f"- `{key}` {summary}\n")
        lines.extend(summaries[:12])
        lines.append("\n")

    top_channels = sorted(channel_rows, key=lambda row: int(row["messages"]), reverse=True)[:20]
    lines.extend([
        "## Top Channels\n",
        "\n",
        "| Module | Channel | Type | Messages | Parsed rows |\n",
        "|-|-|-|-:|-:|\n",
    ])
    for row in top_channels:
        lines.append(
            f"| {row['module']} | `{row['channel']}` | `{row['message_type']}` | "
            f"{row['messages']} | {row['parsed_rows']} |\n"
        )

    lines.extend([
        "\n",
        "## Artifacts\n",
        "\n",
        "- `channel_summary.csv`\n",
        "- `module_summary.csv`\n",
        "- `csv/*.csv`\n",
    ])
    for plot in plots:
        lines.append(f"- `{plot.relative_to(path.parent)}`\n")

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text("".join(lines), encoding="utf-8")
    os.replace(temp_path, path)


def write_outputs(out_dir, records, channel_stats, series, selected):
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_dir = out_dir / "csv"
    plot_dir = out_dir / "plots"
    csv_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)

    channel_rows = build_channel_rows(channel_stats, selected, series)
    module_rows = build_module_rows(channel_rows)
    write_csv(
        out_dir / "channel_summary.csv",
        channel_rows,
        [
            "module",
            "channel",
            "message_type",
            "messages",
            "duration_sec",
            "hz",
            "has_parser",
            "selected",
            "parsed_rows",
            "record_files",
        ],
    )
    write_csv(out_dir / "module_summary.csv", module_rows, ["module", "channels", "messages"])

    for channel, rows in sorted(series.items()):
        write_csv(csv_dir / f"{channel_filename(channel)}.csv", rows)

    plots = create_plots(plot_dir, series)
    write_markdown(out_dir / "record_report.md", records, channel_rows, module_rows, series, plots, selected)
    return channel_rows, module_rows, plots


def parse_channels(args):
    if args.all_parsed_channels:
        return tuple(PARSERS)
    if args.channel:
        channels = []
        for value in args.channel:
            for channel in value.split(","):
                channel = channel.strip()
                if channel:
                    channels.append(channel)
        return tuple(dict.fromkeys(channels))
    return DEFAULT_CHANNELS


def main():
    parser = argparse.ArgumentParser(description="Generate Apollo record channel CSV/plot/report artifacts.")
    parser.add_argument("inputs", nargs="+", help="Record files or directories containing record shards")
    parser.add_argument("-o", "--output", default="", help="Output directory")
    parser.add_argument("--channel", action="append", default=[], help="Selected channel to parse; repeatable or comma-separated")
    parser.add_argument("--all-parsed-channels", action="store_true", help="Parse every channel with a built-in parser")
    parser.add_argument("--inventory-only", action="store_true", help="Only write channel/module inventories; skip streaming and plots")
    parser.add_argument("--full-scan", action="store_true", help="Collect first/last timestamp and Hz for every channel")
    parser.add_argument(
        "--max-points-per-channel",
        type=int,
        default=0,
        help="Limit parsed rows per channel; default parses all selected rows",
    )
    args = parser.parse_args()

    records = discover_records(args.inputs)
    if not records:
        raise SystemExit("No record files found.")

    selected = parse_channels(args)
    unknown = [channel for channel in selected if channel not in PARSERS]
    if unknown:
        print("warning: no built-in parser for selected channel(s): " + ", ".join(unknown), file=sys.stderr)

    out_dir = Path(args.output) if args.output else Path("/apollo_workspace/data/record_reports") / records[0].stem
    channel_stats, series = collect(
        records,
        target_channels=selected,
        max_points_per_channel=args.max_points_per_channel,
        inventory_only=args.inventory_only,
        full_scan=args.full_scan,
    )
    normalize_times(series)
    channel_rows, _module_rows, plots = write_outputs(out_dir, records, channel_stats, series, set(selected))

    print(f"records={len(records)}")
    print(f"channels={len(channel_rows)}")
    print(f"selected_channels={len(selected)}")
    print(f"parsed_channels={len(series)}")
    print(f"plots={len(plots)}")
    print(f"output={out_dir}")
    print(f"report={out_dir / 'record_report.md'}")


if __name__ == "__main__":
    main()
