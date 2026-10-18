---
name: apollo-dev
description: Apollo EDU PnC 赛道开发助手与日常工作流引导工具。当用户遇到以下场景时使用此 Skill：(1) 每日开发启动（电脑重启后进入 Apollo、aem start、aem enter）(2) PnC/Planning 开发（TrafficRule 插件、Scenario 插件、Task 插件、参数配置）(3) 赛事场景调试（借道绕行、交汇路口减速、人行道避让、自主泊车、动态避障等 10+ 场景）(4) 模块调试与排错（mainboard 启动、Planning 打不开、Dreamview 地图不加载、buildtool install）(5) 配置与提交（profile 管理、打包提交、编译后配置丢失）(6) Git 代码管理（分支、回退、保存改动）(7) 赛事资源（场景地图下载、赛事报名）(8) 硬件传感器适配。触发关键词：PnC、Planning、规划、场景、插件、TrafficRule、Scenario、Task、profile、Dreamview、SimControl、星火大赛、赛事开发、借道、泊车、交汇、人行道、动态避障、buildtool install、aem enter、mainboard、编译后配置丢失、打包提交、Git、日志、地图下载、传感器。命令入口：/apollo-dev。
default-enabled: false
---

# Apollo EDU PnC 开发助手

集成日常工作流引导、PnC 场景开发、模块调试和知识库检索，覆盖 Apollo EDU 赛事（PnC 赛道）装好环境后的全部开发活动。

**知识库路径**：`{BASE_DIR}/references/knowledge/`
**配置文件**：`{BASE_DIR}/config.yaml`
> `{BASE_DIR}` 为本 skill 加载时顶部显示的 "Base directory for this skill" 路径。

---

## 问题分流

| 问题类型 | 执行流程 |
|---------|---------|
| 电脑重启/每日启动 | → 高频快答「电脑重启后怎么进入 Apollo」 |
| 打包提交、压缩包 | → 高频快答 + `02_日常工作流/09_赛事压缩包制作.md` |
| buildtool install / 下载代码 | → 高频快答「怎么下载 Planning 代码」 |
| profile 初始化 / 配置参数获取 | → 高频快答 + `02_日常工作流/06_aem_profile配置管理.md` |
| 编译后配置丢失 | → 高频快答「编译后配置参数丢失/被覆盖」 |
| Git 代码保存 / 回退 | → 高频快答 + `02_日常工作流/10_Git代码与配置管理.md` |
| Planning 模块打不开 | → 速查卡片「Planning 模块恢复」+ 检索 `07_FAQ故障排查/planning模块打不开恢复指南.md` |
| 模块在 DreamView 中打不开 | → 速查卡片「mainboard 单模块启动」 |
| **场景开发**（借道/交汇/人行道/泊车…）| → 先 Glob 文件名，再流程 B 检索 `03_规划PnC/` + `04_赛事集锦/` |
| 插件开发（TrafficRule/Scenario/Task）| → 流程 B 检索 `03_规划PnC/05_`~`07_` |
| Dreamview 使用、SimControl | → 流程 B 检索 `05_工程框架与工具/Dreamview功能介绍.md` |
| buildtool 编译错误（开发中） | → 检索 `07_FAQ故障排查/安装及编译问题FAQ——编译相关.md` |
| 赛事报名、赛事规则 | → 流程 B 检索 `01_赛事竞赛/` |
| 硬件传感器、CAN 协议 | → 流程 B 检索 `08_硬件传感器/` |
| 地图、场景下载 | → 流程 B 检索 `09_地图资源/` |

---

## 高频快答

以下问题无需检索知识库，直接回答：

