const token = window.__APOLLO_CLAW_TOKEN__;
const state = { tasks: [], experiments: [], task: null, experiment: null, experimentId: "", report: null, doctor: null, runtime: null, chat: [], chatBusy: false, deepseekConfigured: false, jobId: "", pollTimer: null, actionTimer: null, actionStartedAt: 0, activeAction: "", simWindow: null, token: "" };
const TASK_VISUALS = {
  "speed-bump": "/assets/scenario-obstacle-stop-low.webp",
  crosswalk: "/assets/scenario-crosswalk-low.webp",
  "traffic-light": "/assets/scenario-obstacle-stop-low.webp",
  "stop-sign": "/assets/scenario-obstacle-stop-low.webp",
  "obstacle-stop": "/assets/scenario-obstacle-stop-low.webp",
  "dynamic-follow": "/assets/scenario-obstacle-stop-low.webp",
  "empty-crosswalk-slow": "/assets/scenario-crosswalk-low.webp",
  "traffic-light-slow": "/assets/scenario-obstacle-stop-low.webp",
  "valet-parking": "/assets/hero-planning-lab-low.webp",
};
const $ = (id) => document.getElementById(id);
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }

async function api(path, options = {}) {
  const opts = { ...options, headers: { ...(options.headers || {}) } };
  if (opts.body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  if (opts.method === "POST") opts.headers["X-Apollo-Claw-Token"] = state.token || token;
  let response = await fetch(path, opts);
  if (response.status === 403 && path !== "/api/session") {
    const session = await fetch("/api/session").then((item) => item.json());
    state.token = session.token || "";
    opts.headers["X-Apollo-Claw-Token"] = state.token;
    response = await fetch(path, opts);
  }
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function setPill(id, text, kind = "") {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.className = "pill" + (kind ? " " + kind : "");
}

function showToast(message, kind = "") {
  const toast = $("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = "toast is-visible" + (kind ? " is-" + kind : "");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.className = "toast" + (kind ? " is-" + kind : ""); }, 3600);
}

function setWorkflowStatus(text, kind = "") {
  const box = $("workflow-status");
  if (!box) return;
  box.textContent = text;
  box.className = "workflow-status" + (kind ? " is-" + kind : "");
}

function actionLabel(action) {
  return ({ doctor: "检查环境", "start-sim": "启动仿真", "stop-sim": "退出仿真", record: "开始录制", "record-pause": "暂停录制", "record-resume": "继续录制", "record-stop": "结束录制", report: "生成报告", selfeval: "生成自评", export: "导出", explain: "开始诊断" })[action] || "执行中";
}

function updateActionElapsed() {
  if (!state.activeAction) return;
  const button = document.querySelector(`[data-action="${state.activeAction}"]`);
  if (!button) return;
  const elapsed = Math.max(0, Math.floor((Date.now() - state.actionStartedAt) / 1000));
  const prefix = state.activeAction === "record" ? "启动录制" : state.activeAction === "start-sim" ? "启动仿真" : state.activeAction === "stop-sim" ? "退出仿真" : "处理中";
  button.textContent = `${prefix} ${elapsed}s`;
  setWorkflowStatus(state.activeAction === "start-sim"
    ? `正在启动 WSL、Apollo 容器和 DreamView，已等待 ${elapsed}s。首次启动可能需要一到数分钟。`
    : state.activeAction === "stop-sim"
      ? `正在停止 DreamView、Apollo 容器和守护进程，并关闭 WSL，已等待 ${elapsed}s。`
      : state.activeAction === "record"
      ? `正在启动录制会话，已等待 ${elapsed}s。启动后可使用暂停、继续和结束按钮。`
      : `${actionLabel(state.activeAction)}中，已等待 ${elapsed}s。`, "running");
}

function setActionBusy(action, busy) {
  document.body.classList.toggle("is-operation-running", Boolean(busy));
  document.querySelectorAll("[data-action]").forEach((button) => {
    if (busy) {
      button.disabled = true;
      if (button.dataset.action === action) {
        button.dataset.originalLabel = button.dataset.originalLabel || button.textContent;
        button.classList.add("is-busy");
        button.setAttribute("aria-busy", "true");
        button.textContent = action === "record" ? "录制中 0s" : "处理中 0s";
      }
    } else {
      button.disabled = false;
      button.classList.remove("is-busy");
      button.removeAttribute("aria-busy");
      if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel;
    }
  });
  if (busy) {
    state.activeAction = action;
    state.actionStartedAt = Date.now();
    clearInterval(state.actionTimer);
    state.actionTimer = setInterval(updateActionElapsed, 1000);
    updateActionElapsed();
  } else {
    state.activeAction = "";
    clearInterval(state.actionTimer);
    state.actionTimer = null;
  }
}

function setConsoleSummary(text, kind = "") {
  const box = $("console-summary");
  if (!box) return;
  box.textContent = text;
  box.className = "console-summary" + (kind ? " is-" + kind : "");
}

function setConsoleDetails(raw) {
  const pre = $("console");
  const details = $("console-details");
  if (pre) pre.textContent = raw || "等待操作...";
  if (details) details.hidden = !String(raw || "").trim();
}

function jobHumanSummary(job) {
  const raw = [job.stdout, job.stderr].filter(Boolean).join("\n");
  const dryRun = /dry-run/i.test(raw);
  const failed = job.status === "failed";
  if (job.status === "running") {
    return { text: `${actionLabel(job.action)}正在运行，请保持页面和仿真环境开启。`, kind: "running" };
  }
  if (failed) {
    return { text: `${actionLabel(job.action)}失败。请展开“查看技术日志”定位原因，或先检查环境/场景状态。`, kind: "error" };
  }
  if (job.action === "start-sim") {
    return { text: "Linux、Apollo 容器和 DreamView 已启动，正在打开仿真页面。", kind: "success" };
  }
  if (job.action === "stop-sim") {
    return { text: "仿真已退出：DreamView、Apollo 容器、录制与守护进程均已停止，WSL 已关闭。", kind: "success" };
  }
  if (job.action === "record") {
    return dryRun
      ? { text: "这次只是演练：生成了录制命令，但没有真正进入 Apollo 容器。勾选“实际运行”后再点“开始录制”。", kind: "warn" }
      : { text: "录制会话已开始。需要时可暂停或继续；完成后点击“结束并保存”，再生成 channel 报告。", kind: "success" };
  }
  if (job.action === "record-pause") {
    return { text: "录制已暂停；仿真仍可继续运行，点击“继续录制”后会从同一录制会话恢复。", kind: "warn" };
  }
  if (job.action === "record-resume") {
    return { text: "录制已继续。需要结束时点击“结束并保存”。", kind: "success" };
  }
  if (job.action === "record-stop") {
    const match = raw.match(/录制\s+(\d+)\s+秒，(\d+)\s+个文件/);
    return { text: match ? `录制已保存：${match[1]} 秒，${match[2]} 个文件。下一步生成 channel 报告。` : "录制已结束并保存。下一步生成 channel 报告。", kind: "success" };
  }
  if (job.action === "report") {
    return { text: "channel 报告已生成：CSV、PNG 和 Markdown 已准备好。下一步点击“生成自评”。", kind: "success" };
  }
  if (job.action === "selfeval") {
    return { text: "自评报告已生成。下方会出现报告摘要和 report.json / selfeval.md 等文件链接。", kind: "success" };
  }
  if (job.action === "export") {
    return { text: "报告文件已导出：report.json 和 report.md 已准备好。", kind: "success" };
  }
  if (job.action === "doctor") {
    return { text: "环境检查完成：已区分 Linux、Docker、Apollo 容器和 DreamView 状态。", kind: "success" };
  }
  if (job.action === "explain") {
    return { text: "AI 诊断完成，结果已显示在上方的“DeepSeek 诊断”区域。", kind: "success" };
  }
  return { text: `${actionLabel(job.action)}完成。`, kind: "success" };
}

function renderTasks() {
  const list = $("task-list");
  list.innerHTML = "";
  state.tasks.forEach((task, index) => {
    const button = document.createElement("button");
    button.className = "task" + (state.task && state.task.id === task.id ? " active" : "");
    button.type = "button";
    const strong = document.createElement("strong");
    strong.textContent = task.title || task.id;
    const small = document.createElement("small");
    const number = task.number || `实验${index + 1}`;
    const status = task.status === "planned" ? "待接入" : task.status === "open" ? "可开始" : (task.status || "可用");
    small.textContent = `${number} · ${status}`;
    button.append(strong, small);
    button.addEventListener("click", () => selectTask(task));
    list.appendChild(button);
  });
}

function selectTask(task) {
  state.task = task;
  state.experimentId = "";
  state.experiment = null;
  document.body.dataset.task = task.id || "crosswalk";
  const taskImage = $("task-visual-image");
  if (taskImage) {
    taskImage.src = TASK_VISUALS[task.id] || TASK_VISUALS.crosswalk;
    taskImage.alt = (task.title || "实验任务") + " 场景";
  }
  const taskLabel = [task.number, task.title || task.id].filter(Boolean).join(" · ");
  if ($("task-visual-title")) $("task-visual-title").textContent = taskLabel || "实验任务";
  $("task-title").textContent = taskLabel || "城市道路自动驾驶综合仿真实验";
  $("task-desc").textContent = task.description || "按流程完成环境检查、场景运行、record、报告和复盘。";
  setPill("active-task", taskLabel || task.id, "ok");
  renderTasks();
  renderExperiments();
  renderExperiment();
  state.report = null;
  state.chat = [];
  renderChat();
  updateReportContext();
  updateConfigStatus();
  renderReport(null);
}

function renderExperiments() {
  const select = $("experiment-select");
  select.innerHTML = '<option value="">新建实验</option>';
  state.experiments.forEach((exp) => {
    const option = document.createElement("option");
    option.value = exp.experiment_id;
    option.textContent = `${exp.experiment_id} · ${exp.status || "created"}`;
    select.appendChild(option);
  });
  select.value = state.experimentId || "";
}

async function loadExperiments() {
  const data = await api("/api/experiments");
  state.experiments = data.experiments || [];
  renderExperiments();
}

async function fetchCurrentReport(id) {
  try {
    return await api(`/api/experiments/${encodeURIComponent(id)}/files/lab-report.json`);
  } catch {
    return await api(`/api/experiments/${encodeURIComponent(id)}/report`);
  }
}

async function fetchDoctor(id) {
  try {
    return await api(`/api/experiments/${encodeURIComponent(id)}/files/doctor.json`);
  } catch {
    return null;
  }
}

async function loadExperiment(id) {
  if (!id) {
    state.experiment = null;
    state.experimentId = "";
    state.report = null;
    state.doctor = null;
    state.chat = [];
    renderExperiment();
    renderReport(null);
    renderChat();
    updateReportContext();
    updateConfigStatus();
    return;
  }
  state.experimentId = id;
  state.experiment = await api(`/api/experiments/${encodeURIComponent(id)}`);
  renderExperiments();
  renderExperiment();
  state.report = null;
  state.doctor = null;
  try {
    state.report = await fetchCurrentReport(id);
    renderReport(state.report);
  } catch {
    renderReport(null);
  }
  state.doctor = await fetchDoctor(id);
  renderEnvironmentCheck();
  renderRecordingControls();
  loadChatHistory();
  updateReportContext();
  updateConfigStatus();
  renderChat();
}

function updateConfigStatus() {
  const exp = state.experiment || {};
  const meta = exp.meta || {};
  const record = exp.record || {};
  const status = meta.status || "created";
  const hasRecord = Boolean(record.path || record.status || record.channel_count);
  const runtime = runtimeSnapshot() || state.doctor || {};
  const dreamview = runtime.dreamview || {};
  const simulation = runtime.simulation || {};
  const dreamviewText = dreamview.ok === true ? "已连接" : runtime ? "未连接" : "未检查";
  const recordText = isRecordActive(record) ? (recordPhase(record) === "paused" ? "已暂停" : "录制中") : hasRecord ? (record.status || "已记录") : "未录制";
  const reportText = state.report ? "已生成" : "未生成";
  const experimentLabel = state.experimentId
    ? (meta.scenario || meta.task || "已选择") + " · " + state.experimentId
    : "未选择";
  if ($("config-harness")) $("config-harness").textContent = "本地在线";
  if ($("config-dreamview")) $("config-dreamview").textContent = dreamviewText;
  if ($("config-record")) $("config-record").textContent = recordText;
  if ($("config-report")) $("config-report").textContent = reportText;
  if ($("config-deepseek")) $("config-deepseek").textContent = state.deepseekConfigured ? "已配置" : "规则降级";
  if ($("config-experiment")) $("config-experiment").textContent = experimentLabel;
  if ($("config-hint")) {
    $("config-hint").textContent = !state.experimentId
      ? "选择实验后显示运行状态。"
      : (!runtime && status === "environment_warning") || (runtime && !simulation.started)
        ? "当前仿真环境未就绪：点击“去启动”，确认后会启动 WSL、Apollo 容器和 DreamView。"
        : !hasRecord
          ? "当前实验还没有 record。启动场景后，勾选“实际运行”再录制。"
          : !state.report
            ? "已检测到 record，下一步生成 channel 报告和自评报告。"
            : "当前实验已完成环境检查和报告生成，可以继续查看报告或问答。";
  }
}

function chatStorageKey() {
  return "apollo-claw-report-chat-v1:" + (state.experimentId || "none");
}

function loadChatHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(chatStorageKey()) || "[]");
    state.chat = Array.isArray(parsed)
      ? parsed.filter((item) => item && (item.role === "user" || item.role === "assistant") && item.content).slice(-30)
      : [];
  } catch {
    state.chat = [];
  }
}

