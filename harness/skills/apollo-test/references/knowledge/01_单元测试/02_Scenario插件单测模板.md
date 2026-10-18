# Scenario 插件单测模板

> 提供 Apollo EDU 中 Scenario 插件（场景状态机）的 GTest 测试骨架。

---

## 一、Scenario 插件测试要点

Scenario 插件通过状态机驱动，核心接口：

| 接口 | 说明 |
|------|------|
| `IsTransferable(...)` | 判断当前条件是否可以进入此场景 |
| `Process(...)` | 场景主处理逻辑（每帧调用） |
| `GetStage()` | 获取当前阶段（Stage） |
| `IsDone()` | 场景是否结束 |

测试重点：
1. **IsTransferable 逻辑**：在满足触发条件时返回 true，否则 false
2. **Stage 状态转换**：从 STAGE_A → STAGE_B 的转换条件
3. **结束条件**：IsDone 何时为 true

---

## 二、完整测试骨架

以自主泊车（ValetParking）场景为例：

```cpp
// modules/planning/scenarios/valet_parking/valet_parking_scenario_test.cc

#include "gtest/gtest.h"
#include "modules/planning/scenarios/valet_parking/valet_parking_scenario.h"
#include "modules/planning/proto/scenario_config.pb.h"

namespace apollo {
namespace planning {

class ValetParkingScenarioTest : public ::testing::Test {
 protected:
  void SetUp() override {
    // 初始化场景配置
    ScenarioConfig config;
    config.set_scenario_type(ScenarioConfig::VALET_PARKING);

    // 创建场景对象
    // 注意：构造函数参数根据实际接口调整
    // scenario_ = std::make_unique<ValetParkingScenario>(config, ...);
  }

  // std::unique_ptr<ValetParkingScenario> scenario_;
};

// 测试 1：冒烟测试，场景对象可以创建
TEST_F(ValetParkingScenarioTest, CanInstantiate) {
  // EXPECT_NE(scenario_, nullptr);
  GTEST_SKIP() << "根据实际构造函数参数完善";
}

// 测试 2：不在泊车位附近时，IsTransferable 返回 false
TEST_F(ValetParkingScenarioTest, NotTransferableWhenFarFromParkingSpot) {
  // auto frame = CreateFrameWithoutParkingTarget();
  // EXPECT_FALSE(scenario_->IsTransferable(frame.get(), ...));
  GTEST_SKIP() << "需要构造测试 Frame";
}

// 测试 3：Stage 初始状态正确
TEST_F(ValetParkingScenarioTest, InitialStageIsApproachingParkingSpot) {
  // EXPECT_EQ(scenario_->GetStage()->stage_type(),
  //           ScenarioConfig::VALET_PARKING_APPROACHING_PARKING_SPOT);
  GTEST_SKIP() << "根据实际 Stage 类型完善";
}

}  // namespace planning
}  // namespace apollo
```

---

## 三、Stage 单独测试

通常每个 Stage 也可以单独测试：

```cpp
// stage_approaching_parking_spot_test.cc

#include "gtest/gtest.h"
#include "modules/planning/scenarios/valet_parking/stage_approaching_parking_spot.h"

namespace apollo {
namespace planning {

TEST(StageApproachingParkingSpotTest, FinishesWhenCloseEnough) {
  // StageApproachingParkingSpot stage;
  // 模拟车辆已接近泊车位
  // auto result = stage.Process(...);
  // EXPECT_EQ(result, Stage::FINISHED);
  GTEST_SKIP() << "根据实际 Stage 接口完善";
}

}  // namespace planning
}  // namespace apollo
```

---

## 四、状态机测试策略

对于复杂的状态机，推荐**逐 Stage 隔离测试**：

```
场景状态机测试策略：
┌─────────────────────────────────────────┐
│  Level 1：IsTransferable 纯逻辑测试       │
│  （只测触发条件，不依赖完整 Frame）         │
├─────────────────────────────────────────┤
│  Level 2：Stage.Process 单独测试          │
│  （构造最小化的 Frame 和 ReferenceLineInfo）│
├─────────────────────────────────────────┤
│  Level 3：完整场景集成测试（SimControl）   │
│  （见 ../02_集成测试/01_SimControl自动化测试.md）│
└─────────────────────────────────────────┘
```

**建议先完成 Level 1**（纯逻辑，无 Frame 依赖），再逐步完善 Level 2。

---

## 五、BUILD 配置

```python
cc_test(
    name = "valet_parking_scenario_test",
    srcs = ["valet_parking_scenario_test.cc"],
    deps = [
        ":valet_parking_scenario",
        "//modules/planning/proto:scenario_config_cc_proto",
        "@com_google_googletest//:gtest_main",
        "@com_google_googletest//:gmock",
    ],
)
```

---

## 六、查找现有 Scenario 测试参考

```bash
# 在容器内
find /apollo/modules/planning/scenarios/ -name "*_test.cc" 2>/dev/null | head -10
```
