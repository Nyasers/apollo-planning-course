# Apollo Claw Harness 技术路线

## 参考的现成方案

本 Harness 只借鉴成熟项目的架构，不直接复制代码，也不引入重依赖。

- `openai/openai-agents-python`：借鉴工具、护栏、人工确认、会话等概念，但 MVP 不引入该 SDK。
- `simonw/llm`：借鉴 CLI 与模型适配器分离，保证以后可以切换 DeepSeek、Qwen 或本地模型。
- `Aider-AI/aider`：借鉴命令行工具的分层、配置、运行反馈和仓库感知体验。
- `pydantic/pydantic-ai`：借鉴结构化输出和类型约束，Harness 使用 JSON Schema 约束报告。
- `All-Hands-AI/OpenHands`、`block/goose`：借鉴沙箱、白名单执行和人工确认边界。

## 技术选型

| 层 | MVP 选型 | 原因 |
|---|---|---|
| CLI | Python argparse | 无额外依赖，容易分发 |
| 配置 | `.env` + 环境变量 | 与 WSL、Docker、DeepSeek 兼容 |
| 执行 | subprocess + docker exec | 复用现有 Apollo 容器 |
| 模型 | DeepSeek OpenAI-compatible API | 学生自备 Key，成本低 |
| 数据 | JSON + Markdown + CSV + PNG | 便于网页显示和教师复核 |
| 本地面板 | Python 标准库 http.server | MVP 不引入 Web 框架 |
| 知识库 | Markdown 文本检索 | 先不引入向量数据库 |

## 分层

```text
CLI
  -> Router
  -> Runner / Knowledge / Model
  -> Evidence Store
  -> Report Export
  -> Local Panel
```

## 安全设计

- 命令白名单。
- 危险命令必须二次确认。
- 模型只生成建议，不直接执行。
- API Key 只从 `~/.apollo-claw/.env` 读取。
- 日志、record 和报告默认只保存在本地。
- 报告中的路径和敏感字段需要脱敏。
