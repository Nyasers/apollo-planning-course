# TrafficRule 插件单测模板

> 提供 Apollo EDU 中 TrafficRule 插件的完整 GTest 测试文件骨架，可直接复制修改。

---

## 一、TrafficRule 插件测试要点

TrafficRule 插件的核心逻辑是 `ApplyRule(Frame*, ReferenceLineInfo*)` 方法，测试重点：

1. **决策是否正确触发**：在应该停车的场景下，是否生成了 `stop` decision
2. **决策是否正确跳过**：在不应该停车的场景下，是否没有生成多余的 decision
3. **边界条件**：距离停止线恰好在阈值边界时的行为

---

## 二、完整测试文件骨架

以人行道（Crosswalk）插件为例，保存为 `crosswalk_test.cc`：

```cpp
// modules/planning/traffic_rules/crosswalk/crosswalk_test.cc

#include "gtest/gtest.h"
#include "gmock/gmock.h"

// 被测插件头文件
#include "modules/planning/traffic_rules/crosswalk/crosswalk.h"

// Apollo 测试工具
#include "modules/planning/common/planning_gflags.h"
#include "modules/planning/proto/traffic_rule_config.pb.h"

// Cyber 配置加载（测试中不依赖完整 cyber runtime）
#include "cyber/common/file.h"

namespace apollo {
namespace planning {

class CrosswalkTest : public ::testing::Test {
 protected:
  void SetUp() override {
    // 加载默认 TrafficRule 配置
    TrafficRuleConfig config;
    config.set_rule_id(TrafficRuleConfig::CROSSWALK);
    auto* crosswalk_config = config.mutable_crosswalk();
    crosswalk_config->set_stop_distance(1.0);
    crosswalk_config->set_max_stop_deceleration(6.0);
    crosswalk_config->set_start_watch_timer_distance(20.0);
    crosswalk_config->set_stop_strict_l_distance(6.0);

    crosswalk_ = std::make_unique<Crosswalk>(config, nullptr);
  }

  // 创建一个简单的测试用 ReferenceLineInfo（需要根据实际接口调整）
  // 注意：完整的 Frame 和 ReferenceLineInfo 构造较复杂，建议参考现有测试
  // 或使用 Mock 对象（见 03_Mock常见Apollo依赖.md）

  std::unique_ptr<Crosswalk> crosswalk_;
};

// 测试 1：插件能正常创建（基本冒烟测试）
TEST_F(CrosswalkTest, CanBeCreated) {
  EXPECT_NE(crosswalk_, nullptr);
}

// 测试 2：配置参数正确加载
TEST_F(CrosswalkTest, ConfigIsLoaded) {
  // 验证插件配置的关键参数
  // 根据实际插件接口添加断言
  EXPECT_TRUE(true);  // 占位，替换为实际断言
}

// 测试 3：在距离人行道较远时不产生 stop decision
// （具体实现需要构造 Frame/ReferenceLineInfo，见下方说明）
TEST_F(CrosswalkTest, NoStopWhenFarFromCrosswalk) {
  // TODO: 构造 Frame 和 ReferenceLineInfo
  // auto frame = CreateTestFrame(...);
  // auto reference_line_info = CreateTestReferenceLineInfo(...);
  // crosswalk_->ApplyRule(frame.get(), reference_line_info.get());
  // EXPECT_TRUE(reference_line_info->path_decision()->stop_reference_line_end_id().empty());
  GTEST_SKIP() << "需要构造测试用 Frame，见 03_Mock常见Apollo依赖.md";
}

// 测试 4：在距离人行道较近时产生 stop decision
TEST_F(CrosswalkTest, ShouldStopWhenNearCrosswalk) {
  GTEST_SKIP() << "需要构造测试用 Frame，见 03_Mock常见Apollo依赖.md";
}

}  // namespace planning
}  // namespace apollo
```

---

## 三、对应的 Bazel BUILD 配置

在 `modules/planning/traffic_rules/crosswalk/BUILD` 中添加：

```python
cc_test(
    name = "crosswalk_test",
    srcs = ["crosswalk_test.cc"],
    deps = [
        ":crosswalk",
        "//modules/planning/common:planning_gflags",
        "//modules/planning/proto:traffic_rule_config_cc_proto",
        "@com_google_googletest//:gtest_main",
        "@com_google_googletest//:gmock",
    ],
    tags = ["exclusive"],  # 避免并发冲突
)
```

---

## 四、运行测试

```bash
# 在容器内
buildtool test planning-traffic-rules-crosswalk

# 看详细输出
buildtool test planning-traffic-rules-crosswalk -- --test_output=all

# 运行特定用例
bazel test //modules/planning/traffic_rules/crosswalk:crosswalk_test \
  --test_filter="CrosswalkTest.CanBeCreated"
```

---

## 五、参考现有测试

Apollo 代码库中有大量可参考的测试文件：

```bash
# 在容器内查找现有 traffic_rules 测试
find /apollo/modules/planning/traffic_rules/ -name "*_test.cc" | head -10

# 查看 stop_sign 的测试（通常比较完整）
cat /apollo/modules/planning/traffic_rules/stop_sign/stop_sign_unprotected_test.cc
```

---

## 六、注意事项

1. **Frame 构造复杂**：完整的 `Frame` 需要 localization、prediction 等数据，建议先用 `GTEST_SKIP()` 占位，逐步完善
2. **优先测试纯逻辑**：把纯计算逻辑抽取为独立函数，对这些函数写单测更简单
3. **不要依赖 DreamView**：单测应完全离线运行，不依赖任何运行中的 Apollo 服务
