(() => {
  "use strict";

  const modules = [
    {
      id: "m1",
      code: "M1",
      title: "系统与仿真环境",
      range: "00–03",
      hours: 8,
      summary: "先建立 Linux、Apollo、Cyber RT 与 Planning 的系统地图，完成第一次场景运行。",
      ai: ["apollo-env", "apollo-dev"]
    },
    {
      id: "m2",
      code: "M2",
      title: "C++ 与 PnC 基础",
      range: "04–09",
      hours: 16,
      summary: "围绕真实 Task 源码补齐阅读所需的 C++、指针、类、继承和资源管理能力。",
      ai: ["apollo-dev"]
    },
    {
      id: "m3",
      code: "M3",
      title: "Scenario 与 Task",
      range: "10–16",
      hours: 24,
      summary: "从场景切换、Stage 执行到路径、速度和交通规则，建立 PnC 主线。",
      ai: ["apollo-dev", "apollo-eval"]
    },
    {
      id: "m4",
      code: "M4",
      title: "工程化与综合实验",
      range: "17–20",
      hours: 12,
      summary: "完成配置、编译、新增 Task、日志调试和限速实战，并进入综合实验闭环。",
      ai: ["apollo-test", "apollo-eval"]
    }
  ];

  const contexts = {
    "lesson-00": { module: "m1", hours: 3, stage: "02 环境检查", ai: ["apollo-env"], evidence: "doctor.json" },
    "lesson-01": { module: "m1", hours: 2, stage: "01 实验准备", ai: ["apollo-env", "apollo-dev"], evidence: "系统链路笔记" },
    "lesson-02": { module: "m1", hours: 2, stage: "03 运行场景", ai: ["apollo-dev"], evidence: "一轮规划调用链" },
    "lesson-03": { module: "m1", hours: 1, stage: "03 运行场景", ai: ["apollo-dev"], evidence: "Scenario / Stage / Task 关系图" },

    "lesson-04": { module: "m2", hours: 2, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "C++ 阅读笔记" },
    "lesson-05": { module: "m2", hours: 3, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "指针阅读笔记" },
    "lesson-06": { module: "m2", hours: 2, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "引用与 const 笔记" },
    "lesson-07": { module: "m2", hours: 3, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "类与对象关系图" },
    "lesson-08": { module: "m2", hours: 3, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "继承与多态链路" },
    "lesson-09": { module: "m2", hours: 3, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "容器与所有权笔记" },

    "lesson-10": { module: "m3", hours: 3, stage: "03 运行场景", ai: ["apollo-dev"], evidence: "场景切换流程" },
    "lesson-11": { module: "m3", hours: 3, stage: "03 运行场景", ai: ["apollo-dev"], evidence: "LaneFollow pipeline" },
    "lesson-12": { module: "m3", hours: 3, stage: "04 观察问题", ai: ["apollo-dev"], evidence: "Stage 执行笔记" },
    "lesson-13": { module: "m3", hours: 3, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "Task 生命周期笔记" },
    "lesson-14": { module: "m3", hours: 4, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "路径 Task 分析" },
    "lesson-15": { module: "m3", hours: 4, stage: "05 诊断与源码定位", ai: ["apollo-dev"], evidence: "速度 Task 分析" },
    "lesson-16": { module: "m3", hours: 4, stage: "05 诊断与源码定位", ai: ["apollo-dev", "apollo-eval"], evidence: "规则执行分析" },

    "lesson-17": { module: "m4", hours: 2, stage: "06 录制与可视化", ai: ["apollo-dev", "apollo-test"], evidence: "编译与运行日志" },
    "lesson-18": { module: "m4", hours: 4, stage: "07 评分与优化", ai: ["apollo-dev", "apollo-test"], evidence: "新增 Task 代码与构建" },
    "lesson-19": { module: "m4", hours: 2, stage: "04 观察问题", ai: ["apollo-dev", "apollo-test"], evidence: "日志摘要与 channel" },
    "lesson-20": { module: "m4", hours: 4, stage: "07 评分与优化", ai: ["apollo-test", "apollo-eval"], evidence: "record / score / report" }
  };

  const aiPractices = {
    "lesson-00": {
      task: "解释环境检查结果",
      skills: ["apollo-env"],
      trigger: "首次安装、启动失败或 DreamView 无法打开时。",
      inputs: ["环境检查输出", "失败命令和完整报错", "WSL / Docker / AEM 版本信息"],
      prompt: "请按 Linux/WSL、Docker、AEM、Apollo 容器、DreamView 的顺序分析以下环境输出。请区分：已经确认的事实、可能的原因、需要我执行的验证命令。不要假设我没有提供的系统状态，也不要把推测写成结论。",
      verify: "按建议逐项修复后重新运行环境检查，对比新的 doctor/environment 结果；只有重新检查通过才算解决。",
      evidence: "doctor.json / 环境检查记录"
    },
    "lesson-01": {
      task: "建立 Apollo 与 Planning 全景",
      skills: ["apollo-dev"],
      trigger: "第一次阅读 Planning 源码，需要确认模块边界和调用方向时。",
      inputs: ["PlanningComponent 源码片段", "ScenarioManager / Scenario / Stage / Task 头文件片段", "目录结构"],
      prompt: "仅根据我提供的源码片段，列出 Planning 一轮流程中的调用方向、每个类所属目录、输入和输出。遇到片段中没有出现的类或字段时请明确写“未提供”，不要补充你记忆中的实现。",
      verify: "在本地源码中逐项定位 AI 提到的文件、类和函数；无法定位的内容视为待核实。",
      evidence: "源码路径与调用链笔记"
    },
    "lesson-02": {
      task: "梳理 Planning 一轮运行流程",
      skills: ["apollo-dev"],
      trigger: "阅读 PlanningComponent、RunOnce、Frame 或 ADCTrajectory 相关代码时。",
      inputs: ["PlanningComponent::Proc / RunOnce 片段", "Frame 和 LocalView 片段", "ADCTrajectory 输出位置"],
      prompt: "把下面的 Planning 源码整理成按执行顺序排列的调用链，标出每一步的输入、输出和可能失败的 Status。只使用我提供的代码，不要编造未出现的函数。",
      verify: "用编辑器或 grep 找到每个调用点，并在运行日志中确认至少一个实际执行节点。",
      evidence: "Planning 调用链笔记"
    },
    "lesson-03": {
      task: "拆解 Scenario、Stage 和 Task 的层级",
      skills: ["apollo-dev"],
      trigger: "学习场景切换、Stage 执行或 Task pipeline 配置时。",
      inputs: ["Scenario / Stage / Task 基类片段", "LaneFollow pipeline 配置", "一个场景目录结构"],
      prompt: "根据提供的基类和 pipeline 配置，说明 Scenario、Stage、Task 之间的责任边界和生命周期。请分别回答“谁创建谁、谁执行谁、失败如何传递”，不要把 TrafficRule 和 Task 混为一谈。",
      verify: "在源码和配置中核对构造、进入、执行和退出路径，确认配置里的 task 名能对应到注册实现。",
      evidence: "Scenario / Stage / Task 关系图"
    },
    "lesson-04": {
      task: "读懂 Task 中的 C++ 基础语法",
      skills: ["apollo-dev"],
      trigger: "遇到变量、函数、条件分支或返回值读不懂时。",
      inputs: ["Task::Init / Execute 源码片段", "相关结构体字段", "编译器报错（如有）"],
      prompt: "请逐行解释这段 Task 代码中的变量、函数、条件判断和返回值，并指出哪些语句会影响 Task 的 Status。不要只翻译语法，要说明它们在规划中的作用。",
      verify: "回到源码对每一行做标注，并能用自己的话说明失败分支和正常返回的区别。",
      evidence: "C++ 阅读笔记"
    },
    "lesson-05": {
      task: "理解物理对象与指针关系",
      skills: ["apollo-dev"],
      trigger: "阅读 Frame、ReferenceLineInfo 或指针参数时。",
      inputs: ["Frame* / ReferenceLineInfo* 源码片段", "对象创建位置", "相关 nullptr 检查"],
      prompt: "根据以下源码，说明每个指针指向什么对象、由谁创建、生命周期由谁管理，以及解引用前做了哪些空指针检查。未知的所有权关系请标为“需核实”。",
      verify: "在源码中找到对象创建和传递链，确认指针不会在访问时失效。",
      evidence: "指针与所有权笔记"
    },
    "lesson-06": {
      task: "理解引用与 const 约束",
      skills: ["apollo-dev"],
      trigger: "遇到 const 引用参数或配置对象传递时。",
      inputs: ["函数签名", "const 引用参数", "调用位置"],
      prompt: "解释下面函数为什么使用 const 引用、能否改成值传递或非 const 引用，并说明对性能和可修改性的影响。只根据我提供的代码回答。",
      verify: "检查调用点是否存在修改参数的意图；用编译器验证修改后是否引入 const 错误。",
      evidence: "引用与 const 笔记"
    },
    "lesson-07": {
      task: "拆解类、对象与构造函数",
      skills: ["apollo-dev"],
      trigger: "阅读 Scenario、Stage 或 Task 的成员变量和初始化代码时。",
      inputs: ["类定义", "构造函数", "成员初始化列表"],
      prompt: "根据类定义和构造函数，列出对象包含的成员、哪些成员在构造时初始化、哪些依赖 Init 或配置文件，并指出对象创建后可以被谁持有。",
      verify: "在源码中核对成员初始化和 Init 调用顺序。",
      evidence: "类与对象关系图"
    },
    "lesson-08": {
      task: "追踪继承与 override 链路",
      skills: ["apollo-dev"],
      trigger: "阅读 Task、Decider 或插件实现时。",
      inputs: ["基类头文件", "派生类头文件", "插件注册代码"],
      prompt: "根据提供的头文件和注册代码，画出基类到派生类的继承链，标出 virtual / override 方法、插件注册点和实际调用位置。不要补充未提供的类。",
      verify: "使用 grep 找到注册名和运行时创建的派生类。",
      evidence: "继承与多态链路"
    },
    "lesson-09": {
      task: "分析 vector 与智能指针所有权",
      skills: ["apollo-dev"],
      trigger: "阅读 task_list_、scenario_list_ 或 shared_ptr/unique_ptr 时。",
      inputs: ["容器声明", "shared_ptr / unique_ptr 使用位置", "对象创建和转移代码"],
      prompt: "请按对象所有权整理下面代码：每个对象由谁创建、容器是否持有所有权、shared_ptr 和 unique_ptr 各自承担什么职责，以及哪些地方可能产生悬空引用。",
      verify: "在源码中核对对象创建、插入容器和销毁时机。",
      evidence: "容器与所有权笔记"
    },
    "lesson-10": {
      task: "定位场景切换逻辑",
      skills: ["apollo-dev"],
      trigger: "运行场景与预期不符，需要确认当前 Scenario 时。",
      inputs: ["ScenarioManager::Update / Select 片段", "场景列表配置", "运行日志中的场景名"],
      prompt: "根据下面 ScenarioManager 代码和日志，解释当前场景为什么被选中或没有切换。请分别列出已确认事实、可能原因和需要查看的日志字段。",
      verify: "在 DreamView / 日志中确认场景名和切换时间，再回到源码核对判断条件。",
      evidence: "场景切换记录"
    },
    "lesson-11": {
      task: "拆解 LaneFollow 场景 pipeline",
      skills: ["apollo-dev"],
      trigger: "进入 LaneFollow 场景或准备修改 pipeline 时。",
      inputs: ["LaneFollow pipeline 配置", "Stage 类定义", "Task 名称列表"],
      prompt: "请根据下面配置列出 LaneFollow 的 Stage 和 Task 执行顺序，并标出每个 Task 的职责与输入输出。配置中没有的任务不要自行补上。",
      verify: "使用源码注册名和配置中的 task 名称逐项核对。",
      evidence: "LaneFollow pipeline 笔记"
    },
    "lesson-12": {
      task: "理解 Stage 执行和失败中断",
      skills: ["apollo-dev"],
      trigger: "某个 Stage 未继续执行或出现 fallback 时。",
      inputs: ["Stage::Process 源码", "Task Status 返回逻辑", "运行日志"],
      prompt: "根据 Stage 代码和日志，说明循环如何执行 task_list、Status 失败后如何中断、fallback task 何时介入，并指出最可能触发中断的语句。",
      verify: "在日志中定位失败 Status 和对应 Task，再对照源码重新运行场景。",
      evidence: "Stage 执行与失败记录"
    },
    "lesson-13": {
      task: "梳理 Task 生命周期",
      skills: ["apollo-dev"],
      trigger: "新增 Task 或排查 Task 未执行时。",
      inputs: ["Task 基类头文件", "Init / Execute / Process 实现", "配置路径"],
      prompt: "根据 Task 基类和示例实现，列出从创建、Init、Execute 到返回 Status 的完整生命周期，并说明新增 Task 必须实现和注册哪些内容。",
      verify: "用最小日志 Task 运行一次，确认 Init 和 Execute 都被调用。",
      evidence: "Task 生命周期笔记"
    },
    "lesson-14": {
      task: "分析路径 Task 的输入输出",
      skills: ["apollo-dev"],
      trigger: "阅读 PathBounds、PathData 或路径优化代码时。",
      inputs: ["LaneFollowPath 源码", "ReferenceLineInfo 相关调用", "路径配置"],
      prompt: "请把下面路径 Task 的处理过程拆成输入—中间结果—输出三部分，说明路径边界、路径优化和路径评估分别写到哪个对象，并标出关键函数。",
      verify: "在源码中追踪中间结果最终写入 ReferenceLineInfo 的位置。",
      evidence: "路径 Task 分析"
    },
    "lesson-15": {
      task: "解释 S-T 图与速度边界",
      skills: ["apollo-dev", "apollo-eval"],
      trigger: "分析减速、停车或速度曲线问题时。",
      inputs: ["SpeedBoundsDecider 源码", "StGraphData 结构", "速度/时间曲线数据"],
      prompt: "根据源码和速度曲线数据，解释 S-T 图中边界如何形成、静态障碍物如何影响速度限制，以及当前轨迹为什么在某段时间减速。请把推断和实际数据分开。",
      verify: "用 record 或图表核对 AI 提到的速度、时间区间和边界来源，并重新运行验证。",
      evidence: "速度曲线与 S-T 分析"
    },
    "lesson-16": {
      task: "区分 TrafficRule 与 Task",
      skills: ["apollo-dev", "apollo-eval"],
      trigger: "交通灯、停止线或规则判定异常时。",
      inputs: ["TrafficRule / TrafficDecider 源码", "规则配置", "场景日志"],
      prompt: "根据提供的代码和配置，说明这条规则在什么阶段执行、读取哪些输入、输出什么决策，以及它和普通 Task 的区别。不要把所有规则都当成 Task。",
      verify: "在日志中确认规则名称、执行时间和决策结果，再核对 pipeline 配置。",
      evidence: "规则执行分析"
    },
    "lesson-17": {
      task: "定位编译与插件注册问题",
      skills: ["apollo-dev", "apollo-test"],
      trigger: "buildtool 编译失败或插件未被加载时。",
      inputs: ["完整编译错误", "BUILD / cyberfile.xml", "plugins.xml 和 pipeline 配置"],
      prompt: "请根据编译日志和配置文件，按“缺少依赖、目标名错误、插件未注册、配置路径错误”分类分析失败原因。每条结论都要引用我提供的错误行或配置行。",
      verify: "修复后重新编译，并在运行日志中确认插件已加载。",
      evidence: "编译日志与插件加载记录"
    },
    "lesson-18": {
      task: "辅助完成最小 Task 开发",
      skills: ["apollo-dev", "apollo-test"],
      trigger: "新增 Task 的代码、配置或编译验证阶段。",
      inputs: ["新增 Task 源码", "BUILD / cyberfile.xml", "plugins.xml", "编译或运行日志"],
      prompt: "请检查下面新增 Task 的代码和注册配置，列出还缺少的文件、注册项或配置项，并给出最小验证步骤。不要直接重写整个文件，只指出具体位置和修改原因。",
      verify: "按最小修改编译并运行，确认日志 Task 被调用后再扩展功能。",
      evidence: "Task 代码、构建日志和运行记录"
    },
    "lesson-19": {
      task: "从日志和 channel 定位问题",
      skills: ["apollo-dev", "apollo-test"],
      trigger: "DreamView 表现异常、channel 无消息或日志出现错误时。",
      inputs: ["cyber_monitor 输出", "日志片段", "record 或 channel 列表", "DreamView 现象描述"],
      prompt: "请把下面的日志、channel 和 DreamView 现象按时间顺序对应起来，说明哪个模块没有发布消息、哪个模块可能超时，以及下一步最值得检查的 channel。不要只根据一条错误日志下结论。",
      verify: "重新运行并对比 cyber_monitor、日志时间戳和 DreamView 状态。",
      evidence: "日志摘要与 channel 记录"
    },
    "lesson-20": {
      task: "解释评分与优化结果",
      skills: ["apollo-test", "apollo-eval"],
      trigger: "完成限速修改、record 和评分后。",
      inputs: ["record / channel_summary.csv", "score.json 或场景指标", "修改前后参数或代码差异"],
      prompt: "请根据下面的 record 指标、评分结果和代码差异，按安全性、舒适性、通行效率解释改动效果。必须区分真实测量值、AI 推测和建议；无法从数据确认的内容请列为待验证。",
      verify: "重新运行同一场景，比较修改前后指标，并保留 record、评分和报告作为证据。",
      evidence: "record、score、report.json / report.md"
    }
  };

  const matrix = [
    ["Linux 与 Apollo 环境", "02 环境检查", "apollo-env", "doctor.json"],
    ["Cyber RT 与模块通信", "03 运行场景", "apollo-dev", "channel 结构"],
    ["Planning 与 Task", "05 诊断与源码定位", "apollo-dev", "日志与代码位置"],
    ["record 与 channel", "06 录制与可视化", "apollo-test", "record / CSV"],
    ["TTC、Jerk、急刹", "07 评分与优化", "apollo-eval", "score / 报告"],
    ["报告与复盘", "08 报告与复盘", "apollo-test + apollo-eval", "report.json / report.md"]
  ];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function moduleFor(id) {
    return modules.find((item) => item.id === id) || modules[0];
  }

  function renderCourseModules() {
    const root = document.querySelector("[data-course-modules]");
    if (!root) return;
    root.innerHTML = "";
    modules.forEach((mod) => {
      const card = el("article", "course-module-card");
      card.appendChild(el("div", "course-module-code", mod.code));
      const body = el("div", "course-module-body");
      const head = el("div", "course-module-head");
      head.appendChild(el("h3", "", mod.title));
      head.appendChild(el("span", "course-module-range", `课程 ${mod.range} · ${mod.hours} 学时`));
      body.appendChild(head);
      body.appendChild(el("p", "", mod.summary));
      const foot = el("div", "course-module-foot");
      mod.ai.forEach((skill) => foot.appendChild(el("span", "course-skill", skill)));
      body.appendChild(foot);
      card.appendChild(body);
      root.appendChild(card);
    });
  }

  function renderCourseMatrix() {
    const root = document.querySelector("[data-course-matrix]");
    if (!root) return;
    root.innerHTML = "";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["学习内容", "对应实验阶段", "AI 技能", "产出证据"].forEach((label) => headRow.appendChild(el("th", "", label)));
    thead.appendChild(headRow);
    const tbody = document.createElement("tbody");
    matrix.forEach((row) => {
      const tr = document.createElement("tr");
      row.forEach((value, index) => {
        const td = document.createElement("td");
        if (index === 2) {
          value.split(" + ").forEach((skill) => td.appendChild(el("span", "course-skill", skill)));
        } else {
          td.textContent = value;
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    root.append(thead, tbody);
  }

  function renderLessonContext() {
    const header = document.querySelector(".lesson-header");
    const lessonId = document.body.dataset.lessonId;
    if (!header || !lessonId || !contexts[lessonId]) return;
    const ctx = contexts[lessonId];
    const mod = moduleFor(ctx.module);
    const box = el("section", "lesson-context");
    box.setAttribute("aria-label", "本课在项目课程中的位置");

    const fields = [
      ["课程模块", `${mod.code} ${mod.title}`, `${ctx.hours} 学时`],
      ["对应实验", ctx.stage, "8 阶段实验闭环"],
      ["本课产出", ctx.evidence, "可复查学习证据"]
    ];
    fields.forEach(([label, value, note]) => {
      const item = el("div", "lesson-context-item");
      item.appendChild(el("span", "", label));
      item.appendChild(el("strong", "", value));
      item.appendChild(el("small", "", note));
      box.appendChild(item);
    });

    const aiItem = el("div", "lesson-context-item");
    aiItem.appendChild(el("span", "", "AI 辅助"));
    const skills = el("strong", "lesson-context-skills");
    ctx.ai.forEach((skill) => skills.appendChild(el("code", "", skill)));
    aiItem.appendChild(skills);
    aiItem.appendChild(el("small", "", "脚本产出事实，AI 解释证据"));
    box.appendChild(aiItem);

    const kicker = header.querySelector(".lesson-kicker");
    if (kicker) kicker.insertAdjacentElement("afterend", box);
    else header.prepend(box);

    const link = el("a", "lesson-context-link", "进入对应实验台 →");
    link.href = "lab/crosswalk.html";
    box.appendChild(link);
  }


  function renderLessonAiGuide() {
    const header = document.querySelector(".lesson-header");
    const lessonId = document.body.dataset.lessonId;
    const practice = lessonId && aiPractices[lessonId];
    if (!header || !practice || header.nextElementSibling?.classList.contains("lesson-ai-guide")) return;

    const box = el("section", "lesson-ai-guide");
    const head = el("div", "lesson-ai-head");
    const headCopy = el("div");
    headCopy.appendChild(el("span", "lesson-ai-kicker", "AI 辅助任务"));
    headCopy.appendChild(el("h2", "", practice.task));
    head.appendChild(headCopy);
    const skillWrap = el("div", "lesson-ai-skills");
    practice.skills.forEach((skill) => skillWrap.appendChild(el("code", "", skill)));
    head.appendChild(skillWrap);
    box.appendChild(head);

    const grid = el("div", "lesson-ai-grid");
    const block = (label, value, list) => {
      const item = el("div", "lesson-ai-block");
      item.appendChild(el("span", "", label));
      if (list) {
        const ul = document.createElement("ul");
        list.forEach((text) => ul.appendChild(el("li", "", text)));
        item.appendChild(ul);
      } else {
        item.appendChild(el("p", "", value));
      }
      grid.appendChild(item);
    };
    block("使用时机", practice.trigger);
    block("提供给 AI", "", practice.inputs);
    block("重新验证", practice.verify);
    box.appendChild(grid);

    const details = document.createElement("details");
    details.className = "lesson-ai-prompt";
    const summary = document.createElement("summary");
    summary.textContent = "查看并复制提问模板";
    details.appendChild(summary);
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = practice.prompt;
    pre.appendChild(code);
    details.appendChild(pre);
    const copyButton = el("button", "lesson-ai-copy", "复制提问模板");
    copyButton.type = "button";
    details.appendChild(copyButton);
    box.appendChild(details);

    const footer = el("div", "lesson-ai-footer");
    footer.appendChild(el("small", "", `本课证据：${practice.evidence}。AI 只解释你提供的证据，事实、推测和建议必须分开；API Key 不要发给模型。`));
    const links = el("div", "lesson-ai-actions");
    const params = new URLSearchParams({ task: "crosswalk", lesson: lessonId, source: "apc", return: location.href });
    const launch = el("a", "lesson-ai-launch", "打开本地 Harness →");
    launch.href = "apollo-harness://open/?" + params.toString();
    const direct = el("a", "lesson-ai-direct", "已启动？直接打开");
    direct.href = "http://127.0.0.1:8765/?" + params.toString();
    links.append(launch, direct);
    footer.appendChild(links);
    box.appendChild(footer);

    const status = el("p", "lesson-ai-status", "");
    status.setAttribute("aria-live", "polite");
    status.hidden = true;
    box.appendChild(status);

    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(practice.prompt);
        copyButton.textContent = "已复制";
      } catch (error) {
        const textarea = document.createElement("textarea");
        textarea.value = practice.prompt;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
        copyButton.textContent = "已复制";
      }
      window.setTimeout(() => { copyButton.textContent = "复制提问模板"; }, 1400);
    });
    launch.addEventListener("click", () => {
      status.hidden = false;
      status.className = "lesson-ai-status is-pending";
      status.textContent = "正在唤起本地 Harness。若浏览器弹出系统提示，请选择“打开 Apollo_Harness”。";
    });

    header.insertAdjacentElement("afterend", box);
  }

  function init() {
    renderCourseModules();
    renderCourseMatrix();
    renderLessonContext();
    renderLessonAiGuide();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
