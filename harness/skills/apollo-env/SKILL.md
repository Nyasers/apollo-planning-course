---
name: apollo-env
description: Apollo EDU 赛事环境安装与检测工具。当用户遇到以下场景时使用此 Skill：(1) 全新安装 Apollo（Docker、aem、工程克隆、buildtool build）(2) 环境检测与状态报告（OS、CPU、内存、磁盘、网络、aem、buildtool）(3) 安装过程报错与故障诊断（Docker 安装失败、aem 命令不存在、apt source 问题、buildtool build -p core 报错、application-pnc 克隆失败）(4) 编译缓存下载（首次安装时网络差）(5) 赛事场景插件下载（Profile Plugin）。触发关键词：安装Apollo、安装 Apollo、install apollo、Docker安装、aem安装、aem install、docker、全新环境、环境检测、env check、application-pnc克隆、buildtool build -p core、编译缓存、apollo-pkg、apt source、环境配置。命令入口：/apollo-env、/apollo-env check、/apollo-env diagnose、/apollo-env install。
default-enabled: false
---

# Apollo EDU 环境安装引导

专注于 Apollo EDU PnC 赛道的系统安装、环境检测与故障诊断，覆盖从全新 Ubuntu 到 DreamView 可访问的完整安装链路。

**知识库路径**：`{BASE_DIR}/references/knowledge/`
**环境检测脚本**：`{BASE_DIR}/scripts/env_check.sh`
**配置文件**：`{BASE_DIR}/config.yaml`
> `{BASE_DIR}` 为本 skill 加载时顶部显示的 "Base directory for this skill" 路径。

---

## 环境感知

在执行任何步骤前，先判断用户所处环境：

| 信号 | 判断方法 | 结论 | 影响 |
|------|----------|------|------|
| 提示符含 `in-dev-docker` 或当前目录为 `/apollo_workspace` | 观察终端提示符或 `pwd` | **Apollo 容器内** | 跳过 Docker/aem 安装，直接引导 buildtool/DreamView |
| 存在 `/.dockerenv` 文件 | `test -f /.dockerenv && echo "容器内"` | **容器内** | 同上 |
| `aem` 和 `docker` 均可执行 | `command -v aem && command -v docker` | **宿主机，已部分安装** | 运行 env_check.sh 检测后补缺 |
| 均不可用 | — | **全新环境** | 从头引导完整安装 |

---

## 问题分流

| 问题类型 | 执行流程 |
|---------|---------|
| 安装 Apollo、配置环境 | → 流程 A（完整安装引导） |
| `/apollo-env` | → 流程 A |
| `/apollo-env check` | → 流程 A Step 1（仅检测） |
| `/apollo-env install` | → 流程 A Step 2（跳过检测，直接安装） |
| `/apollo-env diagnose` 或安装报错 | → 流程 A Step 6（故障诊断） |
| `buildtool build -p core` 首次报错 | → 先查高频快答，未命中则检索 `07_FAQ故障排查/buildtool build -p core 报错指南.md` |
| 电脑重启后怎么进入 Apollo / 重新打开 Apollo | → 流程 B（重启后快速进入） |

---

## 高频快答

| 问题 | 快速回答 |
|------|---------|
| 电脑重启后怎么进入 Apollo | `cd application-pnc` → `aem enter`，无需重新安装或 aem start |
| DreamView 怎么打开 | `aem bootstrap start --plus`，浏览器访问 `http://localhost:8888` |
| buildtool 编译要执行几次 | 建议执行两次 `buildtool build -p core`，第一次下载依赖，第二次确保完整 |

---

## 速查卡片：buildtool 编译报错速查

> 来源：https://apollo.baidu.com/community/article/1160

| 报错关键词 | 原因 | 修复 |
|-----------|------|------|
| `Cannot find WORKSPACE` / `Different packages have a same name` | 容器内 `/apollo_workspace` 目录无效或未在正确路径执行 | `exit` → `aem remove` → 重新 `aem start` → `aem enter` → 在 `/apollo_workspace` 下执行 |
| `Error downloading`（Bazel 下载依赖失败） | 网络问题 | 方案 A：换网络（手机热点）重试；方案 B：使用离线缓存（见下） |
| 编译耗时过长 / 首次编译太慢 | 没有使用预编译缓存 | 使用离线缓存（见下） |
| `-luuid` 链接错误 | 旧版镜像缺少 uuid 依赖 | `sudo apt install uuid-dev && sudo ldconfig` 或更新镜像 `exit` → `aem start -f` |
| Bazel 缓存过期 `install/cbf972...` | .cache 中 bazel install 目录过期 | `rm -rf /apollo_workspace/.cache/bazel/install/cbf972...` → 重新 `buildtool build` |

**离线编译缓存（解决下载失败和编译慢）：**
```bash
aem enter
cd /apollo_workspace/
wget https://apollo-system.cdn.bcebos.com/bazel_deps/cache.tar.gz
rm -rf .cache
tar -xzvf cache.tar.gz
buildtool build -p core
```

