# apollo-test

`apollo-test` 现在定位为 **数据包录制、通道盘点、模块图表可视化落盘、回放核验**。

评分、metric、赛事得分解释属于 `apollo-eval`，不要混在 `apollo-test` 里做。

## 主要入口

| 入口 | 用途 |
|-|-|
| `/apollo-test record` | 录制实车或仿真 cyber record |
| `/apollo-test channels` | 输出已有数据包 channel 清单 |
| `/apollo-test report` | 导出 CSV、PNG、Markdown 报告 |
| `/apollo-test replay` | 回放核验 |
| `/apollo-test bag` | 兼容旧入口，优先走 report |

## 脚本

```text
scripts/
├── record_apollo_channels.sh   # 按 pnc/vehicle/full profile 录制 channel
├── record_channel_report.py    # 输出 channel_summary.csv/csv/*.csv/plots/*.png/record_report.md
├── analyze_pnc_record.py       # 旧 PnC 调试分析脚本，兼容保留
└── record_pnc_sim.sh           # 旧 PnC 录包脚本，兼容保留
```

## 示例

录制实车闭环常用通道：

```bash
bash /home/apollo/.openclaw/skills/apollo-test/scripts/record_apollo_channels.sh \
  wanzheng_bihuan "完整闭环实车包" vehicle
```

对已有包生成报告：

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 /home/apollo/.openclaw/skills/apollo-test/scripts/record_channel_report.py \
  /apollo_workspace/data/4闭环/wanzheng_bihuan \
  -o /apollo_workspace/data/4闭环/wanzheng_bihuan_report
```

只做通道清单：

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=/opt/apollo/neo/python \
python3 /home/apollo/.openclaw/skills/apollo-test/scripts/record_channel_report.py \
  /apollo_workspace/data/4闭环/wanzheng_bihuan \
  -o /apollo_workspace/data/4闭环/wanzheng_bihuan_inventory \
  --inventory-only
```