| 问题 | 快速回答 |
|------|---------|
| 电脑重启后怎么进入 Apollo | `cd application-pnc && aem start && aem enter`，然后 `buildtool build -p core`（有代码改动时） |
| 怎么打包提交 | 只改了配置：`tar -zcvf 提交包.tar.gz profiles/default`；改了源码：`tar -zcvf 提交包.tar.gz modules/planning/ profiles/default` |
| 怎么下载 Planning 代码 | 先 `aem enter` 进入容器，再执行 `buildtool install planning*`（全量）或 `buildtool install planning-traffic-rules-crosswalk`（指定模块） |
| 怎么下载（获取）配置参数 | 方式 A（官方包）：`buildtool profile config init --package planning --profile=default`；方式 B（含自定义插件）：`mkdir -p profiles/default/modules && cp -r .aem/envroot/opt/apollo/neo/share/modules/planning profiles/default/modules/`，完成后执行 `aem profile use default` |
| profile 怎么初始化 | `buildtool profile config init --package planning --profile=default` |
| 日志太多/磁盘满了怎么清理 | 日志在 `data/log/` 下，历史日志可安全删除：`find data/log/ -name "*.log.*20[0-9][0-9]*" -type f -delete`；清理前先看大小：`du -sh data/log/` |
| 编译后配置参数丢失/被覆盖 | `buildtool build` 会覆盖 `profiles/` 下的软链配置。**编译后务必执行 `aem profile use default`** 恢复 profile 配置 |
| 怎么用 Git 保存代码和配置 | 宿主机执行：`git add profiles/default/ modules/planning/ && git commit -m "描述改动"`；不同场景用不同 branch：`git checkout -b scene/crosswalk`；切分支后记得重新执行 `aem profile use default` |
| 改坏了怎么用 Git 回退 | `git checkout HEAD -- profiles/default/`（回退配置）或 `git checkout HEAD -- modules/planning/`（回退代码） |

---

## 速查卡片

### mainboard 单模块启动

当某个模块在 DreamView 中打不开或行为异常时，在容器内用 `mainboard -d <dag路径>` 单独启动：

```
Planning:    mainboard -d /apollo/modules/planning/planning_component/dag/planning.dag
路由:        mainboard -d /apollo/modules/external_command/process_component/dag/external_command_process.dag
Prediction:  mainboard -d /apollo/modules/prediction/dag/prediction.dag
Control:     mainboard -d /apollo/modules/control/control_component/dag/control.dag
```

> 排查时通常先启 Planning 看是否有 Segfault 或配置缺失。

### Planning 模块无法打开 / 代码恢复

> 所有命令在**容器内**（`aem enter` 后）的 `/apollo_workspace` 目录下执行。

```bash
# 1. 备份当前代码和配置
tar -zcvf planning_backup.tar.gz modules/planning/
tar -zcvf profiles_default_backup.tar.gz profiles/default/

# 2. 切到临时 profile，释放 default 软链
mkdir -p profiles/tmp
aem profile use tmp

# 3. 删除损坏的代码和配置
rm -rf profiles/default
rm -rf modules/planning

# 4. 重装所有 planning 包（恢复到官方初始状态）
buildtool reinstall planning*

# 5.（可选）重新拉取源码
buildtool install planning*

# 6.（可选）编译
buildtool build -p modules/planning/

# 7. 恢复 profile 配置
buildtool profile config init --package planning --profile=default
aem profile use default
```

---

## 典型工作流

### 工作流 1：改参数调优（最常见）

```
编辑 profiles/default 下的配置文件
  → aem bootstrap start --plus（启动仿真）
  → DreamView 中选择场景运行
  → 观察效果，调整参数
  → 满意后打包：tar -zcvf 提交包.tar.gz profiles/default
```

### 工作流 2：改源码开发

```
buildtool install planning*（拉取源码）
  → 修改 modules/planning/ 下的代码
  → buildtool build -p modules/planning/（编译）
  → aem profile use default（⚠️ 关键：恢复 profile 软链配置）
  → aem bootstrap start --plus（启动仿真验证）
  → 满意后打包：tar -zcvf 提交包.tar.gz modules/planning/ profiles/default
```

### 工作流 3：每日开发（电脑重启后）

```
cd application-pnc
  → aem start（启动容器）
  → aem enter（进入容器）
  → buildtool build -p core（如有代码改动则编译）
  → aem bootstrap start --plus（启动 DreamView）
```

---

## 流程 B：知识库检索

### Step 1：识别问题类型，确定搜索目录

