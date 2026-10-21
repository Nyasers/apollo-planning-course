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

  function init() {
    renderCourseModules();
    renderCourseMatrix();
    renderLessonContext();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
