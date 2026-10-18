"""
地图抽象接口 + stub 实现
对应原 C++ 项目中 Apollo HD Map 的接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class LaneId:
    id: str = ""


@dataclass
class LaneInfo:
    """车道信息"""
    lane_id: LaneId = field(default_factory=LaneId)
    total_length: float = 0.0
    turn_type: str = "NO_TURN"  # NO_TURN, LEFT_TURN, RIGHT_TURN, U_TURN
    predecessor_ids: List[LaneId] = field(default_factory=list)
    successor_ids: List[LaneId] = field(default_factory=list)

    def get_projection(self, x: float, y: float) -> Tuple[bool, float, float]:
        """将点投影到车道上，返回 (success, accumulate_s, lateral)"""
        return False, 0.0, 0.0

    def get_width(self, s: float) -> Tuple[float, float]:
        """返回 (left_width, right_width)"""
        return 1.75, 1.75

    def get_road_width(self, s: float) -> Tuple[float, float]:
        """返回 road boundary (left_width, right_width)"""
        return 3.5, 3.5


@dataclass
class SignalInfo:
    """信号灯信息"""
    signal_id: str = ""
    stop_line_points: List[List[Tuple[float, float]]] = field(default_factory=list)


@dataclass
class SpeedBumpInfo:
    """减速带信息"""
    bump_id: str = ""
    points: List[Tuple[float, float]] = field(default_factory=list)


class MapInterface(ABC):
    """地图抽象接口"""

    @abstractmethod
    def get_lanes(self, x: float, y: float, radius: float) -> List[LaneInfo]:
        """获取指定位置附近的车道"""
        ...

    @abstractmethod
    def get_lane_by_id(self, lane_id: str) -> Optional[LaneInfo]:
        """根据ID获取车道"""
        ...

    @abstractmethod
    def get_forward_nearest_signals(self, x: float, y: float, distance: float) -> List[SignalInfo]:
        """获取前方最近的信号灯"""
        ...

    @abstractmethod
    def get_exact_lanes(self, x: float, y: float, radius: float) -> List[LaneInfo]:
        """获取精确匹配的车道"""
        ...


class StubMapInterface(MapInterface):
    """Stub 实现 - 返回空结果，后续可替换为真实地图服务"""

    def get_lanes(self, x: float, y: float, radius: float) -> List[LaneInfo]:
        return []

    def get_lane_by_id(self, lane_id: str) -> Optional[LaneInfo]:
        return None

    def get_forward_nearest_signals(self, x: float, y: float, distance: float) -> List[SignalInfo]:
        return []

    def get_exact_lanes(self, x: float, y: float, radius: float) -> List[LaneInfo]:
        return []


# 全局地图实例，可在运行时替换
_map_instance: MapInterface = StubMapInterface()


def set_map_interface(map_impl: MapInterface):
    global _map_instance
    _map_instance = map_impl


def get_map_interface() -> MapInterface:
    return _map_instance