**优先按场景名匹配文件名**：先 `Glob("*借道*")` 在 knowledge 目录下匹配，命中则直接读取，跳过 Grep。

文件名未命中时，参考下表缩小范围：

| 问题类型 | 优先目录 |
|---------|---------|
| PnC、Planning、规划 | `03_规划PnC/`（入口：`00_技术参考索引.md`）|
| **下载 Planning 代码**、buildtool install、下载配置参数 | `03_规划PnC/00_代码与配置下载指南.md` |
| TrafficRule / Scenario / Task 插件开发 | `03_规划PnC/05_`~`07_` |
| 具体赛事场景（借道/交汇/人行道/泊车…）| `03_规划PnC/09_`~`17_` + `04_赛事集锦/` |
| Dreamview、仿真 SimControl | `05_工程框架与工具/Dreamview功能介绍.md`、`03_规划PnC/04_使用SimControl仿真调试.md` |
| **Planning 打不开、Planning 崩溃** | `07_FAQ故障排查/planning模块打不开恢复指南.md` |
| buildtool 编译报错（开发中） | `07_FAQ故障排查/安装及编译问题FAQ——编译相关.md`、`buildtool相关问题FAQ.md` |
| Dreamview 地图不加载 | `07_FAQ故障排查/dreamview地图不加载或场景不跳转.md` |
| 日志查看 | `07_FAQ故障排查/Apollo查看日志以及输出日志.md` |
| profile、包管理 | `02_日常工作流/06_aem_profile配置管理.md`、`05_工程框架与工具/` |
| **git、分支、回退、commit** | `02_日常工作流/10_Git代码与配置管理.md` |
| 电脑重启后进入 Apollo | `02_日常工作流/08_电脑重启后怎么进入Apollo.md` |
| 打包提交 | `02_日常工作流/09_赛事压缩包制作.md` |
| 传感器、CAN | `08_硬件传感器/` |
| 地图、场景下载 | `09_地图资源/` |
| 赛事报名、规则 | `01_赛事竞赛/` |

### Step 2：用 Grep 工具检索（禁止使用 Bash grep）

使用内置 **Grep 工具**在 `{BASE_DIR}/references/knowledge/` 中检索：

- 先搜文件列表，找到最相关的 1-3 个文件
- 用 `-C 3` 精准定位段落
- 多关键词重试：「安装」→「部署」→「初始化」

### Step 3：读取文件并回答

文件超 200 行先用 Grep 定位章节，再分段读取。

**回答格式**：
1. FAQ / 报错类 → 「症状 → 原因 → 命令」三段式
2. 场景开发类 → 核心代码逻辑 + 配置片段
3. 流程类 → 按步骤编号列出命令
4. 末尾注明来源：`（来源：文件名.md）`

### Step 4：未找到时

换同义词再试一次；仍无结果则基于 Apollo EDU 领域知识作答，并说明「本地知识库未找到直接记录」。

---

## 重要约束

- **编译后恢复 profile**：提醒用户在 `buildtool build` 后执行 `aem profile use default`，防止配置被覆盖
- **PnC 赛道专注**：不涉及感知（Perception）、定位（Localization）等上游模块，不需要 GPU
- **sudo 操作必须确认**：涉及 `sudo` 的命令需用户确认后才执行
- **macOS 提示**：检测到 macOS 时不执行任何安装命令，仅提示在 Ubuntu 上操作

## 知识库目录结构（快速参考）

见 `{BASE_DIR}/references/knowledge_index.md`

## 文件结构

```
apollo-dev/
├── _meta.json
├── config.yaml
├── SKILL.md
├── README.md
└── references/
    ├── knowledge_index.md
    └── knowledge/
        ├── 01_赛事竞赛/
        ├── 02_日常工作流/    # 4 个文件（profile、重启、打包、Git）
        ├── 03_规划PnC/       # 19 个文件
        ├── 04_赛事集锦/      # 11 个文件
        ├── 05_工程框架与工具/
        ├── 06_技术培训/
        ├── 07_FAQ故障排查/   # 7 个文件（开发相关）
        ├── 08_硬件传感器/
        └── 09_地图资源/
```
