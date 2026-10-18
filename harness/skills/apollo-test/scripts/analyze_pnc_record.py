#!/usr/bin/env python3
"""Analyze PnC simulation record to diagnose planning failures."""

import sys
import os
import math

sys.path.insert(0, '/opt/apollo/neo/python')
sys.path.insert(0, '/opt/apollo/neo/src')

from cyber.python.cyber_py3.record import RecordReader
from google.protobuf import descriptor_pool, symbol_database
from modules.common_msgs.planning_msgs import planning_pb2
from modules.common_msgs.prediction_msgs import prediction_obstacle_pb2
from modules.common_msgs.localization_msgs import localization_pb2
from modules.common_msgs.chassis_msgs import chassis_pb2


CHANNEL_PARSERS = {
    '/apollo/planning': planning_pb2.ADCTrajectory,
    '/apollo/prediction': prediction_obstacle_pb2.PredictionObstacles,
    '/apollo/localization/pose': localization_pb2.LocalizationEstimate,
    '/apollo/canbus/chassis': chassis_pb2.Chassis,
}


def parse_record(record_file):
    reader = RecordReader(record_file)
    data = {ch: [] for ch in CHANNEL_PARSERS}
    for msg in reader.read_messages():
        if msg.topic in CHANNEL_PARSERS:
            proto = CHANNEL_PARSERS[msg.topic]()
            proto.ParseFromString(msg.message)
            data[msg.topic].append((msg.timestamp, proto))
    return data


def analyze_planning(planning_msgs):
    """Analyze planning trajectory for failures."""
    issues = []
    for ts, traj in planning_msgs:
        t_sec = ts / 1e9
        # EStop
        if traj.HasField('estop') and traj.estop.is_estop:
            issues.append({
                'time': t_sec,
                'type': 'ESTOP',
                'detail': traj.estop.reason,
            })
        # Fallback trajectory
        if traj.HasField('trajectory_type'):
            if traj.trajectory_type in (
                planning_pb2.ADCTrajectory.PATH_FALLBACK,
                planning_pb2.ADCTrajectory.SPEED_FALLBACK,
            ):
                issues.append({
                    'time': t_sec,
                    'type': 'FALLBACK',
                    'detail': planning_pb2.ADCTrajectory.TrajectoryType.Name(
                        traj.trajectory_type),
                })
        # Empty trajectory
        if len(traj.trajectory_point) == 0 and not (
                traj.HasField('estop') and traj.estop.is_estop):
            issues.append({
                'time': t_sec,
                'type': 'EMPTY_TRAJECTORY',
                'detail': 'No trajectory points generated',
            })
        # Main decision stop
        if traj.HasField('decision') and traj.decision.HasField('main_decision'):
            md = traj.decision.main_decision
            if md.HasField('stop'):
                issues.append({
                    'time': t_sec,
                    'type': 'MAIN_STOP',
                    'detail': f'reason={md.stop.reason_code} "{md.stop.reason}"',
                })
            elif md.HasField('not_ready'):
                issues.append({
                    'time': t_sec,
                    'type': 'NOT_READY',
                    'detail': md.not_ready.reason if md.not_ready.HasField('reason') else '',
                })
    return issues


def analyze_obstacles(prediction_msgs, planning_msgs):
    """Find obstacles that block the ego vehicle."""
    blocking = []
    for ts, pred in prediction_msgs:
        t_sec = ts / 1e9
        for obs in pred.prediction_obstacle:
            perc = obs.perception_obstacle
            if obs.is_static and perc.HasField('position'):
                blocking.append({
                    'time': t_sec,
                    'id': perc.id,
                    'type': perc.Type.Name(perc.type) if perc.HasField('type') else 'UNKNOWN',
                    'x': perc.position.x,
                    'y': perc.position.y,
                    'is_static': True,
                })
    # Correlate with planning object decisions
    obstacle_decisions = {}
    for ts, traj in planning_msgs:
        if not traj.HasField('decision'):
            continue
        obj_dec = traj.decision.object_decision
        for dec in obj_dec.decision:
            for od in dec.object_decision:
                tag = od.WhichOneof('object_tag')
                if tag in ('stop', 'yield', 'nudge'):
                    key = dec.id
                    if key not in obstacle_decisions:
                        obstacle_decisions[key] = []
                    obstacle_decisions[key].append({
                        'time': ts / 1e9,
                        'decision': tag,
                    })
    return blocking, obstacle_decisions


def analyze_ego_state(localization_msgs, chassis_msgs):
    """Check if ego is stuck."""
    stuck_periods = []
    if len(chassis_msgs) < 2:
        return stuck_periods
    stuck_start = None
    for i, (ts, chassis) in enumerate(chassis_msgs):
        speed = chassis.speed_mps
        t_sec = ts / 1e9
        if abs(speed) < 0.1:
            if stuck_start is None:
                stuck_start = t_sec
        else:
            if stuck_start and (t_sec - stuck_start) > 3.0:
                stuck_periods.append((stuck_start, t_sec))
            stuck_start = None
    if stuck_start:
        last_t = chassis_msgs[-1][0] / 1e9
        if (last_t - stuck_start) > 3.0:
            stuck_periods.append((stuck_start, last_t))
    return stuck_periods


