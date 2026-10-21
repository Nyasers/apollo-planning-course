# Apollo Planning 新手自学路线（V2）

> 本仓库同时公开课程网站和 Apollo Claw Harness 源码。Harness 位于 [`harness/`](./harness/)，用于本地环境检查、仿真启动、record 控制、报告生成和实验证据管理。

## 仓库内容

- [`site/`](./site/)：课程网站、实验中心、报告页和静态资源。
- [`harness/`](./harness/)：Apollo Claw Harness 源码、本地实验面板、脚本、技能和测试。
- [`tools/`](./tools/)：网站构建和检查工具。
- 课程 Markdown 和实验说明位于仓库根目录及 `reference/`。

Harness 快速开始：

```bash
cd harness
python3 -m apollo_claw serve --port 8765
```

Windows 一键配置：

```text
harness/一键配置Harness.cmd
```

Harness 的安装、命令和目录说明见 [`harness/README.md`](./harness/README.md)。原创代码采用 [Apache-2.0](./LICENSE) 许可证；`harness/skills` 中涉及 Apollo 的参考资料和第三方资源仍遵循各自的原始许可。

## 1. 这次调整的原则

原来的内容从源码细节和函数调用开始，对零基础学习者偏难。

V2 改为以下顺序：

```text
先跑起来
  -> 先认识 Apollo 和 Planning 的整体地图
  -> 再认识 Scenario、Stage、Task
  -> 边读项目边补最小 C++ 基础
  -> 最后修改一个小任务并运行验证
```

明确不做的事：

- 不先系统学习完整 C 语言。
- 不先学习复杂路径优化、速度优化和数学推导。
- 不要求一开始读懂 `Plan()` 的全部内部实现。
- 不把所有 Planning 目录都当成必须掌握的内容。
- 不把视频作为唯一学习方式。

本课程的主线是：

```text
Apollo 仿真环境
  -> Planning 架构
  -> Scenario / Stage / Task
  -> 足够的 C++ 基础
  -> 小型修改与验证
```

## 2. 学习前提

Apollo 的仿真和开发环境运行在 Linux 上，不是普通的 Windows 桌面程序。

开始学习前，必须先准备好下面三种 Linux 环境之一：

| 方案 | 适合人群 | 优点 | 注意 |
| --- | --- | --- | --- |
| Ubuntu 虚拟机 | 刚开始、不想动系统分区 | 安全、容易恢复、适合试错 | 占内存和 CPU，速度较慢 |
| Ubuntu 双系统 | 电脑性能足够、愿意折腾 | 性能最好 | 分区有风险，必须先备份 |
| WSL2 | 已经熟悉 Windows 和 Docker | 使用方便 | Docker、GUI、端口和性能需要单独验证 |

Apollo EDU PnC 安装指南给出的基础要求是：

- 4 核 CPU 以上。
- 16 GB 内存以上。
- 建议 55 GB 以上存储空间。
- 不要求 GPU。
- Ubuntu 推荐 18.04、20.04、22.04。
- 不推荐 Ubuntu 24.04。
- Docker 版本要求 19.03+。

详细安装步骤见：

