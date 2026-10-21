(function () {
  "use strict";
  const config = Object.assign({
    apiBase: "",
    simulationUrl: "",
    localPanelUrl: "http://127.0.0.1:8765",
    launcherProtocol: "apollo-harness",
    taskId: "crosswalk",
    lesson: "lesson-15",
    demoMode: true
  }, window.APOLLO_LAB_CONFIG || {});
  const metricsKey = "apollo-lab-metrics-v1";
  const harnessReportKey = "apollo-lab-harness-report-v1";

  const stages = [
    { title: "实验准备", desc: "确认课程、实验目标和运行环境，进入人行道避让任务。" },
    { title: "环境检查", desc: "使用 apollo-env 检查 Docker、aem、buildtool、磁盘和网络。" },
    { title: "运行场景", desc: "在 DreamView/SimControl 中启动人行道避让场景。" },
    { title: "观察问题", desc: "观察车辆减速并在停止线前停车，等待行人通过。" },
    { title: "AI 辅助诊断", desc: "确认车辆停车等待的原因是行人仍在人行横道内。" },
    { title: "录制与可视化", desc: "行人离开后车辆继续通行，使用 apollo-test 采集数据。" },
    { title: "评分与优化", desc: "使用 apollo-eval 查看 TTC、加速度、Jerk 和场景评分。" },
    { title: "报告与复盘", desc: "形成优化前后对比、实验结论和能力反馈。" }
  ];

  const demoMetrics = {
    scenario: "crosswalk",
    scenarioName: "人行道避让",
    source: "site-demo",
    mode: "demo",
    before: { ttc: 1.4, lonAccel: 3.6, jerk: 4.8, hardBrake: 2, score: 82 },
    after: { ttc: 2.3, lonAccel: 2.1, jerk: 2.8, hardBrake: 0, score: 94 },
    updatedAt: new Date().toISOString()
  };

  function readMetrics() {
    try { return JSON.parse(localStorage.getItem(metricsKey) || "null"); }
    catch (error) { return null; }
  }

  function writeMetrics(value) {
    localStorage.setItem(metricsKey, JSON.stringify(value));
  }

  function localPanelParams() {
    return new URLSearchParams({
      task: config.taskId || "crosswalk",
      lesson: config.lesson || "lesson-15",
      source: "apc",
      return: window.location.href
    });
  }

  function localPanelHref() {
    const protocol = config.launcherProtocol || "apollo-harness";
    return protocol + "://open/?" + localPanelParams().toString();
  }

  function localPanelDirectHref() {
    const base = (config.localPanelUrl || "http://127.0.0.1:8765").replace(/\/$/, "");
    return base + "/?" + localPanelParams().toString();
  }

  function syncLocalPanelLinks() {
    document.querySelectorAll("[data-local-panel]").forEach((link) => {
      link.setAttribute("href", localPanelHref());
    });
    document.querySelectorAll("[data-local-direct]").forEach((link) => {
      link.setAttribute("href", localPanelDirectHref());
    });
  }

  function initLocalLauncher() {
    const launchLinks = document.querySelectorAll("[data-local-launch]");
    const status = document.querySelector("[data-local-launch-status]");
    launchLinks.forEach((link) => {
      link.addEventListener("click", () => {
        if (!status) return;
        let leftPage = false;
        const markLeft = () => { leftPage = true; };
        window.addEventListener("blur", markLeft, { once: true });
        status.hidden = false;
        status.className = "lab-local-status is-pending";
        status.textContent = "正在唤起本机启动器，请在弹出的系统提示中选择“打开 Apollo_Harness”。首次启动通常需要 5—15 秒。";
        window.setTimeout(() => {
          if (!status || status.classList.contains("is-warn")) return;
          if (leftPage || document.hidden) {
            status.className = "lab-local-status is-ok";
            status.textContent = "已向本机启动器发出请求。Harness 就绪后会自动打开；如果没有打开，请使用下方“直接打开本地 Harness”。";
          } else {
            status.className = "lab-local-status is-warn";
            status.textContent = "未检测到启动器响应。请确认已运行 install-harness-launcher.ps1，并允许浏览器打开 Apollo_Harness。";
          }
        }, 3000);
      });
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
    const results = run.querySelector("[data-lab-results]");
    const sceneStatus = run.querySelector("[data-lab-scene-status]");
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
        if (results) results.classList.add("is-hidden");
        const sequence = [
          [0, "初始化实验任务：人行道避让", "idle", "准备"],
          [1, "apollo-env：环境检查通过", "idle", "环境就绪"],
          [2, "启动场景：行人从右侧进入人行横道", "running", "接近人行横道"],
          [3, "车辆开始减速，目标是在停止线前停车", "stopping", "减速停车"],
          [4, "车辆在停止线前停车，等待行人通过", "waiting", "等待行人通过"],
          [5, "行人走出人行横道，车辆仍保持停车", "cleared", "行人离开"],
          [6, "确认前方安全，车辆继续直线通行；apollo-test 生成数据", "passed", "车辆继续行驶"],
          [7, "报告已生成：优化前后指标对比完成", "passed", "实验完成"]
        ];
        for (const item of sequence) {
          renderStage(item[0]);
          appendConsole(item[1]);
          if (scene) scene.dataset.state = item[2];
          if (sceneStatus) sceneStatus.textContent = item[3];
          await new Promise((resolve) => window.setTimeout(resolve, 620));
        }
        writeMetrics({ ...demoMetrics, updatedAt: new Date().toISOString() });
        if (results) results.classList.remove("is-hidden");
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

  function readHarnessReport() {
    try {
      const report = JSON.parse(localStorage.getItem(harnessReportKey) || "null");
      return report && validateHarnessReport(report).length === 0 ? report : null;
    } catch (error) {
      return null;
    }
  }

  function writeHarnessReport(report) {
    localStorage.setItem(harnessReportKey, JSON.stringify(report));
  }

  async function initLabIndexSnapshot() {
    const snapshot = document.querySelector("[data-lab-snapshot]");
    if (!snapshot) return;

    const report = readHarnessReport();
    const source = "browser";
    if (!report) {
      setText(document, "[data-lab-source]", "当前没有可读取的实验报告。");
      setText(document, "[data-lab-headline-summary]", "完成本地实验并导入 report.json 后，这里会显示最新结果。");
      setText(document, "[data-lab-current-copy]", "暂无当前报告指标。");
      setText(document, "[data-lab-failing]", "暂无未通过指标数据");
      return;
    }

    const meta = report.meta || {};
    const score = report.score || {};
    const record = report.record || {};
    const metrics = report.metrics || {};
    const lab = report.lab || {};
    const current = lab.current || {};
    const scoreMetrics = Array.isArray(score.metrics) ? score.metrics : [];
    const passedCount = scoreMetrics.filter((item) => item && item.pass === true).length;
    const passed = score.passed_metrics || current.passed_metrics || (scoreMetrics.length ? passedCount + "/" + scoreMetrics.length : "—");
    const ttc = scoreMetrics.find((item) => String(item.name || "").toUpperCase() === "TTC") || {};
    const ttcText = ttc.total !== undefined ? String(ttc.fail ?? "—") + "/" + String(ttc.total) : "—";
    const failing = scoreMetrics.filter((item) => item && item.pass === false).map((item) => item.name).filter(Boolean);
    const messageCount = record.message_count ?? current.message_count ?? "—";
    const duration = record.duration_sec ?? current.duration_sec ?? "—";
    const channelCount = record.channel_count ?? current.channel_count ?? "—";
    const jerk = metrics.max_jerk ?? current.metrics?.max_jerk ?? "—";
    const hardBrake = metrics.hard_brake ?? current.metrics?.hard_brake ?? "—";
    const scenario = meta.scenario || meta.task || "人行道避让";
    const statusMap = { evaluated: "已完成自评", recorded: "已录制", reported: "已生成报告", record_failed: "录制失败", environment_warning: "环境待检查", created: "已创建", demo: "演示报告" };
    const statusText = statusMap[meta.status] || meta.status || "当前报告";
    const sourceText = source === "browser" ? "当前浏览器最新导入报告 · 本地自评" : "网站内置阶段性报告 · 本地自评";

    setText(document, "[data-lab-score]", passed);
    setText(document, "[data-lab-score-note]", score.is_official === true ? "官方评分" : "通过项");
    setText(document, "[data-lab-ttc]", ttcText);
    setText(document, "[data-lab-ttc-note]", ttc.pass === true ? "已通过" : ttc.total !== undefined ? "仍需优化" : "无 TTC 数据");
    setText(document, "[data-lab-messages]", formatCount(messageCount));
    setText(document, "[data-lab-duration]", duration === "—" ? "record 时长未知" : duration + " 秒记录");
    setText(document, "[data-lab-source]", sourceText);
    setText(document, "[data-lab-headline-summary]", scenario + " 当前报告已载入。结果、问题和证据一起保留，作为下一轮优化的起点。");
    setText(document, "[data-lab-badge]", lab.badge || score.source || "阶段性本地自评");
    setText(document, "[data-lab-headline]", scenario + " · " + statusText);
    setText(document, "[data-lab-meta]", "实验编号 " + (meta.experiment_id || "—") + " · " + formatDateTime(meta.created_at) + " · " + (duration === "—" ? "record 时长未知" : duration + " 秒 record"));
    setText(document, "[data-lab-score-detail]", passed);
    setText(document, "[data-lab-ttc-detail]", ttcText);
    setText(document, "[data-lab-messages-detail]", formatCount(messageCount));
    setText(document, "[data-lab-duration-detail]", duration === "—" ? "record 时长未知" : duration + " 秒");
    setText(document, "[data-lab-channels]", String(channelCount));
    setText(document, "[data-lab-jerk]", jerk === "—" ? "—" : formatNumber(jerk, 2));
    setText(document, "[data-lab-hard-brake]", String(hardBrake));
    setText(document, "[data-lab-failing]", failing.length ? "仍待优化：" + failing.join("、") + (ttc.total !== undefined ? "（TTC " + ttcText + " 失败帧）" : "") : "未发现未通过指标，仍需教师复核");
    setText(document, "[data-lab-current-copy]", passed + " 通过" + (failing.length ? "，" + failing.join("、") + " 仍需优化" : "") + "；共 " + formatCount(messageCount) + " 条 record 消息。当前数据和问题都保留。");
  }

  function validateHarnessReport(report) {
    const errors = [];
    if (!report || typeof report !== "object" || Array.isArray(report)) return ["文件内容不是 JSON 对象"];
    ["meta", "environment", "record", "metrics", "ai", "verification", "evidence", "capability"].forEach((key) => {
      if (!(key in report)) errors.push("缺少 " + key + " 字段");
    });
    const meta = report.meta || {};
    ["experiment_id", "task", "created_at", "source", "mode"].forEach((key) => {
      if (!meta[key]) errors.push("缺少 meta." + key);
    });
    if (meta.mode && !["planned", "real", "demo", "replay"].includes(meta.mode)) errors.push("meta.mode 无效");
    if (!report.metrics || typeof report.metrics !== "object" || Array.isArray(report.metrics)) errors.push("metrics 必须是对象");
    if (report.score && typeof report.score.is_official !== "boolean") errors.push("score.is_official 必须是布尔值");
    if (!Array.isArray(report.evidence)) errors.push("evidence 必须是数组");
    (Array.isArray(report.evidence) ? report.evidence : []).forEach((item, index) => {
      if (!item || typeof item !== "object" || !item.type || !item.path) errors.push("evidence[" + index + "] 缺少 type 或 path");
    });
    const raw = JSON.stringify(report);
    if (/sk-[A-Za-z0-9_-]{8,}/.test(raw) || /DEEPSEEK_API_KEY\s*=/i.test(raw)) errors.push("报告中疑似包含 API Key 或密钥配置");
    return errors;
  }

  function emptyReportData() {
    return {
      meta: {
        experiment_id: "",
        task: "",
        scenario: "等待导入报告",
        created_at: "",
        source: "empty",
        mode: "demo",
        status: "empty"
      },
      environment: {},
      record: { channel_count: null, message_count: null, duration_sec: null, status: "empty" },
      metrics: {},
      verification: {},
      score: { source: "尚未导入报告", is_official: false },
      ai: { skills: [] },
      lab: {},
      evidence: [],
      capability: {},
      errors: []
    };
  }
  function demoReportData() {
    const saved = readMetrics() || demoMetrics;
    const before = Object.assign({}, demoMetrics.before, saved.before || {});
    const after = Object.assign({}, demoMetrics.after, saved.after || {});
    return {
      meta: {
        experiment_id: "SITE-DEMO-CROSSWALK",
        task: "crosswalk",
        scenario: saved.scenarioName || demoMetrics.scenarioName,
        created_at: saved.updatedAt || demoMetrics.updatedAt,
        source: "site-demo",
        mode: "demo",
        status: "demo"
      },
      environment: { demo: true },
      record: { duration_sec: 25, channel_count: 6, message_count: 128430 },
      metrics: {
        min_ttc: before.ttc,
        max_acceleration: before.lonAccel,
        max_jerk: before.jerk,
        hard_brake: before.hardBrake
      },
      verification: {
        min_ttc: after.ttc,
        max_acceleration: after.lonAccel,
        max_jerk: after.jerk,
        hard_brake: after.hardBrake,
        score_before: before.score,
        score_after: after.score
      },
      score: { source: "网站演示，不替代官方评测", value: after.score, is_official: false },
      ai: {
        skills: ["apollo-env", "apollo-dev", "apollo-test", "apollo-eval"],
        facts: ["演示中最低 TTC 为 1.4 秒", "演示中发生 2 次急刹", "车辆在停止线前等待行人通过"],
        hypotheses: ["通过人行道前减速偏晚，导致安全距离不足"],
        suggestions: ["降低人行道前速度上限", "检查 crosswalk TrafficRule 和停止线参数", "重新 record 并对比加速度与 Jerk"],
        source_refs: ["网站内人行道演示序列", "课程实验台指标卡片"],
        student_confirmed: false
      },
      evidence: [
        { type: "demo-run", path: "site/lab/crosswalk.html", summary: "网站内车辆停车等待行人的演示过程" },
        { type: "demo-metrics", path: "浏览器 localStorage", summary: "TTC、加速度、Jerk 和急刹次数演示指标" }
      ],
      capability: { environment: 82, log_analysis: 76, data_capture: 88, parameter_tuning: 69, reporting: 74, ai_usage: 92 },
      errors: []
    };
  }

  function incomingRunSummary() {
    const params = new URLSearchParams(window.location.search);
    const run = params.get("apc_run");
    if (!run) return null;
    return {
      run,
      status: params.get("apc_status") || "",
      score: params.get("apc_score") || "",
      source: params.get("apc_source") || ""
    };
  }

  function numberOrNull(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function formatCount(value) {
    const number = numberOrNull(value);
    return number === null ? "—" : number.toLocaleString("zh-CN");
  }

  function formatNumber(value, digits) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
    const number = Number(value);
    if (Number.isInteger(number)) return String(number);
    return number.toFixed(digits ?? 2).replace(/0+$/, "").replace(/\.$/, "");
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function metricValue(section, keys) {
    if (!section || typeof section !== "object") return null;
    for (const key of keys) {
      const value = numberOrNull(section[key]);
      if (value !== null) return value;
    }
    return null;
  }

  function metricValueFrom(sections, keys) {
    for (const section of sections) {
      const value = metricValue(section, keys);
      if (value !== null) return value;
    }
    return null;
  }

  function setImportStatus(root, text, kind) {
    const el = root.querySelector("[data-report-import-status]");
    if (!el) return;
    el.textContent = text;
    el.className = kind || "";
  }

  function fillList(root, selector, values, emptyText) {
    const list = root.querySelector(selector);
    if (!list) return;
    list.innerHTML = "";
    const items = Array.isArray(values) ? values.filter((value) => String(value ?? "").trim()) : [];
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "is-empty";
      li.textContent = emptyText || "暂无";
      list.appendChild(li);
      return;
    }
    items.forEach((value) => {
      const li = document.createElement("li");
      li.textContent = String(value);
      list.appendChild(li);
    });
  }

  function renderEvidence(root, evidence) {
    const list = root.querySelector("[data-report-evidence]");
    if (!list) return;
    list.innerHTML = "";
    if (!Array.isArray(evidence) || !evidence.length) {
      const li = document.createElement("li");
      li.className = "is-empty";
      li.textContent = "暂无证据文件";
      list.appendChild(li);
      return;
    }
    evidence.forEach((item) => {
      const li = document.createElement("li");
      const copy = document.createElement("span");
      const type = document.createElement("strong");
      type.textContent = item.type || "file";
      const summary = document.createElement("small");
      summary.textContent = item.summary || "未提供摘要";
      copy.append(type, summary);
      const path = document.createElement("code");
      path.textContent = item.path || "—";
      li.append(copy, path);
      list.appendChild(li);
    });
  }

  function environmentLabel(environment) {
    if (!environment || typeof environment !== "object" || Object.keys(environment).length === 0) return "未绑定环境检查";
    if (environment.error) return "环境检查异常";
    return "已记录环境检查";
  }

  function renderScoreMetrics(root, metricList) {
    const box = root.querySelector("[data-report-score-table]");
    if (!box) return;
    box.innerHTML = "";
    const items = Array.isArray(metricList) ? metricList : [];
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "lab-report-empty";
      empty.textContent = "当前报告没有逐项场景指标。";
      box.appendChild(empty);
      return;
    }
    const table = document.createElement("table");
    table.className = "lab-table";
    const thead = document.createElement("thead");
    const header = document.createElement("tr");
    ["指标", "结果", "得分", "未通过帧"].forEach((label) => {
      const th = document.createElement("th");
      th.textContent = label;
      header.appendChild(th);
    });
    thead.appendChild(header);
    const tbody = document.createElement("tbody");
    items.forEach((metric) => {
      const row = document.createElement("tr");
      const name = document.createElement("td");
      name.textContent = metric.name || "—";
      const result = document.createElement("td");
      const isPass = metric.pass === true;
      result.textContent = isPass ? "PASS" : "FAIL";
      result.className = isPass ? "is-pass" : "is-fail";
      const score = document.createElement("td");
      let scoreValue = numberOrNull(metric.score);
      if (!isPass && scoreValue === 100) scoreValue = null;
      score.textContent = scoreValue === null ? "—" : formatNumber(scoreValue, 0);
      const fail = document.createElement("td");
      const failCount = numberOrNull(metric.fail);
      const total = numberOrNull(metric.total);
      fail.textContent = failCount === null && total === null ? "—" : (failCount ?? "—") + "/" + (total ?? "—");
      row.append(name, result, score, fail);
      tbody.appendChild(row);
    });
    table.append(thead, tbody);
    box.appendChild(table);
  }

  function renderCapability(root, capability) {
    const box = root.querySelector("[data-report-capability]");
    if (!box) return;
    box.innerHTML = "";
    const labels = {
      environment: "环境诊断",
      log_analysis: "日志定位",
      data_capture: "数据采集",
      parameter_tuning: "参数优化",
      reporting: "报告表达",
      ai_usage: "AI 使用规范"
    };
    const entries = Object.entries(capability || {}).filter(([key, value]) => key in labels && numberOrNull(value) !== null);
    if (!entries.length) {
      const empty = document.createElement("p");
      empty.className = "lab-report-empty";
      empty.textContent = "当前报告没有能力画像数据。";
      box.appendChild(empty);
      return;
    }
    entries.forEach(([key, value]) => {
      const score = Math.max(0, Math.min(100, Number(value)));
      const row = document.createElement("div");
      row.className = "lab-capability-row";
      const label = document.createElement("span");
      label.textContent = labels[key];
      const bar = document.createElement("div");
      bar.className = "lab-capability-bar";
      const fill = document.createElement("i");
      fill.style.width = score + "%";
      bar.appendChild(fill);
      const strong = document.createElement("strong");
      strong.textContent = formatNumber(score, 0);
      row.append(label, bar, strong);
      box.appendChild(row);
    });
  }

  function reportConclusion(report) {
    const record = report.record || {};
    const metrics = report.metrics || {};
    const verify = report.verification || {};
    const score = report.score || {};
    if (record.channel_count === 0 || record.status === "empty") {
      return "本报告的 record channels 为 0，说明场景或模块尚未产生有效数据。应先启动 DreamView/SimControl 场景，再重新 record。";
    }
    const ttcBefore = metricValue(metrics, ["min_ttc", "ttc"]);
    const ttcAfter = metricValue(verify, ["min_ttc", "ttc"]);
    const brakeBefore = metricValue(metrics, ["hard_brake"]);
    const brakeAfter = metricValue(verify, ["hard_brake"]);
    if (ttcBefore !== null && ttcAfter !== null) {
      const trend = ttcAfter >= ttcBefore ? "提高" : "下降";
      const brakeText = brakeBefore !== null && brakeAfter !== null ? "，急刹次数由 " + formatNumber(brakeBefore, 0) + " 次变为 " + formatNumber(brakeAfter, 0) + " 次" : "";
      return "最小 TTC 由 " + formatNumber(ttcBefore) + " 秒" + trend + "至 " + formatNumber(ttcAfter) + " 秒" + brakeText + "。需结合 trajectory、channel 曲线和教师复核判断改进是否成立。";
    }
    if (score.value !== null && score.value !== undefined) {
      return "当前报告得分为 " + formatNumber(score.value) + "，评分来源为 " + (score.source || "未知") + (score.is_official ? "。该分数标记为官方评分。" : "。该分数不是官方评分。");
    }
    if (Array.isArray(score.metrics) && score.metrics.length) {
      const failed = score.metrics.filter((item) => item && item.pass === false).map((item) => item.name).filter(Boolean);
      const passed = score.passed_metrics || (score.metrics.filter((item) => item && item.pass === true).length + "/" + score.metrics.length);
      return "场景自评通过 " + passed + " 项" + (failed.length ? "；未通过：" + failed.join("、") + "。" : "。") + "该结果是本地自评估，不是官方评分。";
    }
    return "报告已生成，但尚无可比较的优化前后指标。请检查 record、apollo-eval 和 verification 字段。";
  }

  function reportToMarkdown(report) {
    const meta = report.meta || {};
    const record = report.record || {};
    const metrics = report.metrics || {};
    const verification = report.verification || {};
    const score = report.score || {};
    const ai = report.ai || {};
    const lab = report.lab || {};
    const lines = [
      "# Apollo Claw 实验报告摘要",
      "",
      "- 实验编号：" + (meta.experiment_id || "—"),
      "- 实验任务：" + (meta.scenario || meta.task || "—"),
      "- 数据来源：" + (meta.source || "—"),
      "- 数据模式：" + (meta.mode || "—"),
      "- 生成时间：" + formatDateTime(meta.created_at),
      "- record：" + (record.channel_count ?? "—") + " channels / " + (record.message_count ?? "—") + " messages",
      "- 场景得分：" + (score.value ?? "—") + "（" + (score.source || "未评分") + "，官方=" + (score.is_official ? "是" : "否") + "）",
      "",
      "## 关键指标",
      "",
      "| 指标 | 优化前 | 当前报告 |",
      "| --- | ---: | ---: |",
      "| 最小 TTC（s） | " + formatNumber(metricValue(metrics, ["min_ttc", "ttc"])) + " | " + formatNumber(metricValue(verification, ["min_ttc", "ttc"])) + " |",
      "| 最大纵向加速度（m/s²） | " + formatNumber(metricValue(metrics, ["max_acceleration", "lon_accel"])) + " | " + formatNumber(metricValue(verification, ["max_acceleration", "lon_accel"])) + " |",
      "| 最大 Jerk（m/s³） | " + formatNumber(metricValue(metrics, ["max_jerk", "jerk"])) + " | " + formatNumber(metricValue(verification, ["max_jerk", "jerk"])) + " |",
      "| 急刹次数 | " + formatNumber(metricValue(metrics, ["hard_brake"]), 0) + " | " + formatNumber(metricValue(verification, ["hard_brake"]), 0) + " |",
      "",
      ...(Array.isArray(score.metrics) && score.metrics.length ? [
        "## 场景指标",
        "",
        "| 指标 | 结果 | 得分 | 未通过帧 |",
        "| --- | --- | ---: | ---: |",
        ...score.metrics.map((metric) => "| " + (metric.name || "—") + " | " + (metric.pass ? "PASS" : "FAIL") + " | " + (metric.pass === false && numberOrNull(metric.score) === 100 ? "—" : (numberOrNull(metric.score) === null ? "—" : formatNumber(metric.score, 0))) + " | " + (metric.fail ?? "—") + "/" + (metric.total ?? "—") + " |"),
        ""
      ] : []),
      ...(Array.isArray(lab.comparison) && lab.comparison.length ? [
        "## 基线与本轮",
        "",
        "| 指标 | Baseline | 本轮 | 变化 |",
        "| --- | --- | --- | --- |",
        ...lab.comparison.map((item) => "| " + (item.label || item.id || "—") + " | " + String(item.before ?? "—") + " " + (item.before_detail || "") + " | " + String(item.after ?? "—") + " " + (item.after_detail || "") + " | " + (item.status || "—") + " |"),
        ""
      ] : []),
      "## AI 事实",
      "",
      ...(ai.facts || []).map((item) => "- " + item),
      "",
      "## AI 推测",
      "",
      ...(ai.hypotheses || []).map((item) => "- " + item),
      "",
      "## AI 建议",
      "",
      ...(ai.suggestions || []).map((item) => "- " + item),
      "",
      ...(lab.human_review && lab.human_review.length ? ["## 人工核验", "", ...lab.human_review.map((item) => "- " + item), ""] : []),
      ...(lab.warnings && lab.warnings.length ? ["## 需要关注", "", ...lab.warnings.map((item) => "- " + item), ""] : []),
      ...(lab.next_actions && lab.next_actions.length ? ["## 下一步", "", ...lab.next_actions.map((item) => "- " + item), ""] : []),
      "## 证据",
      "",
      ...(report.evidence || []).map((item) => "- " + (item.type || "file") + "：" + (item.summary || "") + "（" + (item.path || "") + "）"),
      "",
      "> 本地自评估不等于官方评分。"
    ];
    return lines.join("\n");
  }

  function renderLabReport(root, report) {
    const section = root.querySelector("[data-report-lab-section]");
    if (!section) return;
    const lab = report && report.lab;
    if (!lab || !lab.schema) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    setText(root, "[data-report-lab-headline]", lab.headline || "基线与本轮对比");
    setText(root, "[data-report-lab-summary]", lab.summary || "");
    const box = root.querySelector("[data-report-lab-comparison]");
    if (box) {
      box.innerHTML = "";
      const items = Array.isArray(lab.comparison) ? lab.comparison : [];
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "lab-report-empty";
        empty.textContent = "当前报告没有 baseline 对比数据。";
        box.appendChild(empty);
      } else {
        const table = document.createElement("table");
        table.className = "lab-table";
        const thead = document.createElement("thead");
        const head = document.createElement("tr");
        ["指标", "Baseline", "本轮", "变化"].forEach((label) => {
          const th = document.createElement("th");
          th.textContent = label;
          head.appendChild(th);
        });
        thead.appendChild(head);
        const tbody = document.createElement("tbody");
        const statusText = { improved: "改善", regressed: "退步", unchanged: "持平", changed: "变化" };
        items.forEach((item) => {
          const row = document.createElement("tr");
          const label = document.createElement("td");
          label.textContent = item.label || item.id || "—";
          const before = document.createElement("td");
          before.textContent = String(item.before ?? "—") + " " + (item.before_detail || "");
          const after = document.createElement("td");
          after.textContent = String(item.after ?? "—") + " " + (item.after_detail || "");
          const change = document.createElement("td");
          change.textContent = statusText[item.status] || item.status || "—";
          change.className = item.status === "improved" ? "is-pass" : item.status === "regressed" ? "is-fail" : "";
          row.append(label, before, after, change);
          tbody.appendChild(row);
        });
        table.append(thead, tbody);
        box.appendChild(table);
      }
    }
    fillList(root, "[data-report-lab-review]", lab.human_review, "暂无人工核验记录");
    fillList(root, "[data-report-lab-warnings]", lab.warnings, "没有额外警告");
    fillList(root, "[data-report-lab-next]", lab.next_actions, "暂无下一步建议");
    fillList(root, "[data-report-lab-files]", Object.entries(lab.files || {}).map(([key, value]) => key + " · " + value), "暂无报告文件清单");
  }

  function readReportFromHash() {
    const match = location.hash.match(/^#report=(.+)$/);
    if (!match) return null;
    try {
      const base64 = match[1].replace(/-/g, "+").replace(/_/g, "/");
      const padded = base64 + "=".repeat((4 - base64.length % 4) % 4);
      const binary = atob(padded);
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      const parsed = JSON.parse(new TextDecoder().decode(bytes));
      return validateHarnessReport(parsed).length === 0 ? parsed : null;
    } catch (error) {
      return null;
    }
  }

  async function initReportPage() {
    const root = document.querySelector("[data-lab-report]");
    if (!root) return;
    const hashReport = readReportFromHash();
    if (hashReport) {
      writeHarnessReport(hashReport);
      history.replaceState(null, "", location.pathname + location.search);
    }
    const fileInput = root.querySelector("[data-report-file]");
    const summary = incomingRunSummary();
    const importActions = root.querySelector("[data-report-import-actions]");
    const importTitle = root.querySelector("[data-report-import-title]");
    const importDesc = root.querySelector("[data-report-import-desc]");

    function updateImportChrome() {
      if (importActions) importActions.hidden = false;
      if (importTitle) importTitle.textContent = "导入本地 Harness 报告";
      if (importDesc) importDesc.textContent = "网站不会上传文件。report.json 或 lab-report.json 只在当前浏览器读取，并用于核验实验来源。";
    }

  function renderAiPresentation(root, ai) {
    const box = root.querySelector("[data-report-ai-presentation]");
    if (!box) return;
    box.innerHTML = "";
    const presentation = ai && ai.presentation;
    const make = (tag, className, text) => {
      const el = document.createElement(tag);
      if (className) el.className = className;
      if (text !== undefined && text !== null) el.textContent = String(text);
      return el;
    };
    if (!presentation) {
      const empty = make("div", "ai-presentation-empty");
      empty.appendChild(make("h3", "", "当前报告还是旧版 AI 数据结构"));
      empty.appendChild(make("p", "", "请回到本地 Harness 重新执行“生成自评”，再导入新的 report.json。下方技术细节仍可查看。"));
      box.appendChild(empty);
      return;
    }

    const hero = make("div", "ai-summary-hero is-" + (presentation.severity || "neutral"));
    hero.appendChild(make("span", "ai-summary-kicker", "一句话结论"));
    hero.appendChild(make("h3", "", presentation.headline || "本轮实验分析"));
    hero.appendChild(make("p", "", presentation.summary || "暂无摘要"));
    const badges = make("div", "ai-summary-badges");
    (presentation.badges || []).forEach((badge) => {
      const chip = make("span", "ai-summary-chip is-" + (badge.severity || "neutral"));
      chip.appendChild(make("small", "", badge.label || ""));
      chip.appendChild(make("strong", "", badge.value || "—"));
      badges.appendChild(chip);
    });
    hero.appendChild(badges);
    box.appendChild(hero);

    const findings = Array.isArray(presentation.findings) ? presentation.findings : [];
    if (findings.length) {
      const section = make("section", "ai-readable-section");
      section.appendChild(make("h3", "", "先看这些关键指标"));
      section.appendChild(make("p", "ai-readable-lead", "每一项都标出了实际值、参考标准和对驾驶体验的影响。"));
      const grid = make("div", "ai-finding-grid");
      findings.forEach((item) => {
        const card = make("article", "ai-finding-card is-" + (item.severity || "neutral"));
        const top = make("div", "ai-finding-top");
        top.appendChild(make("strong", "", item.title || item.id || "指标"));
        top.appendChild(make("span", "ai-status-pill", item.status || "—"));
        card.appendChild(top);
        const value = make("div", "ai-finding-value");
        value.appendChild(make("b", "", item.value || "—"));
        if (item.unit) value.appendChild(make("small", "", " " + item.unit));
        card.appendChild(value);
        card.appendChild(make("div", "ai-finding-threshold", "参考标准：" + (item.threshold || "—")));
        card.appendChild(make("p", "", item.explanation || "暂无解释"));
        card.appendChild(make("code", "ai-finding-source", item.source || ""));
        grid.appendChild(card);
      });
      section.appendChild(grid);
      box.appendChild(section);
    }

    const actions = Array.isArray(presentation.actions) ? presentation.actions : [];
    if (actions.length) {
      const section = make("section", "ai-readable-section");
      section.appendChild(make("h3", "", "下一步怎么做"));
      section.appendChild(make("p", "ai-readable-lead", "建议按顺序处理，每一步都说明原因和完成标准。"));
      const list = make("div", "ai-action-list");
      actions.forEach((action) => {
        const card = make("article", "ai-action-card");
        const head = make("div", "ai-action-head");
        head.appendChild(make("span", "ai-action-number", "0" + (action.priority || 1)));
        head.appendChild(make("h4", "", action.title || "下一步"));
        card.appendChild(head);
        card.appendChild(make("p", "", action.why || ""));
        const steps = Array.isArray(action.steps) ? action.steps : [];
        if (steps.length) {
          const ol = make("ol", "ai-action-steps");
          steps.forEach((step) => ol.appendChild(make("li", "", step)));
          card.appendChild(ol);
        }
        if (action.done_when) {
          const done = make("div", "ai-action-done");
          done.appendChild(make("strong", "", "完成标准："));
          done.appendChild(document.createTextNode(action.done_when));
          card.appendChild(done);
        }
        list.appendChild(card);
      });
      section.appendChild(list);
      box.appendChild(section);
    }

    const questions = Array.isArray(presentation.questions) ? presentation.questions : [];
    if (questions.length) {
      const section = make("section", "ai-readable-section ai-question-section");
      section.appendChild(make("h3", "", "需要你确认"));
      const ul = make("ul", "ai-question-list");
      questions.forEach((item) => ul.appendChild(make("li", "", item)));
      section.appendChild(ul);
      box.appendChild(section);
    }

    const glossary = Array.isArray(presentation.glossary) ? presentation.glossary : [];
    if (glossary.length) {
      const details = make("details", "ai-glossary");
      details.appendChild(make("summary", "", "参数名看不懂？展开术语表"));
      const grid = make("div", "ai-glossary-grid");
      glossary.forEach((item) => {
        const card = make("div", "ai-glossary-item");
        const name = make("div", "ai-glossary-name");
        name.appendChild(make("code", "", item.term || ""));
        name.appendChild(make("strong", "", item.label || ""));
        card.appendChild(name);
        card.appendChild(make("p", "", item.meaning || ""));
        card.appendChild(make("small", "", "单位：" + (item.unit || "—") + " · 参考：" + (item.reference || "—")));
        grid.appendChild(card);
      });
      details.appendChild(grid);
      box.appendChild(details);
    }
  }

    function render(noticeOverride, noticeKind) {
      const imported = readHarnessReport();
      const report = imported || emptyReportData();
      const meta = report.meta || {};
      const record = report.record || {};
      const metrics = report.metrics || {};
      const verify = report.verification || {};
      const score = report.score || {};
      const ai = report.ai || {};
      const isHarness = meta.source === "local-harness";
      const emptyRecord = record.channel_count === 0 || record.status === "empty" || String(meta.status || "").includes("empty");
      const isReal = isHarness && meta.mode === "real" && !emptyRecord;
      const badge = root.querySelector("[data-report-mode-badge]");
      const badgeText = meta.source === "empty" ? "等待导入" : isReal ? "本地自评产物" : isHarness ? (emptyRecord ? "Harness · 空 record" : "Harness " + (meta.mode || "报告")) : "报告";
      if (badge) {
        badge.textContent = badgeText;
        badge.className = "lab-source-badge " + (isReal ? "is-real" : "is-demo");
      }

      const defaultNotice = imported
        ? "已载入保存在当前浏览器中的本地 Harness 报告。"
        : summary
          ? "已收到本地运行摘要 " + summary.run + "。摘要不能替代原始报告，请导入对应的 report.json 核验。"
          : "尚未导入报告。选择 report.json 或从 Harness 点击“在网页中打开”。";
      setImportStatus(root, noticeOverride || defaultNotice, noticeKind || (isReal ? "is-ok" : "is-warn"));

      const intro = isReal
        ? "本页显示本地 Harness 自评产物。文件只保存在当前浏览器，网站不会上传文件。"
        : isHarness
          ? emptyRecord
            ? "本报告来自本地 Harness，但 record channels 为 0（状态：" + (meta.status || "empty") + "）。该报告不能作为有效驾驶指标，请先启动仿真场景并重新 record。"
            : "本页显示本地 Harness 报告，但报告模式为 " + (meta.mode || "未知") + "；请结合状态和 record 判断是否可用于正式结论。"
          : "尚未导入实验产物。完成本地 Harness 实验并导出 report.json 后，可在此导入真实指标、AI 建议和证据链。";
      setText(root, "[data-report-intro]", intro);
      setText(root, "[data-report-scenario]", meta.scenario || meta.task || "等待导入报告");
      setText(root, "[data-report-run-id]", meta.experiment_id || "—");
      setText(root, "[data-report-task]", (meta.scenario || meta.task || "—") + (meta.status ? " · " + meta.status : ""));
      setText(root, "[data-report-environment]", environmentLabel(report.environment));
      setText(root, "[data-report-created-at]", formatDateTime(meta.created_at));
      setText(root, "[data-report-record]", (record.channel_count ?? "—") + " channels · " + (record.message_count ?? "—") + " messages · " + (record.duration_sec ?? "—") + " s");
      setText(root, "[data-report-score-source]", score.source || "未运行评分");
      setText(root, "[data-report-ai-skills]", (Array.isArray(ai.skills) ? ai.skills : (ai.skill ? [ai.skill] : [])).join(", ") || "—");
      renderAiPresentation(root, ai);

      const lab = report.lab || {};
      const labBaseline = lab.baseline || {};
      const labCurrent = lab.current || {};
      const labBeforeMetrics = labBaseline.metrics || {};
      const labAfterMetrics = labCurrent.metrics || {};
      const scoreBeforeValue = numberOrNull(verify.score_before) ?? numberOrNull(labBaseline.score_value);
      const scoreValue = numberOrNull(score.value) ?? numberOrNull(verify.score_after) ?? numberOrNull(labCurrent.score_value);
      const scoreDisplay = scoreValue === null ? (score.passed_metrics || labCurrent.passed_metrics || "—") : formatNumber(scoreValue, 0);
      const scoreBeforeDisplay = scoreBeforeValue === null
        ? (labBaseline.passed_metrics || "—")
        : formatNumber(scoreBeforeValue, 0);
      setText(root, "[data-report-score-after]", scoreDisplay);
      setText(root, "[data-report-score-current]", scoreDisplay);
      setText(root, "[data-report-score-before]", scoreBeforeDisplay);
      setText(root, "[data-report-score-label]", scoreValue === null ? (score.passed_metrics ? "通过项" : "未评分") : (score.is_official ? "官方得分" : "综合自评"));
      setText(root, "[data-report-official]", score.value === null || score.value === undefined
        ? (score.passed_metrics ? "本地自评：通过 " + score.passed_metrics + " 项，不提供总分，不替代官方评分。" : "当前报告没有评分结果。")
        : score.is_official ? "官方评分。" : "本地自评估，不替代官方评分。");

      const bars = root.querySelector("[data-report-bars]");
      if (bars) {
        bars.innerHTML = "";
        const configs = [
          { label: "最小 TTC", unit: "s", beforeKeys: ["min_ttc", "ttc"], afterKeys: ["min_ttc", "ttc"], max: 3 },
          { label: "最大纵向加速度", unit: "m/s²", beforeKeys: ["max_lon_accel", "max_acceleration", "lon_accel"], afterKeys: ["max_lon_accel", "max_acceleration", "lon_accel"], max: 4 },
          { label: "最大 Jerk", unit: "m/s³", beforeKeys: ["max_jerk", "jerk"], afterKeys: ["max_jerk", "jerk"], max: 5 },
          { label: "急刹次数", unit: "次", beforeKeys: ["hard_brake"], afterKeys: ["hard_brake"], max: 3 }
        ];
        configs.forEach((item) => {
          const beforeValue = metricValueFrom([labBeforeMetrics, metrics], item.beforeKeys);
          const afterValue = metricValueFrom([labAfterMetrics, verify], item.afterKeys);
          const row = document.createElement("div");
          row.className = "lab-bar-row" + (beforeValue === null && afterValue === null ? " is-empty" : "");
          const name = document.createElement("span");
          name.textContent = item.label;
          const barGroup = document.createElement("div");
          barGroup.className = "lab-report-bars";
          [["before", beforeValue], ["after", afterValue]].forEach(([kind, value]) => {
            const bar = document.createElement("div");
            bar.className = "lab-bar " + kind;
            const fill = document.createElement("i");
            fill.style.width = value === null ? "0%" : Math.min(100, (Math.max(0, value) / item.max) * 100) + "%";
            bar.appendChild(fill);
            barGroup.appendChild(bar);
          });
          const value = document.createElement("span");
          value.textContent = beforeValue === null && afterValue === null ? "无数据" : formatNumber(beforeValue) + " → " + formatNumber(afterValue) + " " + item.unit;
          row.append(name, barGroup, value);
          bars.appendChild(row);
        });
      }
      setText(root, "[data-report-score-note]", isHarness
        ? "当前报告包含场景指标的 PASS/FAIL、得分和未通过帧数。"
        : "导入报告后显示场景指标的 PASS/FAIL、得分和未通过帧数。");
      setText(root, "[data-report-metrics-note]", isHarness
        ? "本区来自本地 Harness 报告；缺失指标显示为“—”，不会自动补造数据。"
        : "当前没有可用的真实指标。请先导入 Harness 报告。");
      renderScoreMetrics(root, score.metrics);
      renderLabReport(root, report);

      fillList(root, "[data-report-ai-facts]", ai.facts, "暂无 AI 事实");
      fillList(root, "[data-report-ai-hypotheses]", ai.hypotheses, "暂无 AI 推测");
      fillList(root, "[data-report-ai-suggestions]", ai.suggestions, "暂无 AI 建议");
      fillList(root, "[data-report-ai-source-refs]", ai.source_refs, "暂无引用");
      setText(root, "[data-report-ai-confirmed]", ai.student_confirmed === true ? "学生确认状态：已确认" : ai.student_confirmed === false ? "学生确认状态：未确认" : "报告未记录学生确认状态");
      renderEvidence(root, report.evidence);
      const errorValues = (report.errors || []).map((item) => typeof item === "string" ? item : (item.message || JSON.stringify(item)));
      fillList(root, "[data-report-errors]", errorValues, "无错误或阻塞");
      setText(root, "[data-report-conclusion]", reportConclusion(report));
      renderCapability(root, report.capability);

      const download = root.querySelector("[data-download-report]");
      if (download) {
        download.disabled = !isHarness;
        download.onclick = () => {
          if (!isHarness) return;
          const blob = new Blob([reportToMarkdown(report)], { type: "text/markdown;charset=utf-8" });
          const link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = (isHarness ? "apollo-claw-" + (meta.experiment_id || "report") : "apollo-lab-demo-report") + ".md";
          link.click();
          URL.revokeObjectURL(link.href);
        };
      }
    }

    if (fileInput) {
      fileInput.addEventListener("change", async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;
        try {
          if (file.size > 5 * 1024 * 1024) throw new Error("文件超过 5 MB，请确认选择的是 report.json");
          const parsed = JSON.parse(await file.text());
          const errors = validateHarnessReport(parsed);
          if (errors.length) throw new Error(errors.slice(0, 4).join("；"));
          writeHarnessReport(parsed);
          updateImportChrome();
          render("导入成功：已读取 " + file.name + "，数据只保存在当前浏览器。", "is-ok");
        } catch (error) {
          setImportStatus(root, "导入失败：" + error.message, "is-error");
        } finally {
          fileInput.value = "";
        }
      });
    }

    const cleanUrl = new URL(location.href);
    cleanUrl.searchParams.delete("mode");
    history.replaceState(null, "", cleanUrl.pathname + cleanUrl.search);
    updateImportChrome();
    render();
  }

  syncLocalPanelLinks();
  initLocalLauncher();
  initRunPage();
  initLabIndexSnapshot().catch((error) => { console.error(error); });
  initReportPage().catch((error) => { console.error(error); });
  window.addEventListener("storage", (event) => {
    if (event.key === harnessReportKey) initLabIndexSnapshot().catch((error) => { console.error(error); });
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) initLabIndexSnapshot().catch((error) => { console.error(error); });
  });
})();