function saveChatHistory() {
  try {
    localStorage.setItem(chatStorageKey(), JSON.stringify(state.chat.slice(-30)));
  } catch {}
}

function updateReportContext() {
  const box = $("ai-report-context");
  if (!box) return;
  if (!state.experimentId) {
    box.textContent = "选择实验后，可围绕当前报告向 DeepSeek 提问。";
    return;
  }
  if (!state.report) {
    box.textContent = "当前实验还没有可问答的报告，请先生成自评或导出 report.json。";
    return;
  }
  const meta = state.report.meta || {};
  const score = state.report.score || {};
  const kind = state.report.lab ? "整合报告" : "基础报告";
  box.textContent = `当前报告：${meta.experiment_id || state.experimentId} · 自评 ${score.passed_metrics || "—"} · ${kind}`;
}

function appendChatLines(row, title, values) {
  if (!Array.isArray(values) || !values.length) return;
  const details = document.createElement("details");
  details.className = "chat-evidence";
  const summary = document.createElement("summary");
  summary.textContent = title;
  const list = document.createElement("ul");
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = String(value);
    list.appendChild(item);
  });
  details.append(summary, list);
  row.appendChild(details);
}

function renderChat() {
  const box = $("chat-view");
  if (!box) return;
  box.innerHTML = "";
  const send = $("chat-send");
  if (send) {
    send.disabled = state.chatBusy || !state.report;
    send.textContent = state.chatBusy ? "回答中..." : "发送";
  }
  if (!state.experimentId) {
    box.textContent = "先选择一个实验，再围绕该实验的报告提问。";
    return;
  }
  if (!state.report) {
    box.textContent = "当前实验还没有报告。完成自评并导出报告后，这里会显示可追问的报告内容。";
    return;
  }
  if (!state.chat.length) {
    const empty = document.createElement("div");
    empty.className = "chat-empty";
    empty.textContent = "报告已加载。可以问：为什么没通过？和基线相比改善了吗？下一轮先改什么？";
    box.appendChild(empty);
  }
  state.chat.forEach((message) => {
    const row = document.createElement("article");
    row.className = "chat-message " + (message.role === "user" ? "is-user" : "is-assistant");
    if (message.error) row.classList.add("is-error");
    const meta = document.createElement("div");
    meta.className = "chat-meta";
    meta.textContent = message.role === "user"
      ? "你"
      : "Apollo Claw" + (message.mode ? " · " + (message.mode === "deepseek" ? "DeepSeek" : "规则回答") : "");
    const text = document.createElement("div");
    text.className = "chat-text";
    text.textContent = message.content || "";
    row.append(meta, text);
    appendChatLines(row, "报告证据", message.evidence);
    appendChatLines(row, "下一步", message.next_steps);
    if (message.note) {
      const note = document.createElement("div");
      note.className = "chat-note";
      note.textContent = message.note;
      row.appendChild(note);
    }
    box.appendChild(row);
  });
  if (state.chatBusy) {
    const waiting = document.createElement("div");
    waiting.className = "chat-waiting";
    waiting.textContent = "正在读取当前报告并组织回答...";
    box.appendChild(waiting);
  }
  box.scrollTop = box.scrollHeight;
}