def suggest_code_scope(issues, obstacle_decisions, stuck_periods):
    """Based on analysis, suggest which code areas to investigate."""
    suggestions = set()
    for issue in issues:
        if issue['type'] == 'ESTOP':
            suggestions.add('modules/planning/planning_interface_base/scenario_base/ (scenario transition logic)')
            suggestions.add('modules/planning/planning_component/ (planning main entry)')
        elif issue['type'] == 'FALLBACK':
            if 'PATH' in issue['detail']:
                suggestions.add('modules/planning/tasks/path_*/ (path planning tasks)')
                suggestions.add('modules/planning/tasks/fallback_path/')
            else:
                suggestions.add('modules/planning/tasks/speed_*/ (speed planning tasks)')
                suggestions.add('modules/planning/tasks/fallback_speed/')
        elif issue['type'] == 'MAIN_STOP':
            reason = issue['detail']
            if 'OBSTACLE' in reason or 'HEAD_VEHICLE' in reason:
                suggestions.add('modules/planning/tasks/deciders/path_decider/')
                suggestions.add('modules/planning/tasks/deciders/speed_decider/')
            if 'SIGNAL' in reason:
                suggestions.add('modules/planning/scenarios/traffic_light_*/')
                suggestions.add('modules/planning/traffic_rules/')
            if 'STOP_SIGN' in reason:
                suggestions.add('modules/planning/scenarios/stop_sign*/')
            if 'DESTINATION' in reason:
                suggestions.add('modules/planning/scenarios/pull_over*/')
        elif issue['type'] == 'EMPTY_TRAJECTORY':
            suggestions.add('modules/planning/planners/public_road/scenario_manager.cc')
            suggestions.add('modules/planning/planning_interface_base/scenario_base/stage.cc')

    for obs_id, decs in obstacle_decisions.items():
        dec_types = set(d['decision'] for d in decs)
        if 'nudge' in dec_types:
            suggestions.add('modules/planning/tasks/deciders/path_decider/ (nudge decision)')
            suggestions.add('modules/planning/tasks/path_*/ (path bounds with nudge)')
        if 'stop' in dec_types:
            suggestions.add('modules/planning/tasks/deciders/speed_decider/ (stop decision for obstacles)')
        if 'yield' in dec_types:
            suggestions.add('modules/planning/tasks/deciders/speed_decider/ (yield decision)')

    if stuck_periods:
        suggestions.add('modules/planning/tasks/speed_*/ (ego stuck, check speed optimization)')
        suggestions.add('modules/planning/scenarios/ (scenario/stage not advancing)')

    return sorted(suggestions)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <record_file>")
        sys.exit(1)

    record_file = sys.argv[1]
    if not os.path.exists(record_file):
        print(f"Error: {record_file} not found")
        sys.exit(1)

    print(f"=== Analyzing: {record_file} ===\n")
    data = parse_record(record_file)

    # Summary
    for ch, msgs in data.items():
        print(f"  {ch}: {len(msgs)} messages")
    print()

    # Planning issues
    planning_msgs = data['/apollo/planning']
    issues = analyze_planning(planning_msgs)
    print(f"=== Planning Issues ({len(issues)} found) ===")
    seen = set()
    for issue in issues:
        key = (issue['type'], issue['detail'])
        if key not in seen:
            seen.add(key)
            print(f"  [{issue['type']}] t={issue['time']:.2f}s: {issue['detail']}")
    print()

    # Obstacle analysis
    prediction_msgs = data['/apollo/prediction']
    blocking, obstacle_decisions = analyze_obstacles(prediction_msgs, planning_msgs)
    print(f"=== Obstacle Decisions ({len(obstacle_decisions)} obstacles with decisions) ===")
    for obs_id, decs in obstacle_decisions.items():
        dec_summary = {}
        for d in decs:
            dec_summary[d['decision']] = dec_summary.get(d['decision'], 0) + 1
        print(f"  obstacle [{obs_id}]: {dec_summary}")
    print()

    # Ego stuck
    chassis_msgs = data['/apollo/canbus/chassis']
    stuck_periods = analyze_ego_state(
        data['/apollo/localization/pose'], chassis_msgs)
    if stuck_periods:
        print(f"=== Ego Stuck Periods ===")
        for start, end in stuck_periods:
            print(f"  stuck from {start:.2f}s to {end:.2f}s ({end-start:.1f}s)")
        print()

    # Code scope suggestions
    suggestions = suggest_code_scope(issues, obstacle_decisions, stuck_periods)
    print(f"=== Suggested Code Scope to Investigate ===")
    for s in suggestions:
        print(f"  -> {s}")
    print()


if __name__ == '__main__':
    main()
