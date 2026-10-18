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
    if (meta.task && config.taskId && meta.task !== config.taskId) errors.push("报告任务 " + meta.task + " 与当前实验 " + config.taskId + " 不一致");
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
      "## 证据",
      "",
      ...(report.evidence || []).map((item) => "- " + (item.type || "file") + "：" + (item.summary || "") + "（" + (item.path || "") + "）"),
      "",
      "> 本地自评估不等于官方评分。"
    ];
    return lines.join("\n");
  }

  function initReportPage() {
    const root = document.querySelector("[data-lab-report]");
    if (!root) return;
    const fileInput = root.querySelector("[data-report-file]");
    const resetButton = root.querySelector("[data-report-reset]");
    const summary = incomingRunSummary();

    function render(noticeOverride, noticeKind) {
      const imported = readHarnessReport();
      const report = imported || demoReportData();
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
      const badgeText = isReal ? "真实 Harness 报告" : isHarness ? (emptyRecord ? "Harness · 空 record" : "Harness " + (meta.mode || "报告")) : "演示数据";
      if (badge) {
        badge.textContent = badgeText;
        badge.className = "lab-source-badge " + (isReal ? "is-real" : "is-demo");
      }

      const defaultNotice = imported
        ? "已载入保存在当前浏览器中的本地 Harness 报告。"
        : summary
          ? "已收到本地运行摘要 " + summary.run + "。摘要不能替代原始报告，请导入对应的 report.json 核验。"
          : "当前显示网站内置演示数据，不代表真实仿真结果。";
      setImportStatus(root, noticeOverride || defaultNotice, noticeKind || (isReal ? "is-ok" : "is-warn"));

      const intro = isReal
        ? "本页显示从本地 Harness 导入的真实 report.json。数据只保存在当前浏览器，网站不会上传文件。"
        : isHarness
          ? emptyRecord
            ? "本报告来自本地 Harness，但 record channels 为 0（状态：" + (meta.status || "empty") + "）。该报告不能作为有效驾驶指标，请先启动仿真场景并重新 record。"
            : "本页显示本地 Harness 报告，但报告模式为 " + (meta.mode || "未知") + "；请结合状态和 record 判断是否可用于正式结论。"
          : "当前展示网站内置演示数据。完成本地 Harness 实验并导出 report.json 后，可在此导入真实指标、AI 建议和证据链。";
      setText(root, "[data-report-intro]", intro);
      setText(root, "[data-report-scenario]", meta.scenario || meta.task || "人行道避让");
      setText(root, "[data-report-run-id]", meta.experiment_id || "—");
      setText(root, "[data-report-task]", (meta.scenario || meta.task || "—") + (meta.status ? " · " + meta.status : ""));
      setText(root, "[data-report-environment]", environmentLabel(report.environment));
      setText(root, "[data-report-created-at]", formatDateTime(meta.created_at));
      setText(root, "[data-report-record]", (record.channel_count ?? "—") + " channels · " + (record.message_count ?? "—") + " messages · " + (record.duration_sec ?? "—") + " s");
      setText(root, "[data-report-score-source]", score.source || "未运行评分");
      setText(root, "[data-report-ai-skills]", (ai.skills || []).join(", ") || "—");

      const scoreBefore = numberOrNull(verify.score_before);
      const scoreValue = numberOrNull(score.value) ?? numberOrNull(verify.score_after);
      const scoreDisplay = scoreValue === null ? (score.passed_metrics || "—") : formatNumber(scoreValue, 0);
      setText(root, "[data-report-score-after]", scoreDisplay);
      setText(root, "[data-report-score-current]", scoreDisplay);
      setText(root, "[data-report-score-before]", scoreBefore === null ? "—" : formatNumber(scoreBefore, 0));
      setText(root, "[data-report-score-label]", scoreValue === null ? (score.passed_metrics ? "通过项" : "未评分") : "场景得分");
      setText(root, "[data-report-official]", score.value === null || score.value === undefined
        ? (score.passed_metrics ? "本地自评：通过 " + score.passed_metrics + " 项，不提供总分，不替代官方评分。" : "当前报告没有评分结果。")
        : score.is_official ? "官方评分。" : "本地自评估，不替代官方评分。");

      const bars = root.querySelector("[data-report-bars]");
      if (bars) {
        bars.innerHTML = "";
        const configs = [
          { label: "最小 TTC", unit: "s", before: ["min_ttc", "ttc"], after: ["min_ttc", "ttc"], max: 3 },
          { label: "最大纵向加速度", unit: "m/s²", before: ["max_acceleration", "lon_accel"], after: ["max_acceleration", "lon_accel"], max: 4 },
          { label: "最大 Jerk", unit: "m/s³", before: ["max_jerk", "jerk"], after: ["max_jerk", "jerk"], max: 5 },
          { label: "急刹次数", unit: "次", before: ["hard_brake"], after: ["hard_brake"], max: 3 }
        ];
        configs.forEach((item) => {
          const beforeValue = metricValue(metrics, item.before);
          const afterValue = metricValue(verify, item.after);
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
      setText(root, "[data-report-metrics-note]", imported
        ? "本区来自导入的 Harness 报告；缺失指标显示为“—”，不会自动补造数据。"
        : "橙色表示优化前，绿色表示当前报告。当前为演示数据，不替代官方评测。");
      renderScoreMetrics(root, score.metrics);

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
        download.onclick = () => {
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
          render("导入成功：已读取 " + file.name + "，数据只保存在当前浏览器。", "is-ok");
        } catch (error) {
          setImportStatus(root, "导入失败：" + error.message, "is-error");
        } finally {
          fileInput.value = "";
        }
      });
    }

    if (resetButton) {
      resetButton.addEventListener("click", () => {
        localStorage.removeItem(harnessReportKey);
        render("已恢复网站内置演示数据。", "is-warn");
      });
    }

    render();
  }

  syncLocalPanelLinks();
  initRunPage();
  initReportPage();
})();
