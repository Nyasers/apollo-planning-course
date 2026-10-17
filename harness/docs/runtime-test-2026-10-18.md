# Apollo Claw Harness 运行测试记录

日期：2026-10-18
环境：Windows 11 + WSL2 Ubuntu 22.04
Apollo 容器：`apollo_neo_dev_edu`
Docker：29.7.1
Python：3.10.12

## 1. 测试结论

Harness 的 P0/P1 骨架和本地服务已经通过实际运行验证；真实仿真场景的完整 record 闭环尚未完成，原因是本轮没有成功启动 SimControl 场景。

测试结果：

| 测试 | 结果 | 说明 |
|---|---|---|
| Python 编译 | 通过 | `compileall` 无错误 |
| 单元测试 | 通过 | 5 个测试全部通过 |
| WSL `doctor` | 通过 | Docker、aem、Apollo 容器、DreamView、技能目录均识别 |
| 20 秒 record | 部分成功 | record 文件生成，但 0 channels |
| channel 报告 | 通过 | 生成 CSV、module summary、Markdown |
| report export | 通过 | 生成 `report.json` / `report.md` |
| 无 Key explain | 通过 | 自动规则降级，并能读取知识库和日志 |
| 本地 HTTP 面板 | 通过 | `/health`、`/api/tasks`、`/api/experiments`、`/api/latest` 正常 |
| DeepSeek 实际调用 | 未执行 | WSL 中未配置 `DEEPSEEK_API_KEY` |

## 2. 实际测试记录

### 2.1 环境检查

执行：

```bash
python3 -m apollo_claw doctor --json
```

结果：

- Docker 29.7.1 正常。
- `aem` 10.0.0-rc1-r4 正常。
- Apollo 容器运行。
- DreamView `http://127.0.0.1:8888/` 返回 HTTP 200。
- 四个 Apollo Claw skill 均找到。

### 2.2 record

执行：

```bash
python3 -m apollo_claw test record --tag crosswalk --seconds 20 --execute
```

生成：

```text
/home/fqx/application-pnc/data/record/20261017-235550-cd3da3-crosswalk/crosswalk.record.00000.20261017235551
```

实际结果：

- 文件已生成，大小约 2080 bytes。
- `cyber_recorder` 进度始终为 `0 channels, 0 messages`。
- `timeout` 返回 124 是预期停止信号，不应直接判定为失败。
- 原因：当时没有启动 SimControl 场景，也没有 Planning / Control / Routing 模块输出。

### 2.3 channel 报告

执行：

```bash
python3 -m apollo_claw test report \
  --experiment 20261017-235550-cd3da3-crosswalk \
  --record /apollo_workspace/data/record/20261017-235550-cd3da3-crosswalk \
  --execute
```

生成：

```text
/home/fqx/application-pnc/data/record/report/20261017-235550-cd3da3-crosswalk/
  channel_summary.csv
  module_summary.csv
  record_report.md
```

报告结果：

- records = 1
- channels = 0
- selected_channels = 12
- parsed_channels = 0
- plots = 0

### 2.4 报告导出

执行：

```bash
python3 -m apollo_claw report export --experiment 20261017-235550-cd3da3-crosswalk
```

生成：

```text
/home/fqx/.apollo-claw/outputs/experiments/20261017-235550-cd3da3-crosswalk/report.json
/home/fqx/.apollo-claw/outputs/experiments/20261017-235550-cd3da3-crosswalk/report.md
```

当前 `meta.status = empty_record`，没有伪造评分或指标。

### 2.5 无 DeepSeek Key 的 explain

执行：

```bash
python3 -m apollo_claw explain \
  --experiment 20261017-235550-cd3da3-crosswalk \
  --log /home/fqx/application-pnc/mainboard.log.INFO.20261017-235414.1681 \
  --question "为什么录制不到 planning 和 control channel？"
```

结果：

- 自动进入规则降级模式。
- 返回事实：channel 数量为 0、record 状态为 empty。
- 返回建议：先启动 SimControl 场景和 Planning/Control/Routing 模块。
- 实验 manifest 保存了 4 条知识库片段和 1 份日志。

### 2.6 本地服务

已验证：

```text
GET /health             200
GET /api/tasks          200
GET /api/experiments    200
GET /api/latest         200
```

服务只监听 `127.0.0.1`。

## 3. 本轮发现并修复的问题

1. `aem --version` 不是有效命令，已改为 `aem version`。
2. `cyber_recorder` 的输出目录原先没有创建，已加入 `mkdir -p`。
3. record 的 `timeout` 返回 124 不能直接判定为失败，已改为根据 record 文件是否存在和大小判断。
4. `test report` 原先不解析 channel 数量，已从 `record_report.md` 提取 `channel_count` 和 `message_count`。
5. `explain` 原先会覆盖实验状态，已改为保留 `empty_record` 等真实状态。
6. 四个 skill 现在会同时安装到本地技能目录和 Apollo 工作区的 `.comate/skills`，容器内脚本路径可解析。

## 4. 阻塞项

未完成“真实场景 + 非空 record”的原因：

- 需要用 DreamView/SimControl 手动选择地图、车辆和场景，并启动 Planning/Control/Routing。
- 本轮浏览器访问 `http://localhost:8888` 被浏览器安全策略拒绝，不能由 AI 自动操作页面。
- 手动直接启动 planning 模块时，默认地图 `sunnyvale_big_loop` 不存在，启动失败。

因此需要在 DreamView 中手动打开有效场景后，再执行一次：

```bash
python3 -m apollo_claw test record --tag crosswalk --seconds 25 --execute
python3 -m apollo_claw test report --record <record-dir> --execute
python3 -m apollo_claw report export
```

## 5. 当前判断

Harness 本身已经具备：

- 环境检查
- 实验目录和状态管理
- 安全命令执行
- record / report / eval 入口
- 报告导出
- 无 Key 降级解释
- 本地只读面板

尚未完成的不是 Harness 代码，而是 Apollo 仿真场景启动和真实非空数据采集。