async function askReport(question) {
  const q = String(question || "").trim();
  if (!q) return;
  if (!state.experimentId || !state.report) {
    showToast("请先选择一份已有报告。", "error");
    return;
  }
  if (state.chatBusy) return;
  const history = state.chat
    .filter((item) => item && (item.role === "user" || item.role === "assistant") && item.content)
    .slice(-8)
    .map((item) => ({ role: item.role, content: item.content }));
  state.chat.push({ role: "user", content: q });
  saveChatHistory();
  state.chatBusy = true;
  renderChat();
  try {
    const data = await api(`/api/experiments/${encodeURIComponent(state.experimentId)}/ask`, {
      method: "POST",
      body: { question: q, history },
    });
    state.chat.push({
      role: "assistant",
      content: data.answer || "报告中没有足够证据回答这个问题。",
      evidence: Array.isArray(data.evidence) ? data.evidence : [],
      next_steps: Array.isArray(data.next_steps) ? data.next_steps : [],
      mode: data.mode || "fallback",
      note: data.note || "",
    });
    showToast(data.mode === "deepseek" ? "DeepSeek 已根据当前报告回答。" : "DeepSeek 未配置，已使用报告规则回答。", data.mode === "deepseek" ? "success" : "warn");
    setWorkflowStatus("报告问答完成。", "success");
  } catch (error) {
    state.chat.push({ role: "assistant", content: "回答失败：" + error.message, error: true });
    showToast("报告问答失败：" + error.message, "error");
  } finally {
    state.chatBusy = false;
    saveChatHistory();
    renderChat();
  }
}

