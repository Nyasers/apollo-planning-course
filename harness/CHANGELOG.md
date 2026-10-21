# 变更记录

## 0.5.1（2026-10-21）

- Harness 侧栏任务清单统一为实验一至实验九，并标注“可开始/待接入”。
- 安装包内置任务清单，脱离仓库运行时也能加载完整实验列表。

- 完善 Bauhaus Mecha Lab 环境动效：网格漂移、路径流动、雷达旋转和低对比扫描线。
- 面板、指标、任务、步骤和助手卡片支持鼠标跟随的局部边缘高亮，Hero 增加轻微视差反馈。
- 录制中状态点脉冲、运行中控制台扫描线使用克制的状态动效，不干扰实验信息阅读。
- 跟随光效仅在精细指针设备启用；触屏、移动端和 `prefers-reduced-motion` 自动降级。
- 完成桌面与移动布局、浏览器控制台、JavaScript 语法及 27 项单元测试回归。

## 0.5.0（2026-10-21）

- Harness 视觉系统升级为 Bauhaus Mecha Lab。
- 新增原创路径分叉品牌图标、实验场景缩略图和 Apollo Claw 助手形象。
- 顶栏、侧栏、Hero、指标卡、流程卡、控制台和报告区统一为几何网格与低圆角设计。
- 去掉大面积 AI 渐变、发光和薄荷绿品牌色，改为工程蓝、信号橙与语义状态色。
- 任务切换会同步更新当前场景图。
- 日志区使用低对比技术底图，AI 区域加入低透明度助手水印。
- 新增本地图片资源路由和 WebP 静态资源打包。
## 0.4.2（2026-10-21）

- AI 报告新增 `ai.presentation` 结构化展示数据。
- 网站默认展示一句话结论、关键指标卡、原因解释和分步行动清单。
- 参数名自动附带中文名称、单位、参考阈值和通俗解释。
- 原始事实、模型推测和引用移入可展开的技术细节区。
- 报告缓存版本更新，重新导入后会自动替换旧版内容并保持 UTF-8 中文显示。
## 0.4.1（2026-10-21）

- 环境检查现在会绑定当前选中的实验，不再另外创建无关实验。
- 自评 AI 结果新增 `ai.skills` 和 `ai.skill`，网站报告可正确展示使用的技能。
- 网站端兼容旧版仅包含 `ai.skill` 的报告。
- 修复报告导入后“环境检查”和“AI 技能”为空的问题。
## 0.4.0（2026-10-21）

- 新增透明综合自评分：关键指标门槛 + 性能分 80% + 舒适性分 20%。
- 关键指标失败时该场景综合自评分为 0；缺失舒适指标时自动回退为性能分。
- 舒适性分使用纵向加速度、Jerk、横向加速度和急刹车四项，单项阈值来自 `apollo-eval` 技能。
- 报告增加 `performance_score`、`comfort_score`、`gate_status` 和逐项舒适性扣分依据。
- 页面将数值分数明确标记为“非官方自评”，同时保留通过项和官方导入扩展能力。
## 0.3.8（2026-10-21）

- 录制改为完全由用户手动结束，移除目标秒数、自动停止计时器和 25 秒限制。
- 页面录制状态统一显示“手动结束”；暂停与继续仍保留。
- 停止录制只由“结束并保存”或退出仿真触发。
## 0.3.7（2026-10-20）

- 修复 report/eval 脚本把 Windows 路径直接传进 Apollo 容器的问题。
- 生成报告、自评和评分前自动把 `harness/skills` 同步到 WSL 工作区的 `.comate/skills`。
- 报告任务自动使用 record 目录，合并分析同一实验的多个 `.record.*` 分片。
- 报告成功后清理旧的 `test-report` 失败记录，避免 AI 继续引用已修复问题。
## 0.3.6（2026-10-20）

- 第 02 步新增“退出仿真”按钮与二次确认。
- 退出流程会停止 DreamView、终止录制和 Apollo 守护进程、停止容器，并执行 `wsl.exe --shutdown`。
- 退出后自动刷新分层环境状态，确认 Linux、Docker、Apollo 和 DreamView 全部停止。

## 0.3.5（2026-10-20）

本版把 Harness 从“打开一个网址”改成可操作真实本地仿真生命周期的工作台。

### 新增

- 环境检查改为分层诊断：Linux/WSL、Docker、Apollo 容器、DreamView 分别展示状态，只有四层全部就绪才标记仿真已启动。
- “去启动”改为真实启动动作：先弹出二次确认，再进入 WSL 执行 `start-apollo.sh`，成功后自动打开 DreamView。
- 录制改造为可控制的 `cyber_recorder` 会话：开始、暂停、继续、结束并保存；暂停不会停止仿真，只停止记录 channel 消息。
- 录制到达目标秒数后自动结束；页面每 2.5 秒同步会话状态和有效录制时长。
- 新增 `/api/runtime`，供页面无副作用地读取当前分层运行状态。
- 修复 Apollo 容器启动后迅速退出的问题：启动脚本现在会拉起持久守护进程，为交互式容器主 bash 提供持续 stdin，并让 WSL 保持运行。
- Windows 上的容器命令统一经 WSL 代理执行，不再依赖不存在的 Windows `docker.exe`。
- Windows 默认工作区映射改为 `\\wsl.localhost\<distro>\home\<user>\application-pnc`，修复录制文件已生成但 Harness 读不到的问题。

### 说明

- 启动脚本默认读取 `APOLLO_START_SCRIPT=/home/fqx/start-apollo.sh`，WSL 发行版和用户可通过 `APOLLO_WSL_DISTRO`、`APOLLO_WSL_USER` 配置。
- 真实录制前会再次检查仿真是否就绪；只有 DreamView、Apollo 容器和 Docker 均正常时才会启动录制。

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

### 面板交互与报告文件（2026-10-18）

- 操作按钮点击后立即进入 busy 状态，显示旋转指示、禁用重复点击，并按秒显示“处理中/录制中”。
- 增加 workflow status 和 toast，明确展示提交、运行、完成和失败状态。
- 修复 token 注入：只替换 token 值，不替换 `window.__APOLLO_CLAW_TOKEN__` 属性名。
- 新增 `/api/experiments/<id>/files/<name>`，可在面板中直接打开 `report.json`、`report.md`、`selfeval.md` 和 `doctor.json`。
- 报告摘要下方新增报告文件链接；工具仅允许读取白名单文件。

### 网站整合报告（2026-10-19）

- 新增 `apollo-claw report bundle`，把当前报告和 baseline 报告合并成 `lab-report.json` / `lab-report.md`。
- 整合报告包含：基线对比、人工核验、警告、下一步、证据清单和报告文件清单。
- 网站实验报告页支持导入 `lab-report.json`，显示基线/本轮对比、人工核验和报告文件。
- 已生成第二轮样例：`lab-report-round2.json` 和 `lab-report-round2.md`。
