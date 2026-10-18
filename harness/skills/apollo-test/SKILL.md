---
name: apollo-test
description: Apollo 数据包录制、通道盘点、模块信号可视化和回放核验工具。主要用于实车或仿真 cyber record 采集，按 pnc/vehicle/full profile 录制 channel，检查已有数据包的 channel/message type/message count，导出核心模块 CSV、PNG 图表和 Markdown 报告，并维护落盘目录与 manifest。不要用它做评分、metric 判分或赛事分数解释；这些属于 apollo-eval。触发关键词：录包、录制、record、bag、数据包、实车数据、闭环数据、channel、通道清单、topic、模块图表、可视化、CSV、PNG、report、落盘、回放、cyber_recorder、DreamView 验证、/apollo-test record、/apollo-test channels、/apollo-test report、/apollo-test replay、/apollo-test bag。
default-enabled: false
---

# Apollo Test

`apollo-test` 的主职责是 **数据包采集与可视化落盘**：

- 录制实车或仿真 cyber record，并按 profile 管理 channel 范围。
- 对已有 record 目录做 channel inventory，输出 `channel_summary.csv`。
- 解析核心模块信号，输出 `csv/*.csv`、`plots/*.png`、`record_report.md`。
- 辅助回放验证数据包是否可复现。

边界：`apollo-test` 不做赛事评分、不解释 metric 分数、不判断是否通过终点；评分和 metric 问题转给 `apollo-eval`。

技能目录记为 `{BASE_DIR}`，通常是 `/home/apollo/.openclaw/skills/apollo-test`。

## 命令分流

| 用户意图 | 处理方式 |
|-|-|
| `/apollo-test` | 询问是要录制、盘点、出报告还是回放 |
| `/apollo-test record` / 录包 | 走“流程 A：录制数据包” |
| `/apollo-test channels` / 通道清单 | 走“流程 B：盘点已有数据包” |
| `/apollo-test report` / 图表落盘 | 走“流程 C：生成报告” |
| `/apollo-test replay` / 回放 | 走“流程 D：回放核验” |
| `/apollo-test bag` | 兼容旧入口，优先生成 report，再按报告辅助调试 |
| GTest / buildtool test | 作为次级测试能力，可读取 `references/knowledge/` |

## 快速命令

录制 PnC 核心通道：

```bash
bash {BASE_DIR}/scripts/record_apollo_channels.sh s_curve "S弯道闭环基线" pnc
```

录制实车闭环常用通道：

```bash
bash {BASE_DIR}/scripts/record_apollo_channels.sh wanzheng_bihuan "完整闭环实车包" vehicle
```

仅盘点已有数据包：

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 {BASE_DIR}/scripts/record_channel_report.py \
  /apollo_workspace/data/4闭环/wanzheng_bihuan \
  -o /apollo_workspace/data/4闭环/wanzheng_bihuan_report \
  --inventory-only
```

生成 CSV、图表、Markdown 报告：

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 {BASE_DIR}/scripts/record_channel_report.py \
  /apollo_workspace/data/4闭环/wanzheng_bihuan \
  -o /apollo_workspace/data/4闭环/wanzheng_bihuan_report
```

指定额外 channel：

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 {BASE_DIR}/scripts/record_channel_report.py \
  /path/to/record_dir \
  -o /path/to/report_dir \
  --channel /apollo/planning \
  --channel /apollo/control \
  --channel /apollo/localization/pose
```

回放：

```bash
cyber_recorder play -f /path/to/xxx.record
```

## 流程 A：录制数据包

先确认用户要录哪类数据：

- `pnc`：默认推荐，planning/control/canbus/localization/perception/prediction/guardian/safety/tf。
- `vehicle`：实车闭环推荐，在 `pnc` 基础上加 GNSS/IMU/lidar 关键 channel。
- `full`：录当前所有发布 channel，文件最大，仅在明确需要原始传感器全量包时使用。

执行：

```bash
bash {BASE_DIR}/scripts/record_apollo_channels.sh <tag> "<描述>" <pnc|vehicle|full>
```

默认输出到：

```text
/apollo_workspace/data/record/apollo_channels/<timestamp>_<tag>/
/apollo_workspace/data/record/apollo_channels/manifest.csv
```

录制结束后，立刻建议用户运行 `record_channel_report.py` 对新包出报告，确认核心 channel 是否齐全。

## 流程 B：盘点已有数据包

用于快速判断一个 record 目录里有什么 channel、每个 channel 有多少消息、message type 是什么。

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 {BASE_DIR}/scripts/record_channel_report.py <record文件或目录> \
  -o <输出目录> \
  --inventory-only
```

重点看：

- `channel_summary.csv`：全量 channel、message type、message count、是否有内置 parser。
- `module_summary.csv`：按 planning/control/canbus/localization 等模块聚合的消息量。

注意：`--inventory-only` 不生成信号图表，只做轻量盘点。

## 流程 C：生成可视化报告

默认解析这些核心 channel：

- `/apollo/canbus/chassis`
- `/apollo/control`
- `/apollo/control/interactive`
- `/apollo/guardian`
- `/apollo/localization/pose`
- `/apollo/perception/obstacles`
- `/apollo/planning`
- `/apollo/prediction`
- `/apollo/sensor/gnss/best_pose`
- `/apollo/sensor/gnss/corrected_imu`
- `/apollo/sensor/gnss/imu`
- `/apollo/sensor/gnss/ins_stat`

执行：

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 {BASE_DIR}/scripts/record_channel_report.py <record文件或目录> \
  -o <输出目录>
```

产物：

```text
<输出目录>/
├── record_report.md
├── channel_summary.csv
├── module_summary.csv
├── csv/
└── plots/
```

默认不会解析点云、raw_data、`/tf` 全量内容；这些只进入 channel 清单。需要更完整时间统计时加 `--full-scan`，但大包会更慢。

## 流程 D：回放核验

回放单个 record：

```bash
cyber_recorder play -f /path/to/xxx.record
```

循环回放：

```bash
cyber_recorder play -f /path/to/xxx.record --loop
```

只回放关键 topic：

```bash
cyber_recorder play -f /path/to/xxx.record \
  -w /apollo/planning \
  -w /apollo/control \
  -w /apollo/localization/pose \
  -w /apollo/canbus/chassis \
  -w /apollo/perception/obstacles
```

回放核验关注：

- Planning、Control、Localization、Canbus 是否同时存在。
- 核心 channel 频率是否异常断档。
- DreamView 现象是否能复现。
- 报告中的速度、转角、制动、轨迹点数是否和观察一致。

## 次级能力：代码测试

如果用户明确问 GTest、BUILD、`buildtool test` 或提交前测试，再读取 `references/knowledge/` 中对应文档。不要让这些内容覆盖主流程。

常用命令：

```bash
buildtool test -p modules/planning/
buildtool test <target> -- --test_output=all
```

旧脚本 `analyze_pnc_record.py`、`record_pnc_sim.sh` 仍可用于兼容旧 PnC 调试流程，但新的录制和报告流程优先使用：

- `{BASE_DIR}/scripts/record_apollo_channels.sh`
- `{BASE_DIR}/scripts/record_channel_report.py`