function initChat() {
  const form = $("chat-form");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const input = $("ai-question");
      if (!input) return;
      const question = input.value;
      input.value = "";
      askReport(question);
    });
  }
  document.querySelectorAll("[data-chat-prompt]").forEach((button) => {
    button.addEventListener("click", () => askReport(button.dataset.chatPrompt || ""));
  });
  const input = $("ai-question");
  if (input) {
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && form) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
  }
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return String(minutes).padStart(2, "0") + ":" + String(rest).padStart(2, "0");
}

function recordPhase(record) {
  return (record && record.session && record.session.phase) || (record && record.status) || "";
}

function isRecordActive(record) {
  return Boolean(record?.session?.active) && ["recording", "paused"].includes(recordPhase(record));
}

function recordElapsed(record) {
  let elapsed = Number(record?.elapsed_sec || 0);
  if (recordPhase(record) === "recording" && record?.session?.resumed_at) {
    const resumed = new Date(record.session.resumed_at).getTime();
    if (Number.isFinite(resumed)) elapsed += Math.max(0, (Date.now() - resumed) / 1000);
  }
  return Math.floor(elapsed);
}

function renderRecordingControls() {
  const record = state.experiment?.record || {};
  const active = isRecordActive(record);
  document.body.classList.toggle("is-recording", active && recordPhase(record) === "recording");
  const startControls = document.querySelector(".record-start-controls");
  const bar = $("record-session-bar");
  if (startControls) startControls.hidden = active;
  if (bar) bar.hidden = !active;
  if ($("execute")) $("execute").disabled = active;
  if (!active) return;
  const phase = recordPhase(record);
  if ($("record-session-state")) {
    $("record-session-state").textContent = phase === "paused"
      ? "已暂停 · 等待手动继续"
      : "录制中 · 手动结束";
  }
  if ($("record-session-time")) $("record-session-time").textContent = formatDuration(recordElapsed(record));
  const pause = document.querySelector('[data-action="record-pause"]');
  const resume = document.querySelector('[data-action="record-resume"]');
  if (pause) pause.hidden = phase !== "recording";
  if (resume) resume.hidden = phase !== "paused";
}

function runtimeSnapshot() {
  if (state.runtime) return state.runtime;
  const doctor = state.doctor || {};
  if (doctor.linux || doctor.docker || doctor.apollo || doctor.dreamview) return doctor;
  return null;
}

function renderEnvironmentCheck() {
  const box = $("env-check-result");
  if (!box) return;
  const runtime = runtimeSnapshot();
  if (!runtime) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const linux = runtime.linux || {};
  const docker = runtime.docker || {};
  const apollo = runtime.apollo || {};
  const dreamview = runtime.dreamview || {};
  const simulation = runtime.simulation || {};
  const dockerDetail = docker.started ? `Engine ${docker.version || "已启动"}` : linux.running ? "Docker 服务未就绪" : "Linux 未启动";
  const apolloDetail = apollo.started ? `${apollo.container || "容器"} · running` : linux.running ? `${apollo.container || "容器"} · ${apollo.state || "stopped"}` : "Linux 未启动，容器未检查";
  const rows = [
    ["Linux", Boolean(linux.running), linux.running ? `${linux.distro || "WSL"} · ${linux.kernel || "运行中"}` : "未启动"],
    ["Docker", Boolean(docker.started), dockerDetail],
    ["Apollo", Boolean(apollo.started), apolloDetail],
    ["DreamView", Boolean(dreamview.ok), dreamview.ok ? (dreamview.url || "已连接") : "未连接"],
  ];
  box.hidden = false;
  box.innerHTML = `<div class="env-check-head"><div><span class="eyebrow">RUNTIME CHECK</span><strong>${simulation.started ? "仿真环境已就绪" : "仿真环境未就绪"}</strong></div><span class="pill ${simulation.started ? "ok" : "bad"}">${simulation.started ? "READY" : "WARN"}</span></div><div class="env-check-grid">${rows.map(([name, ok, detail]) => `<div class="env-check-row ${ok ? "is-ok" : "is-warn"}"><span class="env-dot"></span><b>${esc(name)}</b><small>${esc(detail)}</small></div>`).join("")}</div><p class="env-check-summary">${esc(simulation.summary || "尚未完成环境检查")}</p>`;
}

async function loadRuntime() {
  try {
    state.runtime = await api("/api/runtime");
    renderEnvironmentCheck();
    updateConfigStatus();
  } catch {
    state.runtime = null;
  }
}

async function refreshActiveRecord() {
  if (state.recordRefreshing || state.jobId || !state.experimentId) return;
  if (!isRecordActive(state.experiment?.record || {})) return;
  state.recordRefreshing = true;
  try {
    state.experiment = await api(`/api/experiments/${encodeURIComponent(state.experimentId)}`);
    renderExperiment();
    renderRecordingControls();
    updateConfigStatus();
  } catch {
    // A transient refresh failure should not interrupt the recording session.
  } finally {
    state.recordRefreshing = false;
  }
}

function confirmSimulationAction(action) {
  const dialog = $("confirm-dialog");
  const stopping = action === "stop-sim";
  const title = stopping ? "确认退出仿真？" : "确认启动仿真？";
  const message = stopping
    ? "将停止 DreamView、Apollo 容器、录制与守护进程，并执行 wsl --shutdown。未结束的录制会先尝试保存。"
    : "Harness 将进入本地 WSL，启动 Apollo 容器和 DreamView。该操作可能需要一到数分钟。";
  if ($("confirm-title")) $("confirm-title").textContent = title;
  if ($("confirm-message")) $("confirm-message").textContent = message;
  if ($("confirm-ok")) $("confirm-ok").textContent = stopping ? "确认退出" : "确认启动";
  if (!dialog || typeof dialog.showModal !== "function") {
    return Promise.resolve(window.confirm(message));
  }
  return new Promise((resolve) => {
    const onClose = () => resolve(dialog.returnValue === "confirm");
    dialog.addEventListener("close", onClose, { once: true });
    dialog.returnValue = "cancel";
    dialog.showModal();
  });
}