---

## 流程 B：重启后快速进入

> 适用：Apollo 已安装完成，电脑重启后重新进入开发环境。

```bash
cd application-pnc
aem enter
```

无需重新执行 `aem start`、`bash setup.sh` 或 `buildtool build`。
进入容器后如需启动 DreamView：`aem bootstrap start --plus`

---

## 流程 A：安装引导

### Step 1：环境检测

```bash
bash {BASE_DIR}/scripts/env_check.sh
```

脚本退出码：**0**=全部通过，**1**=存在警告，**2**=存在失败项。

支持 `--json` 输出：
```bash
bash {BASE_DIR}/scripts/env_check.sh --json
```

检测结果标注：
- ✅ 通过 — 已满足
- ⚠️ 警告 — 非推荐但可继续
- ❌ 失败 — 必须安装才能继续

如果是 `/apollo-env check` 触发，到此结束。

### Step 2：安装 Docker

```bash
wget http://apollo-pkg-beta.bj.bcebos.com/docker_install.sh
bash docker_install.sh
```

网络失败时使用阿里云镜像：
```bash
wget http://apollo-pkg-beta.bj.bcebos.com/get_docker.sh
bash get_docker.sh --mirror Aliyun
```

### Step 3：安装 aem

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://apollo-pkg-beta.cdn.bcebos.com/neo/beta/key/deb.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/apolloauto.gpg
sudo chmod a+r /etc/apt/keyrings/apolloauto.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/apolloauto.gpg] https://apollo-pkg-beta.cdn.bcebos.com/apollo/core $(. /etc/os-release && echo "$VERSION_CODENAME") main" | sudo tee /etc/apt/sources.list.d/apolloauto.list
sudo apt-get update && sudo apt install apollo-neo-env-manager-dev --reinstall
```

验证：`aem -h`

### Step 4：克隆赛事工程

```bash
git clone https://github.com/ApolloAuto/application-pnc.git
```

GitHub 不可达时使用 Gitee：
```bash
git clone https://gitee.com/ApolloAuto/application-pnc
```

**无论通过哪个源克隆，都必须执行 setup.sh（它会自动识别 CPU 架构 amd64 / arm64，并写入 .workspace.json）：**
```bash
cd application-pnc
bash setup.sh
```

验证：
```bash
cat .workspace.json   # 应包含正确的 arch 字段
```

### Step 5：启动环境并构建

```bash
aem start
aem enter
buildtool build -p core
buildtool build -p core   # 执行两次确保完整
```

### Step 6：验证

```bash
aem bootstrap start --plus
# 浏览器访问 http://localhost:8888
```

### Step 7（可选）：赛事场景插件下载

见知识库 `{BASE_DIR}/references/knowledge/02_安装部署/04_赛事场景插件下载指南.md`。

### Step 6：故障诊断（`/apollo-env diagnose`）

1. 运行 env_check.sh 获取当前状态
2. 在知识库 `07_FAQ故障排查/` 中检索匹配错误
3. 详细诊断表见 `02_安装部署/00_安装总览.md`

所有涉及 `sudo` 的命令，必须展示给用户确认后再执行。

---

## 知识库检索

当快答未命中时，按如下方式检索：

| 问题类型 | 优先目录 |
|---------|---------|
| 安装流程、Docker、aem | `02_安装部署/`（入口：`00_安装总览.md`）|
| buildtool build -p core 报错 | `07_FAQ故障排查/buildtool build -p core 报错指南.md` |
| Docker 安装失败 | `07_FAQ故障排查/Docker无法安装解决方案.md`、`安装及编译问题FAQ--docker.md` |
| aem 相关问题 | `07_FAQ故障排查/安装及编译问题FAQ--aem 工具、Apollo下载和Apollo启动相关.md` |
| 克隆工程失败 | `07_FAQ故障排查/安装及编译问题FAQ--拉取工程目录.md` |
| 编译缓存 | `02_安装部署/03_赛事编译缓存.md` |
| Profile 插件 | `02_安装部署/04_赛事场景插件下载指南.md` |

---

## 重要约束

- **sudo 操作必须确认**：所有 `sudo` 命令展示后用户确认才执行
- **macOS 不操作**：检测到 macOS 时仅提示在 Ubuntu 上操作，不执行任何安装命令
- **不跳过步骤**：严格按顺序执行，不跳过环境检测
- **幂等性**：每步执行前先检测是否已完成，已安装的自动跳过
- **PnC 专注**：不涉及感知（Perception）、定位（Localization）等上游模块，不需要 GPU

## 文件结构

```
apollo-env/
├── _meta.json
├── config.yaml
├── SKILL.md
├── README.md
├── scripts/
│   └── env_check.sh
└── references/
    ├── knowledge_index.md
    └── knowledge/
        ├── 02_安装部署/    # 11 个文件（安装全流程）
        └── 07_FAQ故障排查/ # 6 个文件（安装相关）
```
