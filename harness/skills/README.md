# Skills 放置目录

Harness 不内置四个 Apollo Claw skill，安装时把外部 skill 复制到本地目录：

```text
~/.apollo-claw/skills/
  apollo-env/
  apollo-dev/
  apollo-test/
  apollo-eval/
```

也可以通过环境变量指定：

```bash
export APOLLO_CLAW_SKILLS_DIR="$HOME/.openclaw/skills"
```

`scripts/install-harness.sh` 默认从 `$HOME/.openclaw/skills` 复制；若路径不同，使用：

```bash
APOLLO_SKILLS_SOURCE=/path/to/skills bash scripts/install-harness.sh
```

Harness 只读取其中的 Markdown 知识库和脚本路径，不重写官方 skill 内容。

安装脚本还会把四个 skill 复制到 `~/application-pnc/.comate/skills/`，该目录在 Apollo 容器内对应 `/apollo_workspace/.comate/skills/`。这样 `test report` 和 `eval` 可以在容器内找到脚本。