function openSimulationPlaceholder() {
  try {
    state.simWindow = window.open("about:blank", "_blank");
    if (state.simWindow) {
      state.simWindow.document.title = "Apollo 仿真启动中";
      state.simWindow.document.body.innerHTML = '<main style="font-family:system-ui;background:#07111c;color:#ecf5fc;min-height:100vh;display:grid;place-items:center"><div style="text-align:center"><h2>正在启动 Apollo 仿真</h2><p style="color:#8ea6be">请等待 Linux、容器与 DreamView 就绪，此页会自动跳转。</p></div></main>';
    }
  } catch {
    state.simWindow = null;
  }
}
function renderExperiment() {
  const box = $("experiment-summary");
  if (!state.experiment) {
    box.textContent = "尚无实验记录。点击“检查环境”或“开始录制”会自动创建。";
    renderRecordingControls();
    return;
  }
  const exp = state.experiment;
  const record = exp.record || {};
  const status = exp.meta?.status || "created";
  const phase = recordPhase(record);
  const active = isRecordActive(record);
  const statusLabels = {
    environment_warning: "环境检查有警告",
    created: "已创建",
    recording: "录制中",
    recording_paused: "录制已暂停",
    recorded: "已录制",
    record_failed: "录制失败",
    evaluated: "已完成评分",
    complete: "已完成"
  };
  const statusText = statusLabels[status] || status;
  const hasRecord = Boolean(record.path || record.channel_count || ["recorded", "dry-run", "failed"].includes(record.status));
  const recordStatus = active ? (phase === "paused" ? "已暂停" : "录制中") : (record.status || (hasRecord ? "已记录" : "未录制"));
  const channelText = record.channel_count ?? (hasRecord ? "—" : "未录制");
  const sizeText = record.size_bytes ?? (hasRecord ? "—" : "未录制");
  const recordText = active
    ? `${formatDuration(recordElapsed(record))} · ${record.file_count ?? 0} 个文件`
    : hasRecord ? channelText + " channels · " + sizeText + " bytes" : "未录制";
  const recordHint = active
    ? (phase === "paused"
      ? "录制已暂停，仿真仍在运行。点击“继续录制”恢复，或“结束并保存”完成本轮。"
      : "正在使用原生 cyber_recorder 写入。暂停不会停止仿真，只停止记录 channel 消息。")
    : !hasRecord
      ? "当前实验还没有 record。请先启动仿真，再勾选“实际运行”开始录制。"
      : record.status === "dry-run"
        ? "本次只生成了录制命令，没有真正写入 Apollo 记录。"
        : "";
  box.innerHTML = `<strong>${esc(statusText)}</strong><div>实验：${esc(exp.meta?.scenario || exp.meta?.task || "-")}</div><div>record：${esc(recordText)}</div><div>记录状态：${esc(recordStatus)}</div>${recordHint ? `<div class="summary-note">${esc(recordHint)}</div>` : ""}`;
  if ($("metric-status")) $("metric-status").textContent = statusText;
  if ($("metric-channels")) $("metric-channels").textContent = active ? "写入中" : hasRecord ? (record.channel_count ?? "—") : "未录制";
  renderRecordingControls();
}

function renderAI(ai) {
  const box = $("ai-view");
  if (!ai || Object.keys(ai).length === 0) {
    box.textContent = "选择实验后，可让 DeepSeek 解释当前证据；未配置 Key 时自动使用规则降级。";
    return;
  }
  box.innerHTML = "";
  const mode = document.createElement("div");
  mode.className = "summary";
  mode.innerHTML = `<strong>诊断模式：${esc(ai.mode || "-")}</strong><div>技能：${esc(ai.skill || "-")}</div>${ai.note ? `<div>${esc(ai.note)}</div>` : ""}`;
  box.appendChild(mode);
  const sections = [["事实", ai.facts], ["推测", ai.hypotheses], ["建议", ai.suggestions], ["引用", ai.source_refs]];
  sections.forEach(([title, values]) => {
    const card = document.createElement("div");
    card.className = "summary";
    const strong = document.createElement("strong"); strong.textContent = title; card.appendChild(strong);
    const list = document.createElement("div"); list.className = "ai-list";
    if ((values || []).length) {
      values.forEach((value) => { const row = document.createElement("div"); row.textContent = value; list.appendChild(row); });
    } else {
      const row = document.createElement("div"); row.textContent = "暂无"; list.appendChild(row);
    }
    card.appendChild(list); box.appendChild(card);
  });
}

function setDeepSeekStatus(configured, masked = "") {
  state.deepseekConfigured = Boolean(configured);
  const text = configured ? `DeepSeek 已配置${masked ? " · " + masked : ""}` : "规则降级模式";
  setPill("deepseek-config-status", text, configured ? "ok" : "");
  setPill("deepseek-status", text, configured ? "ok" : "");
  if ($("deepseek-side-status")) $("deepseek-side-status").textContent = configured ? "已配置" : "规则降级";
  updateConfigStatus();
}

async function loadDeepSeekSettings() {
  try {
    const data = await api("/api/settings/deepseek");
    if ($("deepseek-base")) $("deepseek-base").value = data.base_url || "";
    if ($("deepseek-model")) $("deepseek-model").value = data.model || "";
    setDeepSeekStatus(Boolean(data.configured), data.masked_key || "");
  } catch (error) {
    if ($("deepseek-message")) $("deepseek-message").textContent = `读取 DeepSeek 配置失败：${error.message}`;
  }
}

function setSettingsMessage(text, kind = "") {
  const box = $("deepseek-message");
  box.textContent = text;
  box.className = "settings-message" + (kind ? " " + kind : "");
}

async function saveDeepSeekSettings() {
  try {
    setSettingsMessage("保存中...");
    const body = {
      api_key: $("deepseek-key").value.trim(),
      base_url: $("deepseek-base").value.trim(),
      model: $("deepseek-model").value.trim(),
    };
    const data = await api("/api/settings/deepseek", { method: "POST", body });
    $("deepseek-key").value = "";
    setDeepSeekStatus(Boolean(data.configured), data.masked_key || "");
    setSettingsMessage("配置已保存。下一次 AI 诊断会使用新配置。", "ok");
  } catch (error) {
    setSettingsMessage(`保存失败：${error.message}`, "bad");
  }
}

