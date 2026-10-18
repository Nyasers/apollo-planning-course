const token = window.__APOLLO_CLAW_TOKEN__;
const state = { tasks: [], experiments: [], task: null, experiment: null, experimentId: "", report: null, chat: [], chatBusy: false, jobId: "", pollTimer: null, actionTimer: null, actionStartedAt: 0, activeAction: "", token: "" };
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
  return ({ doctor: "检查环境", record: "开始录制", report: "生成报告", selfeval: "生成自评", export: "导出", explain: "开始诊断" })[action] || "执行中";
}

function updateActionElapsed() {
  if (!state.activeAction) return;
  const button = document.querySelector(`[data-action="${state.activeAction}"]`);
  if (!button) return;
  const elapsed = Math.max(0, Math.floor((Date.now() - state.actionStartedAt) / 1000));
  const prefix = state.activeAction === "record" ? "录制中" : "处理中";
  button.textContent = `${prefix} ${elapsed}s`;
  setWorkflowStatus(state.activeAction === "record"
    ? `正在录制，已等待 ${elapsed}s。请保持 DreamView 和仿真场景运行，不要关闭本页面。`
    : `${actionLabel(state.activeAction)}中，已等待 ${elapsed}s。`, "running");
}

function setActionBusy(action, busy) {
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
  if (job.action === "record") {
    return dryRun
      ? { text: "这次只是演练：生成了录制命令，但没有真正进入 Apollo 容器。勾选“真实执行”后再点“开始录制”。", kind: "warn" }
      : { text: "录制完成。下一步点击“生成 channel 报告”，再点击“生成自评”。", kind: "success" };
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
    return { text: "环境检查完成，结果已保存为 doctor.json。建议接着启动 DreamView 场景。", kind: "success" };
  }
  if (job.action === "explain") {
    return { text: "AI 诊断完成，结果已显示在上方的“DeepSeek 诊断”区域。", kind: "success" };
  }
  return { text: `${actionLabel(job.action)}完成。`, kind: "success" };
}

function renderTasks() {
  const list = $("task-list");
  list.innerHTML = "";
  state.tasks.forEach((task) => {
    const button = document.createElement("button");
    button.className = "task" + (state.task && state.task.id === task.id ? " active" : "");
    button.type = "button";
    const strong = document.createElement("strong");
    strong.textContent = task.title || task.id;
    const small = document.createElement("small");
    small.textContent = `${task.id} · ${task.status || "open"}`;
    button.append(strong, small);
    button.addEventListener("click", () => selectTask(task));
    list.appendChild(button);
  });
}

function selectTask(task) {
  state.task = task;
  state.experimentId = "";
  state.experiment = null;
  $("task-title").textContent = task.title || "城市道路自动驾驶综合仿真实验";
  $("task-desc").textContent = task.description || "按流程完成环境检查、场景运行、record、报告和复盘。";
  setPill("active-task", task.title || task.id, "ok");
  renderTasks();
  renderExperiments();
  renderExperiment();
  state.report = null;
  state.chat = [];
  renderChat();
  updateReportContext();
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

async function loadExperiment(id) {
  if (!id) {
    state.experiment = null;
    state.experimentId = "";
    state.report = null;
    state.chat = [];
    renderExperiment();
    renderReport(null);
    renderChat();
    updateReportContext();
    return;
  }
  state.experimentId = id;
  state.experiment = await api(`/api/experiments/${encodeURIComponent(id)}`);
  renderExperiments();
  renderExperiment();
  state.report = null;
  try {
    state.report = await fetchCurrentReport(id);
    renderReport(state.report);
  } catch {
    renderReport(null);
  }
  loadChatHistory();
  updateReportContext();
  renderChat();
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

function renderExperiment() {
  const box = $("experiment-summary");
  if (!state.experiment) {
    box.textContent = "尚无实验记录。点击“检查环境”或“开始录制”会自动创建。";
    return;
  }
  const exp = state.experiment;
  const record = exp.record || {};
  const status = exp.meta?.status || "created";
  box.innerHTML = `<strong>${esc(status)}</strong><div>实验：${esc(exp.meta?.scenario || exp.meta?.task || "-")}</div><div>record：${esc(record.channel_count ?? "-")} channels · ${esc(record.size_bytes ?? "-")} bytes</div><div>记录状态：${esc(record.status || "-")}</div>`;
  if ($("metric-status")) $("metric-status").textContent = status;
  if ($("metric-channels")) $("metric-channels").textContent = record.channel_count ?? "—";
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
  const text = configured ? `DeepSeek 已配置${masked ? " · " + masked : ""}` : "规则降级模式";
  setPill("deepseek-config-status", text, configured ? "ok" : "");
  setPill("deepseek-status", text, configured ? "ok" : "");
  if ($("deepseek-side-status")) $("deepseek-side-status").textContent = configured ? "已配置" : "规则降级";
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
  [["report.json", "打开 report.json"], ["report.md", "打开 report.md"], ["selfeval.md", "打开 selfeval.md"], ["doctor.json", "打开 doctor.json"]].forEach(([name, label]) => {
    const link = document.createElement("a");
    link.href = `/api/experiments/${encodeURIComponent(experimentId)}/files/${encodeURIComponent(name)}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = label;
    box.appendChild(link);
  });
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
  const cards = [
    ["实验状态", meta.status || "-"],
    ["channels", record.channel_count ?? "-"],
    ["场景分数", score.value ?? "-"],
    ["证据数", (report.evidence || []).length]
  ];
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "report-card";
    const b = document.createElement("b"); b.textContent = value;
    const small = document.createElement("small"); small.textContent = label;
    card.append(b, small); grid.appendChild(card);
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
  const evidence = document.createElement("div");
  evidence.className = "evidence";
  (report.evidence || []).forEach((item) => {
    const row = document.createElement("div");
    row.textContent = `${item.type || "file"} · ${item.path || ""}`;
    evidence.appendChild(row);
  });
  box.appendChild(evidence);
  renderReportFiles(report);
  const webButton = document.querySelector("#open-web-report");
  if (webButton) webButton.hidden = !(meta.source === "local-harness" && state.experimentId);
  setPill("report-status", meta.mode === "real" ? "真实数据" : "演示/计划", meta.mode === "real" ? "ok" : "");
  if ($("metric-status")) $("metric-status").textContent = meta.status || "—";
  if ($("metric-channels")) $("metric-channels").textContent = record.channel_count ?? "—";
  if ($("metric-score")) $("metric-score").textContent = score.value ?? "—";
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
    window.open("https://apc.nyase.ru/lab/report.html?v=20261019-report-handoff-3#report=" + encoded, "_blank", "noopener");
  } catch (error) {
    showToast("打开网站报告失败：" + error.message, "error");
  }
}

async function actionBody(action) {
  const execute = $("execute").checked;
  const task = state.task || { id: "crosswalk", title: "人行道避让" };
  if (action === "doctor") return { task: task.id, scenario: task.title };
  if (action === "record") return { experiment_id: state.experimentId || undefined, task: task.id, scenario: task.title, tag: task.id, seconds: Number($("seconds").value || 25), execute };
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
    state.experimentId = data.experiment_id;
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
    await loadExperiment(state.experimentId || job.experiment_id);
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
  init();
});
