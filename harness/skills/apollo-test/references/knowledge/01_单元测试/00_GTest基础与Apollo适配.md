# GTest 基础与 Apollo 适配

> 本文介绍 Google Test（GTest）在 Apollo EDU 中的使用方式，包括 Bazel 配置和常用断言。

---

## 一、Apollo 中的测试框架

Apollo 使用 **Google Test (GTest)** 作为 C++ 单元测试框架，通过 **Bazel** 构建系统管理。

| 工具 | 版本 | 说明 |
|------|------|------|
| Google Test | 1.11+ | 单元测试断言框架 |
| Google Mock | 同上 | Mock 对象框架（与 GTest 绑定） |
| Bazel | 5.x | 构建与测试运行系统 |
| buildtool | Apollo 封装 | 对 Bazel 的封装，推荐使用 |

---

## 二、Bazel BUILD 文件配置

在 `modules/planning/your_plugin/BUILD` 中添加测试目标：

```python
# 引入 GTest 依赖（Apollo 已全局配置，直接使用）
cc_test(
    name = "your_plugin_test",          # target 名称（惯例：插件名_test）
    srcs = ["your_plugin_test.cc"],      # 测试源文件
    deps = [
        ":your_plugin",                  # 被测试的目标
        "@com_google_googletest//:gtest_main",  # GTest main 函数
        # 如需 Mock：
        "@com_google_googletest//:gmock",
    ],
    # 测试数据（如需读取配置文件）
    data = [
        "//modules/planning/testdata:your_test_data",
    ],
)
```

---

## 三、测试文件基本结构

```cpp
// your_plugin_test.cc
#include "gtest/gtest.h"
#include "modules/planning/your_plugin/your_plugin.h"

namespace apollo {
namespace planning {

// 测试夹具（Fixture）：在多个测试间共享初始化逻辑
class YourPluginTest : public ::testing::Test {
 protected:
  void SetUp() override {
    // 每个测试前执行（初始化）
  }

  void TearDown() override {
    // 每个测试后执行（清理）
  }

  // 共享成员变量
  YourPlugin plugin_;
};

// 基本测试用例（不使用 Fixture）
TEST(YourPluginSimpleTest, BasicFunction) {
  EXPECT_TRUE(true);
}

// 使用 Fixture 的测试用例
TEST_F(YourPluginTest, ShouldDoSomething) {
  // Arrange
  // Act
  auto result = plugin_.SomeMethod();
  // Assert
  EXPECT_EQ(result, expected_value);
}

}  // namespace planning
}  // namespace apollo
```

---

## 四、常用 GTest 断言速查

### 基本断言

| 断言 | 说明 | 失败时 |
|------|------|-------|
| `EXPECT_TRUE(expr)` | 期望 expr 为 true | 继续执行 |
| `EXPECT_FALSE(expr)` | 期望 expr 为 false | 继续执行 |
| `ASSERT_TRUE(expr)` | 同上但失败时中止当前测试 | 停止当前测试 |

### 相等断言

| 断言 | 说明 |
|------|------|
| `EXPECT_EQ(a, b)` | a == b |
| `EXPECT_NE(a, b)` | a != b |
| `EXPECT_LT(a, b)` | a < b |
| `EXPECT_LE(a, b)` | a <= b |
| `EXPECT_GT(a, b)` | a > b |
| `EXPECT_GE(a, b)` | a >= b |

### 浮点断言（重要！）

```cpp
// 浮点数不能用 EXPECT_EQ，应用以下方式：
EXPECT_NEAR(actual, expected, abs_error);   // |actual - expected| <= abs_error
EXPECT_DOUBLE_EQ(actual, expected);         // 4 ULP 精度
EXPECT_FLOAT_EQ(actual, expected);
```

### 字符串断言

```cpp
EXPECT_STREQ(str1, str2);     // C 字符串相等
EXPECT_EQ(string1, string2);  // std::string 相等
```

### 异常断言

```cpp
EXPECT_THROW(stmt, exception_type);   // 期望抛出指定异常
EXPECT_NO_THROW(stmt);                // 期望不抛出异常
```

---

## 五、运行测试

```bash
# 在容器内（aem enter 后）的 /apollo_workspace 目录

# 运行 planning 所有测试
buildtool test -p modules/planning/

# 运行单个包的测试
buildtool test planning-traffic-rules-crosswalk

# 运行特定测试用例（Bazel 原生方式）
bazel test //modules/planning/traffic_rules/crosswalk:crosswalk_test \
  --test_filter="CrosswalkTest.*"

# 查看详细输出（默认只显示 PASSED/FAILED）
buildtool test -p modules/planning/ -- --test_output=all
```

---

## 六、Apollo 中的测试约定

1. **测试文件命名**：与被测文件同名，加 `_test.cc` 后缀（如 `crosswalk.cc` → `crosswalk_test.cc`）
2. **命名空间**：测试代码放在与被测代码相同的命名空间
3. **不依赖 cyber runtime**：单元测试应尽量不依赖 Cyber RT 的消息传输（用 Mock 替代）
4. **测试数据**：放在 `testdata/` 目录下，通过 Bazel `data` 属性引用
5. **Profile 配置**：单测通常直接传入 protobuf 对象，不依赖 profile 文件
