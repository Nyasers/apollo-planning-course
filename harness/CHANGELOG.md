# 变更记录

## 0.3.4（2026-10-18）

在 0.3.3（commit 8aab429）基础上做的一轮本机实测与改造。定位收窄为：**录制仿真 → 基础自评 → 改进建议**，不追求官方评分口径。

### 新增

- `apollo-claw report build --experiment <id> --execute`
  一条命令跑完：九项场景指标 + 体感指标 + 模型分析，输出 `selfeval.md`，并同步刷新 `report.json` / `report.md`。
- `apollo_claw/defaults/metrics_selfeval.json`
  自评用评分配置，九项指标，每项阈值在文件头 `_sources` 里注明出处（技能示例 / 场景文件 / 本项目自定）。
- `report build` 的场景自动匹配：按实验场景名在 `~/.apollo/resources/scenario_sets` 里找对应 `scenario.json`，匹配结果写进报告头部。
- 面板工作流新增第 05 步“生成自评”，服务端新增 `POST /api/actions/selfeval`。
- 报告新增：录制结束时距终点的距离、Jerk 峰值时刻、Jerk P95。
- 模型分析为主输出：`## 分析` 段由 DeepSeek 生成（事实/推测/建议/待确认），标注“数字与判定来自脚本”；无 Key 或调用失败时自动降级为规则模板，报告结构不变。

### 修复

| 问题 | 影响 | 处理 |
|---|---|---|
| record 路径记成 `*.record` 基名，实际文件是 `*.record.00000.<时间戳>` | `test report` 报 FileNotFoundError，实验状态变 `report_failed` | 录制后记录真实文件名；报告接受基名并回退到目录 |
| `eval` 把 `--scenario` 传给 `--config`，且从不传 `--scenario` | 评分命令必挂 | 改为 `--config <metric> --scenario <scenario> --bag <bag>`，`--bag` 省略取当前实验 record |
| `doctor` 会把 `recorded/reported` 状态改回 `environment_checked` | 状态倒退 | 只允许从 created/environment_* 升级 |
| 证据重复写入 | report.json 里同一路径出现两次 | `add_evidence` 按 type+path 去重 |
| `extract_metrics.py` 依赖 pip 包 `cyber_record` | 容器里没有，直接 ModuleNotFoundError | 回退到 Apollo 自带 `cyber.py`/`cyber_py3` |
| 容器 locale 是 ASCII，中文 print 抛 UnicodeEncodeError | 真实错误被掩盖 | 脚本内换容错编码；`docker_exec` 补 `PYTHONIOENCODING/LANG/LC_ALL` |
| 体感重采样取“最近的原始帧” | 定位断档时间隔忽大忽小（0.05s/0.14s），Jerk 被放大到 43 | 改为固定 0.1s 网格线性插值，同一份数据降到 12.36 |
| `grading_system_py` 计算加速度时不防小 `dt` | 算出 94152 m/s²，AccelerationLimit 误判 | `dt < 0.02s` 时加速度记 0 |
| 体感报告“超限 148 次”与“全部通过”同时出现 | 结论自相矛盾 | 按实际超限条目判断，并区分“扣分”与“仅超限” |
| 面板录制复用当前实验 | 同一目录堆多份 record，报告混算 | 已 recorded 的实验默认新建；可用 `reuse_experiment: true` 强制复用 |
| 面板诊断框占位路径写死 `/home/fqx` | 与实际用户不符 | 改为 `~/application-pnc/...` |
| 模型读到早已修复的旧错误 | 把已解决的问题当成现报 | 本轮调用成功后清除同来源旧失败记录 |
| 模型引用未提供的知识库文档 | 引用幻觉 | 提示词限定只能引用 `evidence.knowledge` 里的文件名 |

### 安装注意

技能必须放进**容器能看到的目录**，否则 `test report` 会找不到脚本：

```bash
mkdir -p ~/application-pnc/.comate/skills
cp -a harness/skills/* ~/application-pnc/.comate/skills/
```

容器用户不是 `fqx` 时，在 `~/.apollo-claw/.env` 里设置：

```bash
APOLLO_CONTAINER_USER=<你的用户名>
```

DreamView 启动需要 `APOLLO_DISTRIBUTION_VERSION=9.0`，否则 `aem bootstrap` 会 fallback 到 8.0 并报 `buildtool: command not found`。

### 主仓库维护修正（2026-10-18）

- record 成功后证据记录实际 `*.record.00000.*` 文件，而不是不存在的基名，避免 report.json 中出现两条 record 证据。
- TTC 未通过且原始分数为 100 时，在统一报告中将分数归一为 `null`，避免“失败但显示满分”。
- `report build` 在当前实验缺少 environment 数据时输出警告，提示绑定同一个 experiment 运行 doctor。
- `record_channel_report.py` 的最近障碍物距离改为障碍物坐标减自车定位坐标，修复 4e6 量级距离图。
- 网站实验报告页支持导入真实 report.json，展示环境状态、九项场景指标和 PASS/FAIL。
- site harness 元数据更新为 0.3.4 / selfeval-ready。