async function testDeepSeekConnection() {
  try {
    setSettingsMessage("正在保存并测试 DeepSeek 连接...");
    const saved = await api("/api/settings/deepseek", { method: "POST", body: {
      api_key: $("deepseek-key").value.trim(),
      base_url: $("deepseek-base").value.trim(),
      model: $("deepseek-model").value.trim(),
    }});
    $("deepseek-key").value = "";
    setDeepSeekStatus(Boolean(saved.configured), saved.masked_key || "");
    if (!saved.configured) {
      setSettingsMessage("请先填写 API Key 并保存，再测试连接。", "bad");
      return;
    }
    const data = await api("/api/settings/deepseek/test", { method: "POST", body: {} });
    setSettingsMessage(`连接成功：${data.model || "deepseek"} 返回 ${data.response || "OK"}`, "ok");
  } catch (error) {
    setSettingsMessage(`连接失败：${error.message}`, "bad");
  }
}

async function clearDeepSeekKey() {
  try {
    const data = await api("/api/settings/deepseek/clear", { method: "POST", body: {} });
    setDeepSeekStatus(Boolean(data.configured), data.masked_key || "");
    setSettingsMessage("API Key 已清除。后续诊断会使用规则降级模式。", "ok");
  } catch (error) {
    setSettingsMessage(`清除失败：${error.message}`, "bad");
  }
}

function renderReportFiles(report) {
  const box = $("report-files");
  if (!box) return;
  box.innerHTML = "";
  const experimentId = state.experimentId || report?.meta?.experiment_id;
  if (!report || !experimentId) return;
  const base = location.origin + "/api/experiments/" + encodeURIComponent(experimentId) + "/files/";
  const heading = document.createElement("div");
  heading.className = "report-files-head";
  heading.innerHTML = "<span class='eyebrow'>ARTIFACTS</span><strong>报告文件与地址</strong>";
  const folderButton = document.createElement("button");
  folderButton.type = "button";
  folderButton.className = "report-folder-button";
  folderButton.textContent = "打开本机报告目录";
  folderButton.addEventListener("click", async () => {
    folderButton.disabled = true;
    try {
      const data = await api(`/api/experiments/${encodeURIComponent(experimentId)}/open-folder`, { method: "POST", body: {} });
      showToast("已打开本机报告目录：" + (data.path || ""), "success");
    } catch (error) {
      showToast("打开报告目录失败：" + error.message, "error");
    } finally {
      folderButton.disabled = false;
    }
  });
  heading.appendChild(folderButton);
  box.appendChild(heading);
  const files = [
    ["report.json", "原始报告 JSON", "report.json"],
    ["report.md", "可读报告 Markdown", "report.md"],
    ["selfeval.md", "自评报告", "selfeval.md"],
    ["doctor.json", "环境检查结果", "doctor.json"]
  ];
  if (report.lab && report.lab.schema) files.splice(2, 0, ["lab-report.json", "网站整合报告 JSON", "lab-report.json"]);
  files.forEach(([name, label, file]) => {
    const row = document.createElement("div");
    row.className = "report-file-row";
    const copy = document.createElement("div");
    copy.className = "report-file-copy";
    const title = document.createElement("b");
    title.textContent = label + " · " + name;
    const address = document.createElement("code");
    address.textContent = base + encodeURIComponent(file);
    copy.append(title, address);
    const link = document.createElement("a");
    link.href = base + encodeURIComponent(file);
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "打开";
    row.append(copy, link);
    box.appendChild(row);
  });
  if ((report.evidence || []).length) {
    const evidenceHead = document.createElement("div");
    evidenceHead.className = "report-files-head is-secondary";
    evidenceHead.innerHTML = "<span class='eyebrow'>EVIDENCE</span><strong>证据路径</strong>";
    box.appendChild(evidenceHead);
    report.evidence.forEach((item) => {
      const row = document.createElement("div");
      row.className = "report-evidence-row";
      const kind = document.createElement("b");
      kind.textContent = item.type || "file";
      const path = document.createElement("code");
      path.textContent = item.path || "";
      const summary = document.createElement("small");
      summary.textContent = item.summary || "";
      row.append(kind, path, summary);
      box.appendChild(row);
    });
  }
}

