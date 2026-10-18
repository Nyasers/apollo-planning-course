# Planning 模块打不开 / 无法启动 — 完整恢复指南

## 症状

- DreamView 中点击 Planning 模块按钮无反应或模块变红
- `mainboard -d .../planning.dag` 启动后立即退出，终端报 Segfault / 配置缺失 / 符号未找到
- 编译报错导致无法生成可执行文件
- 改动代码或配置后模块崩溃，回滚困难

---

## 原因

| 原因类别 | 典型表现 |
|---------|---------|
| 源码改坏 | 编译不过 / 运行时 Segfault |
| 配置文件损坏或缺失 | 启动时报 `Failed to load config` 或参数越界 |
| profile 软链断裂 | `profiles/current` 指向已删除的目录 |
| 包版本不一致 | `reinstall` 前后二进制与配置不匹配 |

---

## 修复步骤（完整恢复流程）

> 所有命令在**容器内**（`aem enter` 后）的 `/apollo_workspace` 目录下执行。

### 第一步：备份现有代码和配置

```bash
tar -zcvf planning_backup.tar.gz modules/planning/
tar -zcvf profiles_default_backup.tar.gz profiles/default/
```

> 即使代码已损坏，备份也能保留你的改动记录，必要时可 diff 找回逻辑。

### 第二步：创建临时 profile 并切换

```bash
mkdir -p profiles/tmp
aem profile use tmp
```

> **为什么要这一步？** 如果 `profiles/current -> default` 软链还存在时直接删除 `profiles/default`，软链会断裂，后续 `aem profile use default` 可能失败。先切到 `tmp` 可以安全释放 `default`。

### 第三步：清理损坏的代码和配置

```bash
rm -rf profiles/default
rm -rf modules/planning
```

### 第四步：重装所有 planning 包

```bash
buildtool reinstall planning*
```

`reinstall` 会重新拉取所有 planning 相关包的二进制和配置，恢复到官方初始状态。

### 第五步（可选）：重新下载源码

仅在需要继续修改源码时执行：

```bash
buildtool install planning*
```

### 第六步（可选）：编译

仅在下载了源码后执行：

```bash
buildtool build -p modules/planning/
```

### 第七步：重建并启用 default profile

```bash
buildtool profile config init --package planning --profile=default
aem profile use default
```

验证软链：

```bash
ll profiles/current   # 应显示 current -> default
```

### 第八步：验证 Planning 是否恢复正常

用 `mainboard` 单独启动，观察终端是否有报错：

```bash
mainboard -d /apollo/modules/planning/planning_component/dag/planning.dag
```

无报错后再通过 DreamView 启动完整仿真。

---

## 完整命令速查（复制即用）

```bash
# 容器内 /apollo_workspace 下执行
tar -zcvf planning_backup.tar.gz modules/planning/
tar -zcvf profiles_default_backup.tar.gz profiles/default/
mkdir -p profiles/tmp
aem profile use tmp
rm -rf profiles/default
rm -rf modules/planning
buildtool reinstall planning*
# （如需源码开发）buildtool install planning*
# （如需编译）buildtool build -p modules/planning/
buildtool profile config init --package planning --profile=default
aem profile use default
```

---

## 注意事项

- `rm -rf profiles/default` 会删除你在 `profiles/default` 下手动修改的所有配置参数。备份（步骤一）务必执行。
- 如果只是配置文件损坏（源码没问题），可以跳过步骤 5-6，只执行步骤 7 重建配置即可。
- 恢复后如果仍然报错，检查 `.aem/envroot/opt/apollo/neo/share/modules/planning` 下的包是否完整，必要时 `aem start -f` 更新镜像后重试。
