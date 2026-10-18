# 如何提取 Planning 日志

> 本文说明在 Apollo EDU 环境中提取 Planning 模块运行数据的两种方式：文本日志 和 cyber record 回放。

---

## 一、日志文件路径

所有命令在**容器内**（`aem enter` 后）的 `/apollo_workspace` 目录下执行。

| 日志类型 | 路径 | 说明 |
|---------|------|------|
| Planning 文本日志 | `/apollo_workspace/data/log/planning.INFO` | 实时输出的可读日志 |
| Planning 错误日志 | `/apollo_workspace/data/log/planning.ERROR` | 仅包含 ERROR 级别 |
| cyber record 数据包 | `/apollo_workspace/data/bag/` | 二进制录包，含所有 channel 数据 |

---

## 二、方式一：直接读取文本日志

适用于**快速排查**，不需要安装额外工具。

```bash
# 查看 Planning 实时输出（运行仿真时执行）
tail -f /apollo_workspace/data/log/planning.INFO

# 搜索特定场景或关键词
grep "crosswalk" /apollo_workspace/data/log/planning.INFO

# 查看规划速度输出
grep "speed" /apollo_workspace/data/log/planning.INFO | tail -100

# 查看报错
grep -E "ERROR|WARN|Segfault" /apollo_workspace/data/log/planning.INFO | tail -50
```

---

## 三、方式二：cyber record 录包与回放

适用于**定量分析**，可提取精确的速度/加速度数据。

### 3.1 开始录包

在**宿主机**新开终端执行（不影响仿真运行）：

```bash
cd application-pnc
aem enter

# 开始录制所有 channel
cyber_recorder record -a -o /apollo_workspace/data/bag/my_record.record

# 录制特定 channel（更小的文件）
cyber_recorder record \
  -c /apollo/planning/trajectory \
  -c /apollo/localization/pose \
  -c /apollo/prediction/prediction_obstacles \
  -o /apollo_workspace/data/bag/my_record.record
```

### 3.2 停止录包

```bash
# Ctrl+C 停止，或另一终端：
cyber_recorder stop
```

### 3.3 查看 record 基本信息

```bash
cyber_recorder info /apollo_workspace/data/bag/my_record.record
```

输出示例：
```
record_file: my_record.record
version:     1.0
duration:    45.2 s
begin_time:  2026-05-11 10:23:01
end_time:    2026-05-11 10:23:46
size:        12.3 MB
channels:
  /apollo/planning/trajectory       (1200 msgs)
  /apollo/localization/pose         (4500 msgs)
```

### 3.4 回放 record

```bash
# 回放（DreamView 会显示录制时的场景）
cyber_recorder play -f /apollo_workspace/data/bag/my_record.record

# 循环回放
cyber_recorder play -f my_record.record -l

# 指定速率回放（0.5 = 半速）
cyber_recorder play -f my_record.record -r 0.5
```

---

## 四、提取 Planning 轨迹数据（用于指标计算）

使用 Python 脚本解析 cyber record，见：
`../02_数据分析/01_轨迹指标提取脚本.md`

### 快速查看轨迹中的速度字段

```bash
# 在容器内，用 cyber_tools 查看轨迹消息
cyber_tools echo --channel /apollo/planning/trajectory | head -200
```

输出中找到 `trajectory_point` 下的 `v`（速度）和 `a`（加速度）字段。

---

## 五、清理旧日志（磁盘满时）

```bash
# 查看日志占用
du -sh /apollo_workspace/data/log/
du -sh /apollo_workspace/data/bag/

# 删除旧文本日志（保留最新的）
find /apollo_workspace/data/log/ -name "*.log.*20[0-9][0-9]*" -type f -delete

# 删除旧 record 包（谨慎，确认不需要后删除）
rm /apollo_workspace/data/bag/old_record.record
```