- [第 00 课：Linux 与 Apollo 仿真环境安装](./lesson-00-linux-simulation-setup.md)
- [Apollo EDU版本Pnc工程安装指南](https://apollo.baidu.com/community/article/1239)

注意：

1. 本课程代码阅读基线仍以官方 `ApolloAuto/apollo` 仓库为准。
2. 安装指南使用 `ApolloAuto/application-pnc` 作为适合初学者的 PnC 示例工程。
3. `application-pnc` 是学习和比赛用的工作空间，不等同于完整的 Apollo 官方主仓库。
4. 安装成功后，`buildtool install planning*` 可以获取 Planning 相关代码包。
5. 没有跑通环境时，仍然可以做静态阅读，但加入课程前必须先完成安装检查。

## 3. 新手课程路线

| 单元 | 难度 | 主题 | 学完后能做什么 |
| --- | --- | --- | --- |
| 00 | 入门 | Linux 与 Apollo 仿真环境 | 能启动 Docker、AEM、核心依赖和 DreamView |
| 01 | 入门 | Apollo 与 Planning 全景地图 | 能说出 Apollo 主要组成和 Planning 的位置 |
| 02 | 入门 | Planning 项目目录和一句话数据流 | 能找到 Component、Planner、Scenario、Task |
| 03 | 入门 | 一轮 Planning 的简单流程 | 能画出输入到轨迹输出的简化流程 |
| 04 | 入门 | Scenario、Stage、Task 是什么 | 能用生活化例子解释三者关系 |
| 05 | 基础 | C++：变量、函数、条件、循环 | 能读懂 Task 文件中的基础语法 |
| 06 | 基础 | C++：指针是什么 | 能解释 `Frame*`、`&frame`、`frame->` |
| 07 | 基础 | C++：引用和 `const` | 能区分 `T*`、`T&`、`const T&` |
| 08 | 基础 | C++：类、对象、构造函数 | 能读懂 Task 和 Stage 的类定义 |
| 09 | 基础 | C++：继承、虚函数、`override` | 能理解 Task 为什么继承接口类 |
| 10 | 基础 | C++：`vector` 和智能指针 | 能读懂 `task_list_` 和 `shared_ptr` |
| 11 | 核心 | ScenarioManager：场景怎样切换 | 能追踪 LaneFollow 场景选择和转移 |
| 12 | 核心 | LaneFollow 场景 | 能说清场景包含哪些 Stage |
| 13 | 核心 | Stage：一个阶段怎样执行多个 Task | 能读懂 Stage 的 Task 循环 |
| 14 | 核心 | Task 基类：Init 和 Execute | 能理解一个 Task 的生命周期 |
| 15 | 核心 | 路径 Task 示例 | 能读 LaneFollowPath 的输入、输出和步骤 |
| 16 | 核心 | 速度 Task 示例 | 能读 SpeedBoundsDecider 的输入、输出和步骤 |
| 17 | 核心 | TrafficRule 与 Task 的区别 | 能区分全局交通规则和具体任务 |
| 18 | 实践 | 配置、插件、编译和日志 | 能修改配置、编译模块并找到日志 |
| 19 | 实践 | 新增一个简单 Task | 能加入一个只记录日志的 Task 并运行 |
| 20 | 实践 | 修改一个简单速度/限速行为 | 能完成小型功能修改并记录验证证据 |

## 4. 每课的难度控制

每个单元必须满足：

- 新概念不超过 5 个。
- 每课最多深读 2 个源码文件。
- 代码片段尽量控制在 30 行以内。
- 先讲输入和输出，再讲实现细节。
- 算法数学默认放入“进阶了解”，不作为过关条件。
- C++ 语法点到为止，只解释读懂当前代码所需的部分。
- 每课都有自测题、参考答案和过关检查。
- 没有运行环境时，可以完成静态任务，但必须记录未运行原因。

## 5. 重点学习范围

### 5.1 Scenario 场景

先学：

- `lane_follow`
- `stop_sign_unprotected`
- `traffic_light_protected`

先理解：

```text
Scenario = 当前属于什么驾驶情境
Stage = 情境中的哪个阶段
Task = 这个阶段要完成的具体工作
```

### 5.2 Task 任务

优先学习：

- `lane_follow_path`
- `speed_bounds_decider`
- `traffic_rules/crosswalk`
- `traffic_rules/traffic_light`

暂时不要求：

- 所有优化器的数学推导。
- 所有开放空间泊车算法。
- 全部 30 多个 Task。
- 所有历史兼容代码。

### 5.3 C++ 基础

只学读 Planning 代码必须用到的内容：

- 变量、函数、条件、循环。
- 指针和地址。
- 引用和 `const`。
- 类、对象和成员函数。
- 继承、虚函数和 `override`。
- `vector`、范围循环和智能指针的使用方式。

不要求：

- 手写复杂模板。
- 手动管理 `new/delete`。
- 高级移动语义。
- 复杂元编程。

## 6. 每课自学流程

1. 阅读本课目标。
2. 看完概念解释。
3. 按“源码阅读路线”打开文件。
4. 完成一到两个小实验。
5. 回答自测题。
6. 对照参考答案。
7. 填写过关检查。

学习证据可以是：

- 命令输出。
- 手绘调用图。
- 带注释的源码片段。
- DreamView 截图。
- 修改前后的日志对比。
- 自测题错因记录。

## 7. 当前主线材料

- [第 00 课：Linux 与 Apollo 仿真环境安装](./lesson-00-linux-simulation-setup.md)
- [第 01 课：Apollo 与 Planning 全景地图](./lesson-01-apollo-planning-map.md)

## 8. 参考资料

以下材料内容更深，暂时不作为新手主线。完成第 00～10 课后再阅读：

- [深入阅读：Planning 全貌](./reference/deep-dive-planning-overview.md)
- [深入阅读：一帧规划如何跑完](./reference/deep-dive-one-planning-cycle.md)
- [深入阅读：学习卡](./reference/deep-dive-learning-cards.md)
- [深入阅读：实验手册](./reference/deep-dive-labs.md)

## 9. 第一阶段的通过标准

完成第 00～01 课后，你应该能够：

- 说明 Apollo 为什么运行在 Linux 上。
- 解释虚拟机、双系统和 WSL 的区别。
- 启动 `application-pnc` 工作空间。
- 打开 DreamView 并启动仿真。
- 找到 Planning 相关代码包。
- 说出 Apollo 的主要模块。
- 说出 Planning 在自动驾驶链路中的位置。
- 用一句话解释 Scenario、Stage 和 Task。

任何一项做不到，都不要急着进入指针和源码细节。
## HTML 自学站点

可直接离线打开：

```text
site/index.html
```

站点包含：

- 课程首页与完整路线图。
- 第 00～20 课共 21 个 HTML 课程页面。
- 左侧完整课程导航、右侧本页目录。
- 课程搜索、深浅主题、代码复制。
- 本地学习进度和清单记录。
- 桌面与移动端布局。

重新生成：

```powershell
& 'C:\Users\FQX\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tools\build-site.mjs
```

浏览器自动检查：

```powershell
& 'C:\Users\FQX\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tools\test-site.cjs
```
## 图表与插图

网站使用两种视觉辅助方式：

- Mermaid：用于调用链、继承关系、状态机、数据流和 Task 流程。
- 漫画插图：用于建立直觉，统一为浅色纸张、Apollo 蓝和安全琥珀风格。

Mermaid 运行库保存在本地：

```text
site/assets/vendor/mermaid/mermaid.min.js
```

漫画插图使用 WebP 格式保存在：

```text
site/assets/images/*.webp
```

原始 PNG 和生图提示词保留在本地 `generated/`，不进入公开仓库。所有插图均不放中文文字，避免图像模型中文字乱码；具体含义由网页标题、正文和图注解释。
## MVP 实验中心

实验中心已经加入静态网站：

```text
site/lab/index.html
site/lab/crosswalk.html
site/lab/report.html
```

包含：

- 实验中心首页与 MVP 范围。
- 人行道避让实验台。
- Apollo Claw 四技能入口。
- 场景演示控制台。
- 优化前后指标对比。
- Markdown 实验报告下载。

当前默认为明确标注的演示模式，不连接真实模型和仿真。接入真实后端时，在 `crosswalk.html` 中配置：

```javascript
window.APOLLO_LAB_CONFIG = {
  apiBase: "https://api.example.com",
  simulationUrl: "https://studio.example.com",
  demoMode: false
};
```

后端接口约定：

```text
POST /api/agent
body: { skill, message, experiment, stage }
response: { message, evidence? }
```

实验中心浏览器检查：

```powershell
& 'C:\Users\FQX\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tools\test-lab.cjs
```