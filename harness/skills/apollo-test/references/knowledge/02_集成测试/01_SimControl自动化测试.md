# SimControl 自动化测试

> 本文说明如何通过 DreamView + SimControl 批量运行多个仿真场景，记录通过/失败结果，作为集成测试。

---

## 一、SimControl 简介

SimControl 是 Apollo EDU 内置的仿真控制工具，可以：
- 在无真实车辆的情况下运行规划仿真
- 发送虚拟的定位、感知、预测数据给 Planning 模块
- 自动回放赛事场景，验证规划效果

---

## 二、前置准备

```bash
# 1. 进入容器并启动
cd application-pnc
aem start && aem enter

# 2. 确保已下载场景插件
# 见 apollo-env 知识库：02_安装部署/04_赛事场景插件下载指南.md

# 3. 启动 DreamView+
aem bootstrap start --plus
# 浏览器访问 http://localhost:8888
```

---

## 三、手动运行场景（基础版）

在 DreamView 中逐场景验证：

```
Step 1: 打开 DreamView（http://localhost:8888）
Step 2: 左侧选择 Profile → default
Step 3: 点击 "Scenario"（场景列表）
Step 4: 选择目标场景（如 "crosswalk_01"）
Step 5: 点击 "Run" 启动仿真
Step 6: 观察车辆行为，记录结果
Step 7: 场景结束后查看 "Result"
```

---

## 四、批量场景测试记录表

每次仿真后记录结果，用于集成测试文档：

```markdown
## 集成测试记录 - YYYY-MM-DD

| 场景 ID | 场景名 | 运行次数 | 通过次数 | 通过率 | 备注 |
|--------|-------|---------|---------|-------|------|
| crosswalk_01 | 人行道避让 | 3 | 3 | 100% | 稳定 |
| crosswalk_02 | 人行道（有行人） | 3 | 2 | 67% | 偶发停滞 |
| lane_borrow_01 | 借道绕行 | 3 | 3 | 100% | — |
| junction_01 | 交汇路口 | 3 | 1 | 33% | 需修复 |
```

---

## 五、提高测试可重复性

仿真结果可能因为障碍物随机性产生差异，建议：

```bash
# 每次测试前重置环境
# 1. 关闭 DreamView
aem bootstrap stop

# 2. 重新加载 profile（防止配置漂移）
aem profile use default

# 3. 重启 DreamView
aem bootstrap start --plus

# 4. 运行目标场景
```

---

## 六、配合 cyber_recorder 进行录制

在集成测试时录制 cyber record，供后续 apollo-eval 分析：

```bash
# 测试开始前：
cyber_recorder record \
  -c /apollo/planning/trajectory \
  -c /apollo/localization/pose \
  -o /apollo_workspace/data/bag/integration_test_$(date +%Y%m%d_%H%M%S).record &
RECORDER_PID=$!

# 运行场景...（在 DreamView 中操作）

# 测试结束后：
kill $RECORDER_PID

# 用 apollo-eval 分析录制结果
python3 extract_metrics.py data/bag/integration_test_*.record
```

---

## 七、常见集成测试问题

| 问题 | 可能原因 | 排查方法 |
|------|---------|---------|
| 场景无法启动 | DreamView 未正确加载 profile | 检查左上角 Profile 是否显示 "default" |
| 车辆不动 | Planning 模块未启动 | DreamView 顶部 Planning 状态是否为绿色 |
| 场景结束立即 FAILED | 车辆碰撞或超时 | 观察仿真并查看 Planning 日志 |
| 场景结果不稳定 | 环境状态未重置 | 每次测试前重启 DreamView |
| 录制包过大 | 录制了所有 channel | 指定 `-c` 只录制需要的 channel |
