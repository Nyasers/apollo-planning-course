# buildtool test 使用指南

> 本文说明如何在 Apollo EDU 中使用 buildtool test 运行单元测试，以及如何解读输出结果。

---

## 一、前置条件

在运行测试前，确保：

```bash
# 1. 已进入容器
cd application-pnc && aem start && aem enter

# 2. 已完成编译（测试依赖编译产物）
buildtool build -p modules/planning/

# 3. profile 配置正确（部分测试依赖配置）
aem profile use default
```

---

## 二、基本命令

```bash
# 运行 planning 模块所有测试（推荐）
buildtool test -p modules/planning/

# 运行指定包的测试（包名格式与 buildtool install 相同）
buildtool test planning-traffic-rules-crosswalk
buildtool test planning-traffic-rules-stop-sign
buildtool test planning-scenarios-valet-parking

# 查看有哪些可测试的包
buildtool list-packages | grep planning | head -20
```

---

## 三、输出解读

### 正常通过

```
//modules/planning/traffic_rules/crosswalk:crosswalk_test   PASSED in 0.8s
//modules/planning/traffic_rules/stop_sign:stop_sign_test   PASSED in 1.2s

Executed 2 out of 2 tests: 2 tests pass.
```

### 测试失败

```
//modules/planning/traffic_rules/crosswalk:crosswalk_test   FAILED in 0.5s

FAIL: CrosswalkTest.ShouldStopWhenNearCrosswalk
Expected: reference_line_info->path_decision()->stop_reference_line_end_id()
     is not empty
  Actual: it is empty

Executed 2 out of 2 tests: 1 test FAILED.
```

### 编译失败（测试无法运行）

```
ERROR: /apollo_workspace/modules/planning/traffic_rules/crosswalk/BUILD:12:8:
  Compiling crosswalk_test.cc failed
  error: 'CrosswalkConfig' has no member named 'set_stop_strict_l_distance'
```

→ 说明是代码编译错误，不是测试逻辑问题，先修复编译。

---

## 四、查看详细测试输出

默认只显示 PASSED/FAILED，要看详细的 `std::cout` 和 GTest 输出：

```bash
# 方式 1：buildtool 传递 Bazel 参数
buildtool test planning-traffic-rules-crosswalk -- --test_output=all

# 方式 2：直接使用 Bazel
bazel test //modules/planning/traffic_rules/crosswalk:crosswalk_test \
  --test_output=all \
  --test_filter="CrosswalkTest.*"

# 方式 3：查看测试日志文件
cat bazel-testlogs/modules/planning/traffic_rules/crosswalk/crosswalk_test/test.log
```

---

## 五、运行特定测试用例

```bash
# 只运行名称匹配的测试用例（支持通配符）
bazel test //modules/planning/...:all \
  --test_filter="CrosswalkTest.CanBeCreated"

# 运行名称包含 "Crosswalk" 的所有测试
bazel test //modules/planning/...:all \
  --test_filter="*Crosswalk*"
```

---

## 六、常见报错速查

| 报错 | 原因 | 解决方案 |
|------|------|---------|
| `No such file or directory: BUILD` | 测试 target 未在 BUILD 文件中定义 | 在 BUILD 文件中添加 `cc_test` 配置 |
| `No tests found for given labels` | 包名拼写错误 | 用 `buildtool list-packages \| grep planning` 确认包名 |
| `undefined reference to 'xxx'` | deps 缺少依赖 | 在 BUILD 的 `deps` 中添加缺失的 target |
| `TIMEOUT` | 测试运行超时（默认 60s） | 加 `--test_timeout=120` 或优化测试 |
| `error: cannot convert 'X*' to 'Y*'` | 接口变更，测试代码过时 | 更新测试代码适配新接口 |

---

## 七、测试覆盖率（可选）

```bash
# 生成覆盖率报告（需要额外工具，可选）
bazel coverage //modules/planning/traffic_rules/crosswalk:crosswalk_test \
  --combined_report=lcov

# 查看报告
genhtml bazel-out/_coverage/_coverage_report.dat -o coverage_report/
# 用浏览器打开 coverage_report/index.html
```
