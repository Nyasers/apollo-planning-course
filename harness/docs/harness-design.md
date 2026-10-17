# Apollo Claw Harness 设计稿

> 版本：0.3.3（设计 + P0 骨架 + 任务控制台主题 + DeepSeek 自主配置）
> 日期：2026-10-17
> 目标：在学生本地 WSL2 / Ubuntu 中，把“环境检查 → 仿真运行 → record → channel 报告 → 自评估 → AI 解释 → 实验报告”组织成可审计的确定性流程。

## 1. 设计目标与非目标

### 目标

1. 每个实验都有唯一的 `experiment_id` 和独立目录。
2. 所有命令、原始 stdout/stderr、证据文件和错误都能追溯。
3. 无 DeepSeek Key 时仍能完成环境检查、录包、报告和规则降级解释。
4. 模型只解释证据，不执行命令，不直接决定成绩。
5. 报告契约与 `apc.nyase.ru/lab/` 的导入格式一致。
6. 默认只监听 `127.0.0.1`，不把本地服务和 API Key 暴露到公网。

### 非目标

- 不在 MVP 中实现完整 Agent 平台。
- 不自动修改 Apollo 源码或配置。
- 不自动执行 `sudo`、删除数据或重建容器。
- 不把演示数据写成真实实验数据。
- 不在本机 FQX 电脑上跑重型 Apollo 仿真、编译和长时间录包。

## 2. 参考的 GitHub 方案

本 Harness 只借鉴架构思路，不引入它们的运行时依赖：

| 项目 | 借鉴点 | 本项目落地 |
|---|---|---|
| `openai/openai-agents-python` | 工具调用、护栏、人在回路、可追踪执行 | 每个技能是受限工具；执行前 human confirmation；命令和证据落盘 |
| `simonw/llm` | CLI 与模型适配器解耦，支持多模型后端 | `deepseek.py` 只负责模型适配，未来可替换 Qwen/GLM/OpenAI-compatible |
| `Aider-AI/aider` | 命令分层、配置集中、运行反馈清晰 | `argparse` + `Settings` + 结构化命令结果 |
| `pydantic/pydantic-ai` | 结构化输出、类型和 schema 约束 | `report.schema.json` + `validate_report()` |
| `All-Hands-AI/OpenHands`、`block/goose` | 沙箱、白名单、人工确认、最小权限 | `runner.py` 白名单；API 只读；模型不执行命令 |

设计原则是“借用边界，不复制框架”。

## 3. 分层架构

```text
CLI
  ├─ experiment manifest / store
  ├─ doctor        -> apollo-env 检查
  ├─ test record   -> apollo-test / cyber_recorder
  ├─ test report   -> apollo-test 报告脚本
  ├─ eval          -> apollo-eval 评分脚本
  ├─ explain/advise-> 知识库 + DeepSeek（或规则降级）
  └─ report export -> report.json / report.md
          |
          v
    ExperimentStore
      outputs/experiments/<id>/
        experiment.json
        doctor.json
        commands/*.stdout.txt
        commands/*.stderr.txt
        report.json
        report.md
        record/ 或外部 record 路径
```

## 4. 实验状态机

```text
created
  -> environment_checked
  -> environment_warning
  -> recorded
  -> reported
  -> evaluated
  -> ai_explained
  -> completed

任一阶段失败：
  -> * _failed
  -> 错误写入 errors[]
```

状态只用于教学流程和界面摘要，不等于官方评分。

## 5. 六个核心命令

```bash
apollo-claw doctor --json
apollo-claw explain --log <log-file> --experiment <id>
apollo-claw test record --seconds 25 --execute
apollo-claw test report --record <record-path> --execute
apollo-claw eval --scenario <scenario.json> --bag <bag-path> --execute
apollo-claw advise --evidence <report.json>
apollo-claw report export --experiment <id>
```

所有 `record`、`test report`、`eval` 默认 dry-run；只有显式加 `--execute` 才进入容器执行。

## 6. 统一报告契约

报告以 `report.json` 为唯一数据源，字段包括：

- `meta`：实验编号、任务、场景、时间、状态、是否真实数据。
- `environment`：WSL、Docker、aem、Apollo 容器、工作区。
- `record`：record 路径、时长、channel 数量。
- `metrics`：TTC、加速度、Jerk、急刹、碰撞、到达终点。
- `score`：来源、数值、是否官方评分。
- `ai`：事实、推测、建议、引用、学生确认。
- `verification`：优化前后对比。
- `evidence`：record、CSV、PNG、评分、报告。
- `capability`：环境诊断、日志定位、数据采集、参数优化、报告表达、AI 使用规范。

缺失指标必须为 `null`，不能用 0 或示例数字补齐。报告导出前会执行契约校验和路径脱敏。

## 7. 安全与隐私

- `runner.py` 只接受白名单命令。
- 容器命令使用 argv 列表，不把用户输入直接拼成 shell。
- 默认不执行 `sudo`、`rm`、`git push`、容器重建。
- API Key 只从 `~/.apollo-claw/.env` 读取。
- 报告导出会脱敏 `sk-...`、`DEEPSEEK_API_KEY=...`、用户 home 绝对路径。
- 本地图形面板只监听 `127.0.0.1:8765`，使用一次性 token 调用白名单动作；不提供任意命令输入。
- 静态课程网站不直接请求本地 Harness API；通过链接打开本地图形面板，或导入本地 `report.json`。

## 8. 与网站的关系

```text
apc.nyase.ru
  └─ 课程、实验引导、静态报告页
         |
         v
  127.0.0.1:8765
  └─ 本地 Harness 面板 / 真实报告
         |
         v
  ~/.apollo-claw/outputs/experiments/<id>/
```

网站不承担仿真计算；本地 Harness 不负责课程内容。二者通过 `report.json` 和任务 ID 连接。

## 9. 当前实现状态

已实现：

- 实验 manifest 和独立目录。
- `doctor` 轻量检查。
- record/report/eval 的 dry-run 和容器执行入口。
- 白名单 runner、命令输出落盘。
- `explain` / `advise` 的 DeepSeek 与规则降级。
- 报告契约校验、路径脱敏、`report.json` / `report.md` 导出。
- 本地图形面板、任务流程、受控动作、实验列表、报告查看、DeepSeek API 本地配置和 AI 诊断。
- 单元测试：manifest、证据路径、报告契约、API Key 防泄漏、模型输入脱敏、后台动作和静态前端。

仍需在独立 Ubuntu/Apollo 机器上验证：

- 真实 Docker / aem / DreamView。
- 20-30 秒 `record`。
- channel 报告脚本的真实路径和产物。
- `apollo-eval` 的 metric/scenario/bag 输入。
- 真实 DeepSeek 调用与网页 `report.json` 导入。
