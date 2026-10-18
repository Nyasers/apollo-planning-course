# Mock 常见 Apollo 依赖

> 在 Apollo 单元测试中，`Frame`、`ReferenceLineInfo` 等核心对象构造复杂。本文提供常见 Mock 和简化构造方案。

---

## 一、为什么需要 Mock

Apollo Planning 的核心对象依赖链：

```
Frame
  ├── LocalView（localization, prediction, perception 等）
  ├── ReferenceLine（地图路径）
  └── ReferenceLineInfo
        ├── PathDecision（路径决策）
        ├── SpeedDecision
        └── Obstacle（障碍物列表）
```

完整构造这些对象需要地图、定位、预测等数据，不适合单元测试。**Mock 策略**：

| 依赖 | Mock 方式 | 适用场景 |
|------|---------|---------|
| `Frame` | 使用 GMock + 接口抽象 | 测试需要检查 Frame 调用的逻辑 |
| `ReferenceLineInfo` | 构造最小化真实对象 | 测试 TrafficRule ApplyRule |
| `Obstacle` | 使用 `Obstacle::CreateStaticVirtualObstacles` | 简单场景 |
| `PlanningContext` | 直接构造（无复杂依赖） | 测试需要 context 的逻辑 |
| 配置文件（.pb.txt） | 内联在测试中构造 proto | 避免依赖文件系统 |

---

## 二、Mock PlanningContext

`PlanningContext` 相对简单，可以直接构造：

```cpp
#include "modules/planning/common/planning_context.h"

// 在测试中创建 PlanningContext
PlanningContext planning_context;

// 设置场景类型
planning_context.mutable_planning_status()
    ->mutable_scenario()
    ->set_scenario_type(ScenarioConfig::LANE_FOLLOW);

// 在插件中使用
plugin.Init(config, &planning_context);
```

---

## 三、构造简单 Obstacle

```cpp
#include "modules/planning/common/obstacle.h"
#include "modules/prediction/proto/prediction_obstacle.pb.h"

// 创建静态障碍物（最简单方式）
apollo::prediction::PredictionObstacle prediction_obstacle;
prediction_obstacle.mutable_perception_obstacle()->set_id(1);
prediction_obstacle.mutable_perception_obstacle()->set_type(
    apollo::perception::PerceptionObstacle::VEHICLE);

// 设置位置
auto* position = prediction_obstacle.mutable_perception_obstacle()
    ->mutable_position();
position->set_x(10.0);   // 前方 10 米
position->set_y(0.0);
position->set_z(0.0);

// 设置尺寸
prediction_obstacle.mutable_perception_obstacle()->set_length(4.0);
prediction_obstacle.mutable_perception_obstacle()->set_width(2.0);
prediction_obstacle.mutable_perception_obstacle()->set_height(1.5);

// 创建 Obstacle 对象
double start_time = 0.0;
auto obstacle = Obstacle::CreateObstacles(prediction_obstacle, start_time);
```

---

## 四、使用 GMock 创建 Mock 类

对于需要抽象接口的场景，使用 GMock：

```cpp
#include "gmock/gmock.h"
#include "modules/planning/common/frame.h"

// 如果 Frame 有虚函数，可以这样 Mock：
class MockFrame : public Frame {
 public:
  MOCK_METHOD(const std::list<ReferenceLineInfo>&,
              reference_line_info, (), (const, override));
  MOCK_METHOD(bool,
              IsNearDestination, (), (const, override));
};

// 在测试中使用
TEST_F(YourTest, ShouldCallReferenceLineInfo) {
  MockFrame mock_frame;
  EXPECT_CALL(mock_frame, reference_line_info())
      .WillOnce(::testing::ReturnRef(test_reference_line_infos_));

  your_plugin_.ApplyRule(&mock_frame, ...);
}
```

---

## 五、内联构造 proto 配置（避免依赖文件）

测试中不要读取文件，直接在代码中构造：

```cpp
// 不推荐（依赖文件系统）：
// CrosswalkConfig config;
// cyber::common::GetProtoFromFile("testdata/crosswalk_config.pb.txt", &config);

// 推荐（内联构造）：
TrafficRuleConfig config;
config.set_rule_id(TrafficRuleConfig::CROSSWALK);
auto* crosswalk = config.mutable_crosswalk();
crosswalk->set_stop_distance(1.0);
crosswalk->set_max_stop_deceleration(6.0);
crosswalk->set_start_watch_timer_distance(20.0);
```

---

## 六、实用测试辅助函数

在测试夹具中添加辅助函数，简化重复代码：

```cpp
class PlanningTestHelper {
 public:
  // 创建简单的直线 ReferenceLine
  static ReferenceLine CreateStraightReferenceLine(
      double length, double start_x = 0.0) {
    std::vector<common::PathPoint> points;
    for (double s = 0.0; s <= length; s += 0.5) {
      common::PathPoint p;
      p.set_x(start_x + s);
      p.set_y(0.0);
      p.set_theta(0.0);
      p.set_kappa(0.0);
      p.set_s(s);
      points.push_back(p);
    }
    return ReferenceLine(points);
  }

  // 创建简单的车辆状态（前方 x 米，速度 v）
  static common::VehicleState CreateVehicleState(
      double x, double speed = 5.0) {
    common::VehicleState state;
    state.set_x(x);
    state.set_y(0.0);
    state.set_heading(0.0);
    state.set_linear_velocity(speed);
    return state;
  }
};
```

---

## 七、参考 Apollo 官方测试

在容器内查找复杂依赖的处理方式：

```bash
# 查找有完整 Frame 构造的测试
grep -r "new Frame\|std::make_unique<Frame>" \
  /apollo/modules/planning/ --include="*_test.cc" | head -5

# 查看 planning 测试工具
ls /apollo/modules/planning/testdata/
ls /apollo/modules/planning/common/test/
```
