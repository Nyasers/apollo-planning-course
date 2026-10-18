# 提交前测试 Checklist

> 在打包提交前，逐项完成以下检查，确保提交包质量。

---

## Checklist 总览

```
[ ] 1. 代码编译通过（无 ERROR）
[ ] 2. 单元测试通过（无 FAILED）
[ ] 3. 数据包回放验证通过
[ ] 4. profile 配置正确加载
[ ] 5. 目标场景仿真通过
[ ] 6. 打包文件完整
```

---

## 详细步骤

### 1. 代码编译通过

```bash
# 在容器内
buildtool build -p modules/planning/

# 期望输出：
# INFO: Build completed successfully, N total actions.
```

**常见问题**：如果有编译错误，先修复后再继续。编译错误不影响仿真，但评测可能重新编译。

---

### 2. 单元测试通过

```bash
# 运行 planning 所有单测
buildtool test -p modules/planning/

# 期望输出：
# Executed N out of N tests: N tests pass.
```

**如果有 FAILED**：
- 查看测试日志定位失败原因
- 修复后重新运行，确保全部 PASSED
- 如果是已知不相关的测试失败，记录说明

---

### 3. 数据包回放验证通过

改完 Planning 代码后，必须用原始 case bag 验证新代码是否真正参与运行。不要直接播放完整 record 后观察旧的 `/apollo/planning` 输出。

```bash
# 启动本地 Planning 模块
mainboard -d modules/planning/dag/planning.dag

# 回放时屏蔽 bag 中旧的 Planning/Control 输出
cyber_recorder play -f /path/to/xxx.record \
  -k /apollo/planning \
  -k /apollo/control \
  --loop
```

**期望**：Planning 日志实时输出，原问题现象消失，无新增 ERROR。

---

### 4. profile 配置正确加载

```bash
# 重新加载 profile（编译后必须执行！）
aem profile use default

# 验证关键配置文件存在
ls profiles/default/modules/planning/

# 验证软链指向正确
readlink -f profiles/default/modules/planning/planning.pb.txt
```

**期望**：软链最终指向 `/apollo_workspace/profiles/default/modules/planning/planning.pb.txt`，不是容器内的 `/apollo/` 路径。

---

### 5. 目标场景仿真通过

在 DreamView 中逐一验证所有目标场景：

```bash
# 启动 DreamView
aem bootstrap start --plus
# 打开 http://localhost:8888
```

对每个目标场景：
- [ ] 车辆成功到达终点
- [ ] 无碰撞
- [ ] Planning 模块全程绿色（无崩溃）
- [ ] 场景特定动作完成（停止线前停车、完成借道等）

**至少运行 2 次**每个场景，确保结果稳定。

---

### 6. 打包文件完整

根据修改内容选择打包方式：

```bash
# 只修改了配置参数（最常见）
tar -zcvf 提交包.tar.gz profiles/default/

# 修改了源码（含插件开发）
tar -zcvf 提交包.tar.gz modules/planning/ profiles/default/

# 验证包内容
tar -tzvf 提交包.tar.gz | head -30

# 验证包大小是否合理（纯配置约几十 KB，含代码约几十 MB）
du -sh 提交包.tar.gz
```

**关键检查**：
- `profiles/default/` 中包含自定义的 `.pb.txt` 配置文件
- 如果有新增插件，`modules/planning/traffic_rules/` 或 `scenarios/` 下包含新文件
- 不要包含临时文件（`.cache/`、`data/bag/`、`*.log` 等）

---

## 快速重置与验证脚本

```bash
#!/bin/bash
# 提交前全量验证（在容器内执行）
set -e

echo "=== Step 1: 编译 ==="
buildtool build -p modules/planning/

echo "=== Step 2: 单元测试 ==="
buildtool test -p modules/planning/ || {
  echo "单元测试失败，请修复后重试"
  exit 1
}

echo "=== Step 3: 数据包回放验证 ==="
echo "请使用 /apollo-test bag 或手动执行："
echo "  mainboard -d modules/planning/dag/planning.dag"
echo "  cyber_recorder play -f /path/to/xxx.record -k /apollo/planning -k /apollo/control --loop"

echo "=== Step 4: 恢复 Profile ==="
aem profile use default

echo "=== Step 5: 验证关键配置存在 ==="
test -f profiles/default/modules/planning/planning.pb.txt && \
  echo "planning.pb.txt: OK" || echo "WARNING: planning.pb.txt 不存在"

echo ""
echo "编译和测试均通过！请在 DreamView 中手动验证仿真场景，然后打包。"
echo ""
echo "打包命令（按需选择）："
echo "  配置+代码: tar -zcvf 提交包.tar.gz modules/planning/ profiles/default/"
echo "  仅配置:   tar -zcvf 提交包.tar.gz profiles/default/"
```

保存为 `/apollo_workspace/pre_submit_check.sh`，每次提交前运行：

```bash
bash /apollo_workspace/pre_submit_check.sh
```
