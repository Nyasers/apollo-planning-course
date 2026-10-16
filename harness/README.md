# Apollo Claw Harness

Apollo Claw Harness 是运行在学生本地 WSL2 / Ubuntu 环境中的轻量实验编排器。它不做自动驾驶算法，也不自研完整 Agent 平台。

## 核心原则

> 脚本产出事实，模型解释事实，学生确认操作，系统保存证据。

## 命令

```bash
apollo-claw doctor --json
apollo-claw explain --log <log-file>
apollo-claw advise --evidence <report.json>
apollo-claw test record --tag crosswalk --seconds 25
apollo-claw test report --record <record-dir>
apollo-claw eval --scenario <scenario.json> --bag <output.bag>
apollo-claw report export --evidence <evidence.json>
apollo-claw serve --port 8765
```

## 目录

```text
harness/
  apollo_claw/        Python package
  docs/               技术路线和交接说明
  examples/           示例报告
  scripts/            启动和安装脚本
  skills/             四个 Apollo Claw skill 的放置说明
  report.schema.json  统一报告数据契约
```

## 环境

- 目标环境：WSL2 Ubuntu 22.04 / Ubuntu 主机。
- Apollo 容器默认名：`apollo_neo_dev_edu`。
- 本地面板默认：`http://127.0.0.1:8765/`。
- DeepSeek Key 仅保存在 `~/.apollo-claw/.env`。

## 安全边界

- 不自动执行 `sudo`。
- 不自动删除数据或覆盖配置。
- 不自动修改 Apollo 源码。
- 不把 API Key、record 原始数据和隐私信息提交到 Git。
- 模型只生成建议，不直接执行命令。
