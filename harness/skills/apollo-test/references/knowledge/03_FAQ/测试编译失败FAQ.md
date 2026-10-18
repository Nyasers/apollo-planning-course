# 测试编译失败 FAQ

> 收集 `buildtool test` 或编写测试文件时的常见编译报错与解决方案。

---

## 一、BUILD 文件相关

### 报错：`No such target`

```
ERROR: no such target '//modules/planning/traffic_rules/crosswalk:crosswalk_test'
```

**原因**：BUILD 文件中没有定义 `crosswalk_test` target。

**解决**：在 `modules/planning/traffic_rules/crosswalk/BUILD` 中添加：

```python
cc_test(
    name = "crosswalk_test",
    srcs = ["crosswalk_test.cc"],
    deps = [
        ":crosswalk",
        "@com_google_googletest//:gtest_main",
    ],
)
```

---

### 报错：`undefined reference to 'XXX'`

```
undefined reference to 'apollo::planning::Crosswalk::ApplyRule'
```

**原因**：BUILD 文件的 `deps` 缺少对应的库。

**解决**：确保 `deps` 包含被测目标：

```python
deps = [
    ":crosswalk",      # ← 被测目标，必须包含
    "@com_google_googletest//:gtest_main",
],
```

---

## 二、头文件相关

### 报错：`file not found`

```
fatal error: 'modules/planning/traffic_rules/crosswalk/crosswalk.h' file not found
```

**原因**：include 路径错误，或代码未下载到本地。

**解决**：

```bash
# 检查文件是否存在
ls modules/planning/traffic_rules/crosswalk/crosswalk.h

# 如果不存在，先下载源码
buildtool install planning-traffic-rules-crosswalk
```

---

### 报错：`has no member named 'xxx'`

```
error: 'CrosswalkConfig' has no member named 'set_stop_strict_l_distance'
```

**原因**：proto 字段名变更（Apollo 版本更新）。

**解决**：

```bash
# 查看实际的 proto 字段定义
grep -A 20 "message CrosswalkConfig" \
  /apollo/modules/planning/proto/traffic_rule_config.proto
```

根据实际字段名更新测试代码。

---

## 三、Mock 相关

### 报错：`cannot instantiate abstract class`

```
error: cannot declare variable 'mock_frame' to be of abstract type 'MockFrame'
```

**原因**：Mock 类未实现所有纯虚函数。

**解决**：在 MockFrame 中添加缺失的 `MOCK_METHOD`：

```cpp
// 查看 Frame 的纯虚函数
grep "= 0" /apollo/modules/planning/common/frame.h

// 对每个纯虚函数都添加 MOCK_METHOD
class MockFrame : public Frame {
 public:
  MOCK_METHOD(void, missing_method, (), (override));
  // ...
};
```

---

### 报错：`MOCK_METHOD type mismatch`

```
error: no matching function for call to 'MockFrame::MockFrame()'
```

**原因**：Frame 的构造函数有必须参数，Mock 类需要传递。

**解决**：提供 Mock 构造函数参数，或改用组合而非继承：

```cpp
// 方式：不继承 Frame，创建一个独立的接口 Mock
// 或直接测试不依赖 Frame 的纯函数逻辑
```

---

## 四、运行时相关

### 报错：`SEGFAULT in test`

```
[FATAL] Segmentation fault (core dumped)
```

**原因**：测试中访问了空指针，通常是依赖对象未初始化。

**解决**：

```bash
# 查看详细的崩溃堆栈
bazel test //...:your_test --test_output=all 2>&1 | grep -A 20 "SEGFAULT"

# 检查 SetUp() 中是否所有成员变量都已初始化
```

---

### 报错：`Test TIMEOUT`

```
//modules/planning/...:your_test   TIMEOUT
```

**原因**：测试运行时间超过默认限制（60s）。

**解决**：

```bash
# 增大超时时间
bazel test //...:your_test --test_timeout=300

# 或在 BUILD 中设置
cc_test(
    name = "your_test",
    timeout = "long",    # short(60s) / moderate(300s) / long(900s)
    ...
)
```

---

## 五、快速调试技巧

```bash
# 只重新运行失败的测试（不重新编译）
bazel test //...:your_test --cache_test_results=no

# 保留测试临时文件（方便检查）
bazel test //...:your_test --test_tmpdir=/tmp/bazel_test_tmp

# 打印测试中的 LOG 输出
bazel test //...:your_test --test_output=all 2>&1 | grep -E "PASS|FAIL|LOG"
```