function renderReport(report) {
  const box = $("report-view");
  if (!report) {
    const hasExperiment = Boolean(state.experimentId);
    box.innerHTML = `<p>当前还没有可展示的报告。先完成 record，再依次生成 channel 报告和自评报告；生成后这里会自动显示场景指标、AI 建议和文件链接。</p><div class="report-empty-actions"><button class="button" type="button" data-report-empty-action="selfeval">生成自评报告</button><button class="button secondary" type="button" data-report-empty-action="export">导出报告文件</button></div>`;
    box.querySelectorAll("[data-report-empty-action]").forEach((button) => {
      button.disabled = !hasExperiment;
      button.addEventListener("click", () => runAction(button.dataset.reportEmptyAction));
    });
    setPill("report-status", "尚无报告");
    renderReportFiles(null);
    const webButton = document.querySelector("#open-web-report");
    if (webButton) webButton.hidden = true;
    if ($("metric-score")) $("metric-score").textContent = "—";
    if ($("metric-score-label")) $("metric-score-label").textContent = "综合自评";
    if ($("metric-evidence")) $("metric-evidence").textContent = "—";
    return;
  }
  const meta = report.meta || {};
  const record = report.record || {};
  const score = report.score || {};
  const ai = report.ai || {};
  box.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "report-grid";
  const failedMetrics = (score.metrics || []).filter((item) => item && item.pass === false);
  const scoreValue = score.value;
  const scoreText = scoreValue === null || scoreValue === undefined
    ? (score.passed_metrics || "未评分")
    : String(scoreValue);
  const scoreLabel = scoreValue === null || scoreValue === undefined ? "场景通过项" : "综合自评";
  const scoreNote = scoreValue === null || scoreValue === undefined
    ? (score.passed_metrics
      ? "没有总分 · " + (failedMetrics.length ? failedMetrics.map((item) => item.name).join("、") + " 未通过" : "无失败项")
      : "尚未生成评分结果")
    : (score.is_official ? "官方评分" : "非官方自评") + " · 性能 " + (score.performance_score ?? "—") + " · 舒适 " + (score.comfort_score ?? "—") + " · " + (score.gate_status || "—");
  const cards = [
    { label: "实验状态", value: meta.status || "-", note: "" },
    { label: "channels", value: record.channel_count ?? "-", note: "" },
    { label: scoreLabel, value: scoreText, note: scoreNote },
    { label: "证据数", value: (report.evidence || []).length, note: "" }
  ];
  const crosswalkDistance = report.metrics && report.metrics.crosswalk_stop_distance_m;
  const crosswalkScore = report.score && report.score.crosswalk_stop_distance;
  if (crosswalkDistance !== undefined && crosswalkDistance !== null) {
    const crosswalkPass = crosswalkScore && crosswalkScore.pass;
    cards.push({ label: "人行道停车距离", value: String(crosswalkDistance) + " m", note: crosswalkPass ? "符合 1.5—2.0m" : "不在 1.5—2.0m 范围" });
  }
  cards.forEach((item) => {
    const card = document.createElement("div");
    card.className = "report-card";
    const b = document.createElement("b"); b.textContent = item.value;
    const small = document.createElement("small"); small.textContent = item.label;
    card.append(b, small);
    if (item.note) {
      const note = document.createElement("em");
      note.className = "report-card-note";
      note.textContent = item.note;
      card.appendChild(note);
    }
    grid.appendChild(card);
  });
  box.appendChild(grid);
  const facts = document.createElement("div");
  facts.className = "summary";
  facts.innerHTML = `<strong>AI 事实</strong>${(ai.facts || []).length ? ai.facts.map((x) => `<div>• ${esc(x)}</div>`).join("") : "暂无"}`;
  box.appendChild(facts);
  const suggestions = document.createElement("div");
  suggestions.className = "summary";
  suggestions.innerHTML = `<strong>建议</strong>${(ai.suggestions || []).length ? ai.suggestions.map((x) => `<div>• ${esc(x)}</div>`).join("") : "暂无"}`;
  box.appendChild(suggestions);
  renderReportFiles(report);
  const webButton = document.querySelector("#open-web-report");
  if (webButton) webButton.hidden = !(meta.source === "local-harness" && state.experimentId);
  setPill("report-status", meta.mode === "real" ? "真实数据" : "演示/计划", meta.mode === "real" ? "ok" : "");
  if ($("metric-status")) $("metric-status").textContent = meta.status || "—";
  if ($("metric-channels")) $("metric-channels").textContent = record.channel_count ?? "—";
  if ($("metric-score")) {
    $("metric-score").textContent = scoreValue === null || scoreValue === undefined
      ? (score.passed_metrics ? score.passed_metrics + " 通过" : "未评分")
      : String(scoreValue);
  }
  if ($("metric-score-label")) {
    $("metric-score-label").textContent = scoreValue === null || scoreValue === undefined ? "场景通过项" : "综合自评";
  }
  if ($("metric-evidence")) $("metric-evidence").textContent = (report.evidence || []).length;
}

async function openCurrentReportInWebsite() {
  if (!state.experimentId) {
    showToast("请先选择一个已有实验。", "error");
    return;
  }
  try {
    let raw;
    try {
      raw = await api("/api/experiments/" + encodeURIComponent(state.experimentId) + "/files/lab-report.json");
    } catch {
      raw = await api("/api/experiments/" + encodeURIComponent(state.experimentId) + "/report");
    }
    const payload = {
      meta: raw.meta || {},
      environment: raw.environment || {},
      record: raw.record || {},
      metrics: raw.metrics || {},
      score: raw.score || {},
      ai: raw.ai || {},
      lab: raw.lab || {},
      verification: raw.verification || {},
      evidence: raw.evidence || [],
      capability: raw.capability || {},
      errors: raw.errors || []
    };
    const bytes = new TextEncoder().encode(JSON.stringify(payload));
    let binary = "";
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    const encoded = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    window.open("https://apc.nyase.ru/lab/report.html?v=20261021-report-import-v2#report=" + encoded, "_blank", "noopener");
  } catch (error) {
    showToast("打开网站报告失败：" + error.message, "error");
  }
}

async function actionBody(action) {
  const execute = $("execute").checked;
  const task = state.task || { id: "crosswalk", title: "人行道避让" };
  if (action === "doctor") return { experiment_id: state.experimentId || undefined, task: task.id, scenario: task.title };
  if (action === "start-sim") return { task: task.id, scenario: task.title };
  if (action === "stop-sim") return { task: task.id, scenario: task.title, experiment_id: state.experimentId || undefined };
  if (action === "record") return { experiment_id: state.experimentId || undefined, task: task.id, scenario: task.title, tag: task.id, execute };
  if (["record-pause", "record-resume", "record-stop"].includes(action)) return { experiment_id: state.experimentId };
  if (action === "report") return { experiment_id: state.experimentId, record: state.experiment?.record?.path, execute };
  if (action === "selfeval") return { experiment_id: state.experimentId, execute };
  if (action === "export") return { experiment_id: state.experimentId };
  if (action === "explain") return { experiment_id: state.experimentId, question: $("ai-question").value.trim() || "请分析当前实验证据并给出下一步建议。", log: $("ai-log").value.trim() };
  return {};
}

async function runAction(action) {
  if (state.jobId) {
    showToast("已有任务正在运行，请等待当前任务完成。", "error");
    return;
  }
  if (action === "start-sim" || action === "stop-sim") {
    const confirmed = await confirmSimulationAction(action);
    if (!confirmed) return;
    if (action === "start-sim") openSimulationPlaceholder();
  }
  const label = actionLabel(action);
  setActionBusy(action, true);
  setWorkflowStatus(`${label}：正在提交本地 Harness...`, "running");
  setConsoleSummary(`${label}：正在提交本地 Harness...`, "running");
  setConsoleDetails(`[${action}] 正在提交任务...\n`);
  showToast(`${label}已开始，正在等待本地 Harness 响应。`);
  try {
    const payload = await actionBody(action);
    if (action === "report" && !payload.record) throw new Error("请先完成一次 record，或选择已有实验");
    if ((action === "report" || action === "selfeval" || action === "export" || action === "explain") && !payload.experiment_id) throw new Error("请先选择或创建实验记录");
    const data = await api(`/api/actions/${action}`, { method: "POST", body: payload });
    state.jobId = data.job.job_id;
    if (data.experiment_id) state.experimentId = data.experiment_id;
    setConsoleSummary(`${label}已提交，任务编号 ${state.jobId}，请等待运行结果。`, "running");
    setConsoleDetails(`[${action}] 任务已启动：${state.jobId}\n`);
    setPill("job-status", "运行中", "ok");
    setWorkflowStatus(`${label}已提交，任务编号 ${state.jobId}。`, "running");
    await pollJob(state.jobId);
  } catch (error) {
    setActionBusy(false);
    setPill("job-status", "失败", "bad");
    setWorkflowStatus(`${label}失败：${error.message}`, "error");
    showToast(`${label}失败：${error.message}`, "error");
    setConsoleSummary(`${label}失败：${error.message}`, "error");
    setConsoleDetails(`错误：${error.message}`);
    state.jobId = "";
    if (action === "start-sim" && state.simWindow && !state.simWindow.closed) state.simWindow.close();
  }
}

