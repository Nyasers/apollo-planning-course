#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grading_system_py 主程序入口

支持两种数据源模式:
  1. bag模式: 读取仿真输出的 record/bag 文件进行离线评分
  2. channel模式: 订阅 Cyber 通道进行实时评分

使用方法:
  # 模式1: 读取bag文件
  python3 main.py --config grading_system/conf/grading_metrics_default.conf \
                  --mode bag \
                  --bag_file /apollo-simulator/output_data/1/1.output.bag

  # 模式2: 订阅Cyber通道 (需要在Apollo环境中运行)
  python3 main.py --config grading_system/conf/grading_metrics_default.conf \
                  --mode channel
"""

import argparse
import math
import sys
import time
from collections import deque
from typing import Dict, List, Optional, Any

from grading_system_py.condition.acceleration_handler import AccelerationConditionHandler
from grading_system_py.condition.speed_handler import SpeedConditionHandler
from grading_system_py.condition.on_road_handler import OnRoadConditionHandler
from grading_system_py.condition.obstacle_bypass_handler import ObstacleBypassConditionHandler
from grading_system_py.condition.ttc_handler import TtcConditionHandler
from grading_system_py.condition.centripetal_acceleration_handler import CentripetalAccelerationConditionHandler
from grading_system_py.condition.time_limit_handler import TimeLimitConditionHandler
from grading_system_py.condition.region_overlap_lw_handler import RegionOverlapLwConditionHandler
from grading_system_py.condition.object_overlap_handler import ObjectOverlapConditionHandler
from grading_system_py.condition.condition_handler_base import ConditionHandlerBase


# ============================================================
# 数据模型 (与 protobuf 兼容的轻量结构)
# ============================================================

class Object:
    """对应 GradingWorld.Object"""
    def __init__(self):
        self.id = ""
        self.position_x = 0.0
        self.position_y = 0.0
        self.heading = 0.0
        self.speed = 0.0
        self.speed_acceleration = 0.0
        self.speed_heading = 0.0
        self.spin = 0.0  # 角速度 (rad/s)
        self.length = 4.5
        self.width = 2.0
        self.height = 1.8
        self.front_edge_to_center = 2.25
        self.back_edge_to_center = 2.25
        self.polygon_point = []


class GradingWorld:
    """对应 proto GradingWorld"""
    def __init__(self):
        self.timestamp_sec = 0.0
        self.auto_driving_car = Object()
        self.object: List[Object] = []
        self.speed_limit: Optional[float] = None
        self.last_frame = False
        self.perceived_signal = []


class DetailedResult:
    """评分详细结果"""
    def __init__(self):
        self.timestamp = 0.0
        self.is_pass = True
        self.description = ""
        self.delta_score = 0.0

    def add_description(self, text: str):
        self.description += text


# ============================================================
# 配置解析
# ============================================================

class ConditionConfig:
    """条件配置 - 从 .conf 文件解析"""
    def __init__(self):
        self.condition_type = ""  # speed_condition, acceleration_condition, etc.
        # 通用字段
        self.name = ""
        self.use_score = False
        self.single_deduction = 5.0
        self.deduction_unit = 1.0
        # SpeedCondition
        self.min_speed = -0.5
        self.max_speed = 1000.0
        self.speed_limit_regions = []
        # AccelerationCondition
        self.min_acceleration = -1000.0
        self.max_acceleration = 1000.0
        self.duration = 2.0
        self.cut_in_distance = 1.0
        self.ttc = 5.0
        self.dist_stopline = 25.0
        self.light_turn_prev_time = 4.0
        # OnRoadCondition
        self.use_road_boundary = False
        # ObstacleBypassCondition
        self.obstacle_id = ""
        self.min_lateral_distance = 1.0
        self.test_range = None
        # TtcCondition
        self.time = 3.0
        # CentripetalAccelerationCondition
        self.max_centripetal_acceleration = 2.0
        # TimeLimitCondition
        self.timeout = 100.0
        # RegionOverlapLWCondition
        self.x = 0.0
        self.y = 0.0
        self.length = 5.0
        self.width = 12.0
        self.object_ids = ""
        self.require_fully_contain = False
        # ObjectOverlapCondition
        self.source_object_ids = ""
        self.target_object_ids = "*"
        self.distance = 0.05
        self.direction = "INCLUDE_BACK"
        self.ignore_object_ids = []


class MetricConfig:
    """单个 Metric 配置"""
    def __init__(self):
        self.name = ""
        self.description = ""
        self.is_critical = True
        self.require_all_time_pass = True
        self.once_pass_stay_pass = True
        self.get_deduction_score = True  # True=扣分制, False=得分制
        self.condition = ConditionConfig()


class GradingConfig:
    """完整评分配置"""
    def __init__(self):
        self.metrics: List[MetricConfig] = []
        self.use_score = False


def parse_config_file(config_path: str) -> GradingConfig:
    """
    解析评分配置文件，支持两种格式:
    - JSON 格式 (.json)
    - Protobuf text format (.conf)
    """
    if config_path.endswith('.json'):
        return _parse_json_config(config_path)
    else:
        return _parse_text_config(config_path)


def _parse_json_config(config_path: str) -> GradingConfig:
    """解析 JSON 格式的配置文件"""
    import json

    config = GradingConfig()

    with open(config_path, 'r') as f:
        data = json.load(f)

    config.use_score = data.get('use_score', False)

    for metric_data in data.get('metric', []):
        metric = MetricConfig()
        metric.name = metric_data.get('name', '')
        metric.description = metric_data.get('description', '')
        metric.is_critical = metric_data.get('is_critical', True)
        metric.require_all_time_pass = metric_data.get('require_all_time_pass', True)
        metric.once_pass_stay_pass = metric_data.get('once_pass_stay_pass', True)
        metric.get_deduction_score = metric_data.get('get_deduction_score', True)

        condition_data = metric_data.get('condition', {})
        cond = metric.condition

        # 检测 condition 类型
        supported_types = [
            'speed_condition', 'acceleration_condition', 'on_road_condition',
            'obstacle_bypass_condition', 'ttc_condition',
            'centripetal_acceleration_condition', 'time_limit_condition',
            'region_overlap_lw_condition', 'object_overlap_condition',
        ]
        found = False
        for ctype in supported_types:
            if ctype in condition_data:
                cond.condition_type = ctype
                _fill_condition_from_json(cond, ctype, condition_data[ctype])
                found = True
                break

        if found:
            config.metrics.append(metric)

    return config


def _fill_condition_from_json(cond: ConditionConfig, ctype: str, data: dict):
    """从 JSON dict 填充 condition 字段"""
    cond.name = data.get('name', '')
    cond.use_score = data.get('use_score', False)
    cond.single_deduction = data.get('single_deduction', cond.single_deduction)
    cond.deduction_unit = data.get('deduction_unit', cond.deduction_unit)

    if ctype == 'speed_condition':
        cond.min_speed = data.get('min_speed', cond.min_speed)
        cond.max_speed = data.get('max_speed', cond.max_speed)
        # 限速区域
        for region_data in data.get('speed_limit_regions', []):
            cond.speed_limit_regions.append(region_data)

    elif ctype == 'acceleration_condition':
        cond.min_acceleration = data.get('min_acceleration', cond.min_acceleration)
        cond.max_acceleration = data.get('max_acceleration', cond.max_acceleration)
        cond.duration = data.get('duration', cond.duration)
        cond.cut_in_distance = data.get('cut_in_distance', cond.cut_in_distance)
        cond.ttc = data.get('ttc', cond.ttc)
        cond.dist_stopline = data.get('dist_stopline', cond.dist_stopline)
        cond.light_turn_prev_time = data.get('light_turn_prev_time', cond.light_turn_prev_time)

    elif ctype == 'on_road_condition':
        cond.use_road_boundary = data.get('use_road_boundary', False)

    elif ctype == 'obstacle_bypass_condition':
        cond.obstacle_id = data.get('obstacle_id', '')
        cond.min_lateral_distance = data.get('min_lateral_distance', 1.0)
        cond.max_speed = data.get('max_speed', cond.max_speed)

    elif ctype == 'ttc_condition':
        cond.time = data.get('time', cond.time)

    elif ctype == 'centripetal_acceleration_condition':
        cond.max_centripetal_acceleration = data.get(
            'max_centripetal_acceleration', cond.max_centripetal_acceleration)

    elif ctype == 'time_limit_condition':
        cond.timeout = data.get('timeout', cond.timeout)

    elif ctype == 'region_overlap_lw_condition':
        cond.x = data.get('x', cond.x)
        cond.y = data.get('y', cond.y)
        cond.length = data.get('length', cond.length)
        cond.width = data.get('width', cond.width)
        cond.object_ids = data.get('object_ids', '')
        cond.require_fully_contain = data.get('require_fully_contain', False)

    elif ctype == 'object_overlap_condition':
        cond.source_object_ids = data.get('source_object_ids', '')
        cond.target_object_ids = data.get('target_object_ids', '*')
        cond.distance = data.get('distance', 0.05)
        cond.direction = data.get('direction', 'INCLUDE_BACK')
        cond.ignore_object_ids = data.get('ignore_object_ids', [])


def _parse_text_config(config_path: str) -> GradingConfig:
    """解析 protobuf text format 的配置文件 (.conf)"""
    config = GradingConfig()

    with open(config_path, 'r') as f:
        content = f.read()

    # 简易解析器 (处理 protobuf text format)
    metrics = _split_metrics(content)
    for metric_text in metrics:
        metric = _parse_metric(metric_text)
        if metric:
            config.metrics.append(metric)

    # 检查顶层 use_score
    if 'use_score: true' in content.split('metric')[0]:
        config.use_score = True

    return config


def _split_metrics(content: str) -> List[str]:
    """拆分出各个 metric 块"""
    metrics = []
    depth = 0
    current = ""
    in_metric = False

    i = 0
    while i < len(content):
        # 跳过注释
        if content[i] == '#':
            while i < len(content) and content[i] != '\n':
                i += 1
            continue

        if content[i:i+6] == 'metric' and depth == 0:
            in_metric = True
            # 找到开始的 {
            while i < len(content) and content[i] != '{':
                i += 1
            depth = 1
            current = ""
            i += 1
            continue

        if in_metric:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    metrics.append(current)
                    in_metric = False
                    i += 1
                    continue
            current += content[i]
        i += 1

    return metrics


def _parse_metric(text: str) -> Optional[MetricConfig]:
    """解析单个 metric 块"""
    metric = MetricConfig()

    metric.name = _extract_string(text, 'name')
    metric.description = _extract_string(text, 'description')
    metric.is_critical = _extract_bool(text, 'is_critical', True)
    metric.require_all_time_pass = _extract_bool(text, 'require_all_time_pass', True)

    # 检测 condition 类型
    condition_types = [
        'speed_condition', 'acceleration_condition', 'on_road_condition',
        'obstacle_bypass_condition', 'ttc_condition',
    ]
    for ctype in condition_types:
        if ctype in text:
            metric.condition.condition_type = ctype
            _parse_condition_fields(text, ctype, metric.condition)
            return metric

    # 不支持的 condition 类型，跳过
    return None


def _parse_condition_fields(text: str, ctype: str, cond: ConditionConfig):
    """解析 condition 内部字段"""
    # 提取 condition 块内容
    start = text.find(ctype)
    if start < 0:
        return
    brace_start = text.find('{', start)
    if brace_start < 0:
        return

    depth = 1
    i = brace_start + 1
    block = ""
    while i < len(text) and depth > 0:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                break
        block += text[i]
        i += 1

    cond.name = _extract_string(block, 'name') or cond.name
    cond.use_score = _extract_bool(block, 'use_score', False)
    cond.single_deduction = _extract_float(block, 'single_deduction', cond.single_deduction)
    cond.deduction_unit = _extract_float(block, 'deduction_unit', cond.deduction_unit)

    if ctype == 'speed_condition':
        cond.min_speed = _extract_float(block, 'min_speed', cond.min_speed)
        cond.max_speed = _extract_float(block, 'max_speed', cond.max_speed)
    elif ctype == 'acceleration_condition':
        cond.min_acceleration = _extract_float(block, 'min_acceleration', cond.min_acceleration)
        cond.max_acceleration = _extract_float(block, 'max_acceleration', cond.max_acceleration)
        cond.duration = _extract_float(block, 'duration', cond.duration)
        cond.cut_in_distance = _extract_float(block, 'cut_in_distance', cond.cut_in_distance)
        cond.ttc = _extract_float(block, 'ttc', cond.ttc)
        cond.dist_stopline = _extract_float(block, 'dist_stopline', cond.dist_stopline)
        cond.light_turn_prev_time = _extract_float(block, 'light_turn_prev_time', cond.light_turn_prev_time)
    elif ctype == 'on_road_condition':
        cond.use_road_boundary = _extract_bool(block, 'use_road_boundary', False)
    elif ctype == 'obstacle_bypass_condition':
        cond.obstacle_id = _extract_string(block, 'obstacle_id') or ""
        cond.min_lateral_distance = _extract_float(block, 'min_lateral_distance', 1.0)
        cond.max_speed = _extract_float(block, 'max_speed', cond.max_speed)
    elif ctype == 'ttc_condition':
        cond.time = _extract_float(block, 'time', cond.time)


def _extract_string(text: str, field: str) -> str:
    """提取字符串字段值"""
    import re
    pattern = rf'{field}\s*:\s*"([^"]*)"'
    m = re.search(pattern, text)
    return m.group(1) if m else ""


def _extract_float(text: str, field: str, default: float) -> float:
    """提取浮点数字段值"""
    import re
    pattern = rf'{field}\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'
    m = re.search(pattern, text)
    return float(m.group(1)) if m else default


def _extract_bool(text: str, field: str, default: bool) -> bool:
    """提取布尔字段值"""
    import re
    pattern = rf'{field}\s*:\s*(true|false)'
    m = re.search(pattern, text)
    if m:
        return m.group(1) == 'true'
    return default


# ============================================================
# Condition 适配器 (让 handler 可以直接用 ConditionConfig)
# ============================================================

class ConditionAdapter:
    """将 ConditionConfig 适配为各 handler 期望的接口"""

    def __init__(self, config: ConditionConfig):
        self._config = config

    @property
    def acceleration_condition(self):
        return self._config

    @property
    def speed_condition(self):
        return self._config

    @property
    def on_road_condition(self):
        return self._config

    @property
    def obstacle_bypass_condition(self):
        return self._config

    @property
    def ttc_condition(self):
        return self._config

    @property
    def centripetal_acceleration_condition(self):
        return self._config

    @property
    def time_limit_condition(self):
        return self._config

    @property
    def region_overlap_lw_condition(self):
        return self._config

    @property
    def object_overlap_condition(self):
        return self._config


# ============================================================
# 评分引擎
# ============================================================

# handler 映射
HANDLER_MAP = {
    'speed_condition': SpeedConditionHandler,
    'acceleration_condition': AccelerationConditionHandler,
    'on_road_condition': OnRoadConditionHandler,
    'obstacle_bypass_condition': ObstacleBypassConditionHandler,
    'ttc_condition': TtcConditionHandler,
    'centripetal_acceleration_condition': CentripetalAccelerationConditionHandler,
    'time_limit_condition': TimeLimitConditionHandler,
    'region_overlap_lw_condition': RegionOverlapLwConditionHandler,
    'object_overlap_condition': ObjectOverlapConditionHandler,
}


class MetricEvaluator:
    """单个 Metric 的评估器"""

    def __init__(self, metric_config: MetricConfig):
        self.config = metric_config
        self.handler = HANDLER_MAP[metric_config.condition.condition_type]()
        self.condition_adapter = ConditionAdapter(metric_config.condition)
        self.all_passed = True
        self.metric_score = 100.0
        self.frame_results: List[DetailedResult] = []
        # object_overlap 返回 True=碰撞，需要反转为 metric fail
        self._invert = (metric_config.condition.condition_type == 'object_overlap_condition')

    def evaluate_frame(self, world_list: deque, future_list: deque) -> DetailedResult:
        """评估一帧"""
        result = DetailedResult()
        result.timestamp = world_list[-1].timestamp_sec

        handler_result = self.handler.evaluate(
            self.condition_adapter, world_list, future_list, result)

        # object_overlap: True=碰撞=metric不通过, 需要反转
        if self._invert:
            passed = not handler_result
        else:
            passed = handler_result

        result.is_pass = passed
        if not passed:
            self.all_passed = False
            if self.config.get_deduction_score:
                # 扣分制: metric_score -= delta_score
                if self.config.condition.use_score and result.delta_score > 0:
                    self.metric_score = max(0, self.metric_score - result.delta_score)
            else:
                # 得分制: delta_score 就是当前得分，取最新值
                pass

        if not self.config.get_deduction_score:
            # 得分制: metric_score = 最新的 delta_score
            self.metric_score = result.delta_score

        self.frame_results.append(result)
        return result


class GradingEngine:
    """评分引擎 - 管理所有 Metric 的评估"""

    def __init__(self, config: GradingConfig):
        self.config = config
        self.evaluators: Dict[str, MetricEvaluator] = {}
        self.world_history: deque = deque(maxlen=100)

        for metric in config.metrics:
            if metric.condition.condition_type in HANDLER_MAP:
                self.evaluators[metric.name] = MetricEvaluator(metric)

        print(f"[GradingEngine] Loaded {len(self.evaluators)} metrics: "
              f"{list(self.evaluators.keys())}")

    def feed_frame(self, world: GradingWorld):
        """输入一帧数据进行评估"""
        self.world_history.append(world)
        results = {}
        for name, evaluator in self.evaluators.items():
            result = evaluator.evaluate_frame(self.world_history, deque())
            results[name] = result
        return results

    def get_summary(self) -> dict:
        """获取评分汇总"""
        summary = {
            'is_scenario_pass': True,
            'metrics': {},
        }
        for name, evaluator in self.evaluators.items():
            if evaluator.config.require_all_time_pass:
                # 需要所有帧都通过
                is_pass = evaluator.all_passed
            else:
                # 只要有一帧通过即可 (如 ReachEnd)
                is_pass = any(r.is_pass for r in evaluator.frame_results)

            if evaluator.config.is_critical and not is_pass:
                summary['is_scenario_pass'] = False

            summary['metrics'][name] = {
                'is_pass': is_pass,
                'score': evaluator.metric_score,
                'fail_count': sum(1 for r in evaluator.frame_results if not r.is_pass),
                'total_frames': len(evaluator.frame_results),
            }
        return summary


# ============================================================
# 模式1: 读取 Bag 文件
# ============================================================

def run_bag_mode(engine: GradingEngine, bag_file: str, interval: float = 0.1):
    """
    从 bag/record 文件读取数据并评分

    依赖 Apollo Cyber Python API:
        from cyber.python.cyber_py3 import record
    """
    print(f"[Bag Mode] Reading: {bag_file}")
    print(f"[Bag Mode] Frame interval: {interval}s")

    try:
        from cyber.python.cyber_py3 import record
        from modules.common_msgs.chassis_msgs import chassis_pb2
        from modules.common_msgs.localization_msgs import localization_pb2
        from modules.common_msgs.perception_msgs import perception_obstacle_pb2
    except ImportError as e:
        print(f"[ERROR] Apollo Cyber Python modules not available: {e}")
        print("  Please run in Apollo environment or set PYTHONPATH to include:")
        print("    /opt/apollo/neo/python/")
        print("")
        print("  Alternatively, use --mode demo for a demonstration.")
        sys.exit(1)

    reader = record.RecordReader(bag_file)
    channels = reader.get_channellist()
    print(f"[Bag Mode] Found {len(channels)} channels in bag")
    for ch in channels:
        count = reader.get_messagenumber(ch)
        print(f"  {ch} ({count} msgs)")

    # 通道名
    chassis_topic = '/apollo/canbus/chassis'
    localization_topic = '/apollo/localization/pose'
    perception_topic = '/apollo/perception/obstacles'

    # 状态
    last_chassis = None
    last_localization = None
    last_perception = None
    last_speed = 0.0
    last_chassis_ts = 0.0
    begin_time_ns = None
    next_frame_ns = 0
    interval_ns = int(interval * 1e9)
    frame_count = 0

    print(f"\n[Bag Mode] Processing frames...")

    for channel_name, msg_data, datatype, timestamp_ns in reader.read_messages():
        if begin_time_ns is None:
            begin_time_ns = timestamp_ns

        # 更新各通道最新消息
        if channel_name == chassis_topic:
            chassis = chassis_pb2.Chassis()
            chassis.ParseFromString(msg_data)
            last_chassis = chassis

        elif channel_name == localization_topic:
            loc = localization_pb2.LocalizationEstimate()
            loc.ParseFromString(msg_data)
            last_localization = loc

        elif channel_name == perception_topic:
            percep = perception_obstacle_pb2.PerceptionObstacles()
            percep.ParseFromString(msg_data)
            last_perception = percep

        # 按 interval 发射帧
        elapsed_ns = timestamp_ns - begin_time_ns
        if elapsed_ns >= next_frame_ns:
            elapsed_sec = elapsed_ns / 1e9
            world = _build_world_from_messages(
                elapsed_sec, last_chassis, last_localization, last_perception,
                last_speed, last_chassis_ts
            )
            if last_chassis:
                last_speed = last_chassis.speed_mps
                last_chassis_ts = elapsed_sec

            results = engine.feed_frame(world)
            frame_count += 1
            next_frame_ns += interval_ns

            # 打印不通过的帧
            for name, r in results.items():
                if not r.is_pass:
                    print(f"  [FAIL] t={elapsed_sec:.2f}s {name}: {r.description[:80]}")

    # 标记最后一帧
    if engine.world_history:
        last_world = GradingWorld()
        last_world.timestamp_sec = engine.world_history[-1].timestamp_sec
        last_world.auto_driving_car = engine.world_history[-1].auto_driving_car
        last_world.object = engine.world_history[-1].object
        last_world.speed_limit = engine.world_history[-1].speed_limit
        last_world.last_frame = True
        engine.feed_frame(last_world)

    print(f"\n[Bag Mode] Processed {frame_count} frames")


def _build_world_from_messages(timestamp, chassis, localization, perception,
                                last_speed, last_chassis_time) -> GradingWorld:
    """从各通道消息构建 GradingWorld"""
    world = GradingWorld()
    world.timestamp_sec = timestamp

    adc = world.auto_driving_car
    adc.length = 4.5
    adc.width = 2.0
    adc.front_edge_to_center = 2.25
    adc.back_edge_to_center = 2.25

    if chassis:
        speed_mps = chassis.speed_mps
        adc.speed = speed_mps
        # 计算加速度
        if last_chassis_time > 0 and timestamp > last_chassis_time:
            dt = timestamp - last_chassis_time
            # 帧间隔异常小时（相邻消息时间戳几乎重合）不要做除法，
            # 否则会算出 9 万 m/s² 这种天文数字，凭空把 AccelerationLimit 判挂
            if dt >= 0.02:
                adc.speed_acceleration = (speed_mps - last_speed) / dt
            else:
                adc.speed_acceleration = 0.0

    if localization:
        pose = localization.pose
        adc.position_x = pose.position.x
        adc.position_y = pose.position.y
        adc.heading = pose.heading
        if pose.HasField('linear_velocity'):
            adc.speed_heading = math.atan2(
                pose.linear_velocity.y, pose.linear_velocity.x)
        if pose.HasField('angular_velocity'):
            adc.spin = pose.angular_velocity.z

    if perception:
        for obs in perception.perception_obstacle:
            obj = Object()
            obj.id = str(obs.id)
            obj.position_x = obs.position.x
            obj.position_y = obs.position.y
            obj.heading = obs.theta
            obj.length = obs.length
            obj.width = obs.width
            obj.height = obs.height
            obj.speed = math.hypot(obs.velocity.x, obs.velocity.y)
            obj.speed_heading = math.atan2(obs.velocity.y, obs.velocity.x)
            obj.front_edge_to_center = obs.length / 2
            obj.back_edge_to_center = obs.length / 2
            world.object.append(obj)

    return world


# ============================================================
# 模式2: 订阅 Cyber 通道
# ============================================================

def run_channel_mode(engine: GradingEngine, interval: float = 0.1):
    """
    订阅 Cyber 通道实时评分

    依赖 Apollo Cyber Python API:
        from cyber.python.cyber_py3 import cyber
    """
    print("[Channel Mode] Starting real-time grading...")

    try:
        from cyber.python.cyber_py3 import cyber
        from modules.common_msgs.chassis_msgs import chassis_pb2
        from modules.common_msgs.localization_msgs import localization_pb2
        from modules.common_msgs.perception_msgs import perception_obstacle_pb2
    except ImportError as e:
        print(f"[ERROR] Apollo Cyber Python modules not available: {e}")
        print("  Please run in Apollo environment.")
        sys.exit(1)

    cyber.init("grading_system_py")
    node = cyber.Node("grading_evaluator")

    # 共享状态
    state = {
        'chassis': None,
        'localization': None,
        'perception': None,
        'last_speed': 0.0,
        'last_time': 0.0,
        'begin_time': None,
    }

    def on_chassis(msg):
        state['chassis'] = msg

    def on_localization(msg):
        state['localization'] = msg

    def on_perception(msg):
        state['perception'] = msg

    # 订阅通道
    node.create_reader("/apollo/canbus/chassis",
                       chassis_pb2.Chassis, on_chassis)
    node.create_reader("/apollo/localization/pose",
                       localization_pb2.LocalizationEstimate, on_localization)
    node.create_reader("/apollo/perception/obstacles",
                       perception_obstacle_pb2.PerceptionObstacles, on_perception)

    print("[Channel Mode] Subscribed to channels. Waiting for data...")
    print("  Press Ctrl+C to stop and see results.\n")

    frame_count = 0
    try:
        while not cyber.is_shutdown():
            time.sleep(interval)

            if state['begin_time'] is None:
                if state['localization'] is not None:
                    state['begin_time'] = time.time()
                continue

            elapsed = time.time() - state['begin_time']
            world = _build_world_from_messages(
                elapsed, state['chassis'], state['localization'],
                state['perception'], state['last_speed'], state['last_time']
            )

            if state['chassis']:
                state['last_speed'] = state['chassis'].speed_mps
                state['last_time'] = elapsed

            results = engine.feed_frame(world)
            frame_count += 1

            # 实时打印不通过的结果
            for name, r in results.items():
                if not r.is_pass:
                    print(f"  [FAIL] t={elapsed:.2f}s {name}: {r.description}")

    except KeyboardInterrupt:
        print(f"\n[Channel Mode] Stopped. Processed {frame_count} frames.")

    cyber.shutdown()


# ============================================================
# Demo 模式 (无需 Apollo 环境)
# ============================================================

def run_demo_mode(engine: GradingEngine):
    """演示模式 - 使用模拟数据"""
    print("[Demo Mode] Running with simulated data...\n")

    # 模拟一段仿真数据: 车辆加速 -> 匀速 -> 急刹
    for i in range(50):
        t = i * 0.1
        if t < 2.0:
            speed = 3.0 * t          # 加速阶段
            accel = 3.0
        elif t < 3.5:
            speed = 6.0 + (t - 2.0) * 8  # 继续加速
            accel = 8.0
        else:
            speed = max(0, 18.0 - (t - 3.5) * 6)  # 急刹
            accel = -6.0

        world = GradingWorld()
        world.timestamp_sec = t
        world.last_frame = (i == 49)

        adc = world.auto_driving_car
        adc.position_x = t * speed / 2
        adc.position_y = 0
        adc.heading = 0
        adc.speed = speed
        adc.speed_acceleration = accel
        adc.speed_heading = 0
        adc.length = 4.5
        adc.width = 2.0
        adc.front_edge_to_center = 2.25
        adc.back_edge_to_center = 2.25

        # 前方有一个静止障碍物
        obs = Object()
        obs.id = "static_obs"
        obs.position_x = 60.0
        obs.position_y = 0.0
        obs.heading = 0
        obs.speed = 0
        obs.speed_heading = 0
        obs.length = 4.5
        obs.width = 2.0
        obs.front_edge_to_center = 2.25
        obs.back_edge_to_center = 2.25
        world.object.append(obs)

        world.speed_limit = 16.67  # 60 km/h

        results = engine.feed_frame(world)

        # 只打印有问题的帧
        fails = [f"{name}" for name, r in results.items() if not r.is_pass]
        if fails:
            print(f"  t={t:.1f}s | speed={speed:.1f} | accel={accel:+.1f} | "
                  f"FAIL: {', '.join(fails)}")


# ============================================================
# 主入口
# ============================================================


def _fill_endpoint_from_scenario(config: GradingConfig, scenario_path: str):
    """从场景文件中读取终点坐标填充到 ReachEnd metric"""
    import json
    try:
        with open(scenario_path, 'r', encoding='utf-8') as f:
            scenario = json.load(f)
        end_info = scenario.get('scenario', {}).get('autoCarInfo', {}).get('end', {})
        end_x = end_info.get('x', 0)
        end_y = end_info.get('y', 0)
        if end_x and end_y:
            for metric in config.metrics:
                if metric.condition.condition_type == 'region_overlap_lw_condition':
                    metric.condition.x = end_x
                    metric.condition.y = end_y
                    print(f"[Config] ReachEnd endpoint set to ({end_x:.2f}, {end_y:.2f})")
    except Exception as e:
        print(f"[WARN] Failed to read scenario file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Apollo Grading System (Python)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Demo mode (no dependencies needed):
  python3 main.py --config /apollo_workspace/grading_system/conf/grading_metrics_default.conf --mode demo

  # Read from bag file:
  python3 main.py --config /apollo_workspace/grading_system/conf/grading_metrics_default.conf \\
                  --mode bag --bag_file /apollo-simulator/output_data/1/1.output.bag

  # Subscribe to Cyber channels:
  python3 main.py --config /apollo_workspace/grading_system/conf/grading_metrics_default.conf --mode channel
        """)

    parser.add_argument('--config', required=True,
                        help='Path to grading config file (.conf)')
    parser.add_argument('--mode', choices=['bag', 'channel', 'demo'],
                        default='demo',
                        help='Data source mode: bag/channel/demo')
    parser.add_argument('--bag_file', default='',
                        help='Path to .bag/.record file (bag mode)')
    parser.add_argument('--scenario', default='',
                        help='Path to scenario JSON (provides end position for ReachEnd)')
    parser.add_argument('--interval', type=float, default=0.1,
                        help='Frame interval in seconds (default: 0.1)')

    args = parser.parse_args()

    # 解析配置文件
    print(f"[Config] Loading: {args.config}")
    config = parse_config_file(args.config)
    print(f"[Config] Parsed {len(config.metrics)} supported metrics")

    # 如果提供了 scenario 文件，补充 ReachEnd 的终点坐标
    if args.scenario:
        _fill_endpoint_from_scenario(config, args.scenario)

    # 创建评分引擎
    engine = GradingEngine(config)
    print()

    # 根据模式运行
    if args.mode == 'bag':
        if not args.bag_file:
            print("[ERROR] --bag_file is required in bag mode")
            sys.exit(1)
        run_bag_mode(engine, args.bag_file, args.interval)

    elif args.mode == 'channel':
        run_channel_mode(engine, args.interval)

    elif args.mode == 'demo':
        run_demo_mode(engine)

    # 打印汇总
    print("\n" + "=" * 60)
    print("  GRADING SUMMARY")
    print("=" * 60)

    summary = engine.get_summary()
    scenario_pass = summary['is_scenario_pass']
    print(f"\n  Scenario: {'PASS' if scenario_pass else 'FAIL'}\n")

    print(f"  {'Metric':<25} {'Result':<8} {'Score':<8} {'Fail/Total'}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*12}")
    for name, info in summary['metrics'].items():
        status = "PASS" if info['is_pass'] else "FAIL"
        score_str = f"{info['score']:.0f}"
        ratio = f"{info['fail_count']}/{info['total_frames']}"
        print(f"  {name:<25} {status:<8} {score_str:<8} {ratio}")

    print()


if __name__ == '__main__':
    main()
