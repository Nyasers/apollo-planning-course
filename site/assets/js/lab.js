(function () {
  "use strict";
  const config = Object.assign({
    apiBase: "",
    simulationUrl: "",
    localPanelUrl: "http://127.0.0.1:8765",
    taskId: "crosswalk",
    lesson: "lesson-15",
    demoMode: true
  }, window.APOLLO_LAB_CONFIG || {});
  const metricsKey = "apollo-lab-metrics-v1";

  const stages = [
    { title: "实验准备", desc: "确认课程、实验目标和运行环境，进入人行道避让任务。" },
    { title: "环境检查", desc: "使用 apollo-env 检查 Docker、aem、buildtool、磁盘和网络。" },
    { title: "运行场景", desc: "在 DreamView/SimControl 中启动人行道避让场景。" },
    { title: "观察问题", desc: "观察规划轨迹、速度曲线和车辆对行人的避让行为。" },
    { title: "AI 辅助诊断", desc: "使用 apollo-dev 定位相关配置、源码和日志。" },
    { title: "录制与可视化", desc: "使用 apollo-test 录制 record，生成 channel 和图表报告。" },
    { title: "评分与优化", desc: "使用 apollo-eval 查看 TTC、加速度、Jerk 和场景评分。" },
    { title: "报告与复盘", desc: "形成优化前后对比、实验结论和能力反馈。" }
  ];

  const demoMetrics = {
    scenario: "crosswalk",
    scenarioName: "人行道避让",
    before: { ttc: 1.8, lonAccel: 3.6, jerk: 4.8, hardBrake: 2, score: 82 },
    after: { ttc: 2.7, lonAccel: 2.1, jerk: 2.8, hardBrake: 0, score: 94 },
    updatedAt: new Date().toISOString()
  };

  function readMetrics() {
    try { return JSON.parse(localStorage.getItem(metricsKey) || "null"); }
    catch (error) { return null; }
  }

  function writeMetrics(value) {
    localStorage.setItem(metricsKey, JSON.stringify(value));
  }

  function localPanelHref() {
    const base = (config.localPanelUrl || "http://127.0.0.1:8765").replace(/\/$/, "");
    const params = new URLSearchParams({
      task: config.taskId || "crosswalk",
      lesson: config.lesson || "lesson-15",
      source: "apc",
      return: window.location.href
    });
    return base + "/?" + params.toString();
  }

  function syncLocalPanelLinks() {
    document.querySelectorAll("[data-local-panel]").forEach((link) => {
      link.setAttribute("href", localPanelHref());
    });
  }

  function setText(root, selector, value) {
    const el = root && root.querySelector(selector);
    if (el) el.textContent = value;
  }

  function initRunPage() {
    const run = document.querySelector("[data-lab-run]");
    if (!run) return;

    const buttons = Array.from(run.querySelectorAll("[data-lab-stage]"));
    const scene = run.querySelector("[data-lab-scene]");
    const consoleBox = run.querySelector("[data-lab-console]");
    const runButton = run.querySelector("[data-run-demo]");
    const reportLink = run.querySelector("[data-report-link]");
    const progress = run.querySelector("[data-lab-progress]");
    const agentLog = run.querySelector("[data-agent-log]");
    const agentInput = run.querySelector("[data-agent-input]");
    const agentForm = run.querySelector("[data-agent-form]");
    let current = 0;

    function appendConsole(text) {
      if (!consoleBox) return;
      const line = document.createElement("div");
      line.className = "lab-console-line";
      line.textContent = text;
      consoleBox.appendChild(line);
      consoleBox.scrollTop = consoleBox.scrollHeight;
    }

    function appendMessage(role, title, text) {
      if (!agentLog) return;
      const message = document.createElement("div");
      message.className = "lab-message " + role;
      const strong = document.createElement("strong");
      strong.textContent = title;
      message.appendChild(strong);
      message.appendChild(document.createTextNode(text));
      agentLog.appendChild(message);
      agentLog.scrollTop = agentLog.scrollHeight;
    }

    function renderStage(index) {
      current = Math.max(0, Math.min(index, stages.length - 1));
      const stage = stages[current];
      setText(run, "[data-stage-title]", stage.title);
      setText(run, "[data-stage-desc]", stage.desc);
      setText(run, "[data-stage-count]", String(current + 1).padStart(2, "0") + " / " + String(stages.length).padStart(2, "0"));
      if (progress) progress.style.width = Math.round(((current + 1) / stages.length) * 100) + "%";
      buttons.forEach((button, buttonIndex) => {
        button.classList.toggle("is-active", buttonIndex === current);
        button.classList.toggle("is-done", buttonIndex < current);
      });
    }

    buttons.forEach((button, index) => {
      button.addEventListener("click", () => renderStage(index));
    });

    const messages = {
      env: "环境检查完成：Docker 正常，aem 正常，buildtool 可用；当前为教学演示模式，未执行任何系统修改。本地模式下由 apollo-env 返回真实检查结果。",
      dev: "AI 诊断建议：先检查 crosswalk TrafficRule、参考线停止点和速度边界配置。证据来自 planning 日志，建议按“日志 → 场景配置 → Task pipeline”顺序定位。",
      test: "数据采集建议：使用 pnc profile 录制 record，重点检查 planning、control、localization 和 perception channel；由 apollo-test 生成 channel_summary.csv、PNG 和 Markdown 报告。",
      eval: "评分提示：当前演示数据中 TTC 偏低且急刹次数较多。建议降低通过人行道前的速度上限，并观察 Jerk 是否下降。该结论只有在本地 Harness 和 apollo-eval 运行后才作为真实实验证据。"
    };

    async function requestAgent(skill, message) {
      if (!config.apiBase) {
        await new Promise((resolve) => window.setTimeout(resolve, 450));
        return { title: "Apollo Claw · 演示模式", text: messages[skill] || messages.dev };
      }
      const response = await fetch(config.apiBase.replace(/\/$/, "") + "/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skill, message, experiment: "crosswalk", stage: current + 1 })
      });
      if (!response.ok) throw new Error("Agent API " + response.status);
      const payload = await response.json();
      return { title: "Apollo Claw · " + skill, text: payload.message || payload.text || "未返回内容。" };
    }

    run.querySelectorAll("[data-agent-skill]").forEach((button) => {
      button.addEventListener("click", async () => {
        const skill = button.dataset.agentSkill;
        appendMessage("user", "学生", button.textContent.trim());
        try {
          const result = await requestAgent(skill, button.textContent.trim());
          appendMessage("system", result.title, result.text);
        } catch (error) {
          appendMessage("system", "调用失败", error.message);
        }
      });
    });

    if (agentForm) {
      agentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = agentInput && agentInput.value.trim();
        if (!text) return;
        appendMessage("user", "学生", text);
        agentInput.value = "";
        try {
          const result = await requestAgent("dev", text);
          appendMessage("system", result.title, result.text);
        } catch (error) {
          appendMessage("system", "调用失败", error.message);
        }
      });
    }

    run.querySelectorAll("[data-open-simulation]").forEach((button) => {
      button.addEventListener("click", () => {
        if (!config.simulationUrl) {
          appendConsole("尚未配置 Apollo Studio/DreamView 地址，当前使用场景演示模式。");
          appendMessage("system", "仿真入口未配置", "请在 APOLLO_LAB_CONFIG.simulationUrl 中配置真实实验入口。MVP 当前展示教学流程和数据结构，不冒充真实仿真。");
          return;
        }
        window.open(config.simulationUrl, "_blank", "noopener");
      });
    });

    if (runButton) {
      runButton.addEventListener("click", async () => {
        runButton.disabled = true;
        runButton.textContent = "运行中…";
        if (consoleBox) consoleBox.textContent = "";
        const sequence = [
          [0, "初始化实验任务：人行道避让", "idle"],
          [1, "apollo-env：环境检查通过", "running"],
          [2, "启动场景：行人横穿 + 静态障碍物", "running"],
          [3, "检测到通过人行道前减速偏急，TTC 偏低", "avoiding"],
          [4, "apollo-dev：定位 crosswalk 规则和速度边界参数", "avoiding"],
          [5, "apollo-test：生成 channel 清单、轨迹和速度图表", "avoiding"],
          [6, "apollo-eval：场景得分 82 → 94，急刹 2 → 0", "passed"],
          [7, "报告已生成：优化前后指标对比完成", "passed"]
        ];
        for (const item of sequence) {
          renderStage(item[0]);
          appendConsole(item[1]);
          if (scene) scene.dataset.state = item[2];
          await new Promise((resolve) => window.setTimeout(resolve, 520));
        }
        writeMetrics({ ...demoMetrics, updatedAt: new Date().toISOString() });
        runButton.disabled = false;
        runButton.textContent = "重新运行演示";
        if (reportLink) {
          reportLink.classList.add("is-ready");
          reportLink.removeAttribute("aria-disabled");
        }
      });
    }

    renderStage(0);
    const existing = readMetrics();
    if (!existing && agentLog) {
      appendMessage("system", "Apollo Claw · MVP 原型", "当前为前端演示模式。配置 APOLLO_LAB_CONFIG.apiBase 后，可接入真实的 Apollo Claw Harness、DeepSeek/Qwen 模型和后端工具。");
    }
  }

  function initReportPage() {
    const report = document.querySelector("[data-lab-report]");
    if (!report) return;
    const data = readMetrics() || demoMetrics;
    const rows = [
      ["TTC", "s", data.before.ttc, data.after.ttc, 3],
      ["纵向加速度", "m/s²", data.before.lonAccel, data.after.lonAccel, 4],
      ["Jerk", "m/s³", data.before.jerk, data.after.jerk, 5],
      ["急刹次数", "次", data.before.hardBrake, data.after.hardBrake, 3]
    ];

    rows.forEach(([label, unit, before, after, max]) => {
      const row = document.createElement("div");
      row.className = "lab-bar-row";
      const name = document.createElement("span");
      name.textContent = label;
      const bars = document.createElement("div");
      const barBefore = document.createElement("div");
      barBefore.className = "lab-bar before";
      const fillBefore = document.createElement("i");
      fillBefore.style.width = Math.min(100, (before / max) * 100) + "%";
      barBefore.appendChild(fillBefore);
      const barAfter = document.createElement("div");
      barAfter.className = "lab-bar after";
      const fillAfter = document.createElement("i");
      fillAfter.style.width = Math.min(100, (after / max) * 100) + "%";
      barAfter.appendChild(fillAfter);
      bars.append(barBefore, barAfter);
      const value = document.createElement("span");
      value.textContent = before + " → " + after + " " + unit;
      row.append(name, bars, value);
      report.querySelector("[data-report-bars]")?.appendChild(row);
    });

    setText(report, "[data-report-score-before]", String(data.before.score));
    setText(report, "[data-report-score-after]", String(data.after.score));
    setText(report, "[data-report-scenario]", data.scenarioName || "人行道避让");

    const download = report.querySelector("[data-download-report]");
    if (download) {
      download.addEventListener("click", () => {
        const lines = [
          "# Apollo Claw 实验报告（MVP 演示）",
          "",
          "实验场景：" + (data.scenarioName || "人行道避让"),
          "",
          "| 指标 | 优化前 | 优化后 |",
          "| --- | ---: | ---: |",
          "| 场景得分 | " + data.before.score + " | " + data.after.score + " |",
          "| TTC | " + data.before.ttc + " s | " + data.after.ttc + " s |",
          "| 纵向加速度 | " + data.before.lonAccel + " m/s² | " + data.after.lonAccel + " m/s² |",
          "| Jerk | " + data.before.jerk + " m/s³ | " + data.after.jerk + " m/s³ |",
          "| 急刹次数 | " + data.before.hardBrake + " | " + data.after.hardBrake + " |",
          "",
          "结论：通过 Apollo Claw 辅助定位和参数优化，急刹显著减少，舒适性和安全性提升。"
        ];
        const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "apollo-claw-mvp-report.md";
        link.click();
        URL.revokeObjectURL(link.href);
      });
    }
  }

  syncLocalPanelLinks();
  initRunPage();
  initReportPage();
})();
