# Apollo Claw Harness

Apollo Claw Harness 是运行在学生本地 WSL2 / Ubuntu 环境中的轻量实验编排器。它不做自动驾驶算法，也不自研完整 Agent 平台。

## 核心原则

> 脚本产出事实，模型解释事实，学生确认操作，系统保存证据。

设计说明见 [docs/harness-design.md](docs/harness-design.md)，技术选型见 [docs/technical-route.md](docs/technical-route.md)，实际运行记录见 [docs/runtime-test-2026-10-18.md](docs/runtime-test-2026-10-18.md)。

## 命令

```bash
apollo-claw doctor --json
apollo-claw explain --log <log-file>
apollo-claw advise --evidence <report.json>
apollo-claw test record --tag crosswalk --seconds 25
apollo-claw test report --record <record-dir>
apollo-claw eval --scenario <scenario.json> --bag <output.bag>
apollo-claw report export --experiment <experiment-id>
apollo-claw report build --experiment <experiment-id>   # 自评报告
apollo-claw report bundle --experiment <experiment-id> --baseline <baseline-report.json>  # 网站整合报告：场景指标 + 体感 + 建议
apollo-claw experiment list
apollo-claw experiment show --id <experiment-id>
apollo-claw serve --port 8765
```

`test record`、`test report`、`eval` 默认 dry-run；只有加 `--execute` 才进入 Apollo 容器执行。

## 自评报告

```bash
apollo-claw report build --experiment <id> --execute
```

一条命令跑完两件事：用 apollo-eval 的评分器逐帧判场景指标（到终点、超时、碰撞、在路、限速、加速度、急刹、横向加速度、TTC），再用 extract_metrics 算体感指标，最后合成一份 `selfeval.md`，带改进建议。

- 评分配置默认用包内的 `apollo_claw/defaults/metrics_selfeval.json`，可用 `--metric` 换成自己的。
- 场景文件省略时，会按实验的场景名在 `~/.apollo/resources/scenario_sets` 里自动匹配；报告里会写明用了哪个文件。
- 这份报告是**自评**，不是官方评分，阈值来自技能示例与知识库推荐值。

## 图形化面板

```bash
python3 -m apollo_claw serve --port 8765
```

打开 `http://127.0.0.1:8765/`。面板提供任务选择、环境检查、record、channel 报告、报告导出、DeepSeek API 配置、DeepSeek 诊断、任务控制台和实验报告摘要。面板只监听本机，并通过启动时生成的一次性 token 保护受控动作；不提供任意命令输入。


## 目录

```text
harness/
  apollo_claw/        Python package
    experiment.py     实验 manifest 和目录
    runner.py         白名单命令执行器
    report.py         报告契约、脱敏和导出
    server.py         本地图形化面板和受控动作 API
  docs/               技术路线和设计稿
  examples/           示例报告
  scripts/            安装、启动和检查脚本
  skills/             四个 Apollo Claw skill 的放置位置
  report.schema.json  统一报告数据契约
  tests/              轻量单元测试
```

## 环境

- 目标环境：WSL2 Ubuntu 22.04 / Ubuntu 主机。
- Apollo 容器默认名：`apollo_neo_dev_edu`。
- 本地图形面板默认：`http://127.0.0.1:8765/`。
- DeepSeek Key 仅保存在 `~/.apollo-claw/.env`。
- 技能目录默认：宿主侧 `~/.apollo-claw/skills/{apollo-env,apollo-dev,apollo-test,apollo-eval}`；安装脚本还会同步到容器可见的 `~/application-pnc/.comate/skills`。

## 安装

```bash
cd harness
bash scripts/install-harness.sh
```

如果四个技能已经在 `~/.openclaw/skills`：

```bash
APOLLO_SKILLS_SOURCE="$HOME/.openclaw/skills" bash scripts/install-harness.sh
```

## 测试

```bash
python3 -m unittest discover -v
```

## 安全边界

- 不自动执行 `sudo`、删除数据、覆盖配置或大规模修改 Apollo 源码。
- 不自动修改 Apollo 源码。
- 不把 API Key、record 原始数据和隐私信息提交到 Git。
- 模型只生成建议，不直接执行命令。
- 本地面板只监听 `127.0.0.1`，使用启动时生成的一次性 token 调用受控动作，不提供任意命令输入。
- 面板操作按钮会显示忙碌状态和计时；报告生成后可直接打开 report.json、report.md、selfeval.md 和 doctor.json。