async function pollJob(jobId) {
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    const output = [job.stdout, job.stderr].filter(Boolean).join("\n");
    setConsoleDetails(output || "等待输出...");
    setPill("job-status", job.status, job.status === "failed" ? "bad" : job.status === "succeeded" ? "ok" : "");
    if (job.status === "running") {
      const elapsed = Math.max(0, Math.floor((Date.now() - state.actionStartedAt) / 1000));
      setConsoleSummary(`${actionLabel(job.action)}正在运行 · 已等待 ${elapsed}s`, "running");
      setWorkflowStatus(`${actionLabel(job.action)}正在运行 · 已等待 ${elapsed}s`, "running");
      state.pollTimer = setTimeout(() => pollJob(jobId), 1200);
      return;
    }
    setActionBusy(false);
    state.jobId = "";
    if (state.pollTimer) clearTimeout(state.pollTimer);
    const human = jobHumanSummary(job);
    setConsoleSummary(human.text, human.kind);
    if (job.status === "succeeded") {
      setWorkflowStatus(`${actionLabel(job.action)}完成，正在刷新实验状态。`, "success");
      showToast(`${actionLabel(job.action)}完成。`, "success");
    } else {
      setWorkflowStatus(`${actionLabel(job.action)}失败，请查看任务控制台。`, "error");
      showToast(`${actionLabel(job.action)}失败，请查看任务控制台。`, "error");
    }
    await loadExperiments();
    if (job.action === "doctor" || job.action === "start-sim" || job.action === "stop-sim") await loadRuntime();
    await loadExperiment(state.experimentId || job.experiment_id);
    if (job.action === "start-sim") {
      if (job.status === "succeeded") {
        if (state.simWindow && !state.simWindow.closed) state.simWindow.location.href = "http://localhost:8888/";
        else window.open("http://localhost:8888/", "_blank", "noopener");
      } else if (state.simWindow && !state.simWindow.closed) {
        state.simWindow.close();
      }
    }
  } catch (error) {
    setActionBusy(false);
    state.jobId = "";
    setPill("job-status", "失败", "bad");
    setWorkflowStatus(`任务轮询失败：${error.message}`, "error");
    showToast(`任务轮询失败：${error.message}`, "error");
    setConsoleSummary(`任务轮询失败：${error.message}`, "error");
    setConsoleDetails(`轮询失败：${error.message}`);
  }
}

async function init() {
  try {
    const session = await api("/api/session");
    state.token = session.token || "";
    state.tasks = session.tasks?.tasks || [];
    setDeepSeekStatus(Boolean(session.deepseek_configured));
    await loadDeepSeekSettings();
    await loadRuntime();
    const params = new URLSearchParams(location.search);
    const wanted = params.get("task");
    selectTask(state.tasks.find((task) => task.id === wanted) || state.tasks[0] || { id: "crosswalk", title: "人行道避让" });
    await loadExperiments();
    if (!state.experimentId && state.experiments.length) state.experimentId = state.experiments[0].experiment_id;
    if (state.experimentId) await loadExperiment(state.experimentId);
    setPill("service-status", "本地在线", "ok");
  } catch (error) {
    setPill("service-status", "连接失败", "bad");
    $("console").textContent = `无法连接 Harness：${error.message}`;
  }
}

function initAmbientInteractions() {
  const supportsFinePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!supportsFinePointer || reducedMotion) return;

  const spotlightSelector = ".panel, .metric, .task, .sidebar-card, .assistant-card, .sidebar-visual, .step";
  document.addEventListener("pointermove", (event) => {
    const target = event.target.closest(spotlightSelector);
    if (target) {
      const rect = target.getBoundingClientRect();
      target.style.setProperty("--spot-x", (event.clientX - rect.left) + "px");
      target.style.setProperty("--spot-y", (event.clientY - rect.top) + "px");
      target.classList.add("is-pointer-over");
    }
    const hero = document.querySelector(".hero");
    if (hero) {
      const rect = hero.getBoundingClientRect();
      if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) {
        const x = (event.clientX - rect.left) / Math.max(1, rect.width) - 0.5;
        const y = (event.clientY - rect.top) / Math.max(1, rect.height) - 0.5;
        hero.style.setProperty("--hero-x", (x * 8).toFixed(2) + "px");
        hero.style.setProperty("--hero-y", (y * 5).toFixed(2) + "px");
      }
    }
  }, { passive: true });
  document.addEventListener("pointerout", (event) => {
    const target = event.target.closest(spotlightSelector);
    if (target && !target.contains(event.relatedTarget)) target.classList.remove("is-pointer-over");
  }, { passive: true });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => runAction(button.dataset.action)));
  $("refresh").addEventListener("click", async () => { await loadExperiments(); await loadExperiment(state.experimentId); });
  $("refresh-exp").addEventListener("click", async () => { await loadExperiments(); });
  $("experiment-select").addEventListener("change", (event) => loadExperiment(event.target.value).catch((error) => { $("console").textContent = error.message; }));
  $("deepseek-save").addEventListener("click", saveDeepSeekSettings);
  $("deepseek-test").addEventListener("click", testDeepSeekConnection);
  document.getElementById("deepseek-clear").addEventListener("click", clearDeepSeekKey);
  const webReportButton = document.getElementById("open-web-report");
  if (webReportButton) webReportButton.addEventListener("click", openCurrentReportInWebsite);
  initChat();
  initAmbientInteractions();
  setInterval(renderRecordingControls, 1000);
  setInterval(refreshActiveRecord, 2500);
  init();
});
