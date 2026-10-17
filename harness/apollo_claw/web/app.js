const token = window.__APOLLO_CLAW_TOKEN__;
const state = { tasks: [], experiments: [], task: null, experiment: null, experimentId: "", jobId: "", pollTimer: null };
const $ = (id) => document.getElementById(id);
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }

async function api(path, options = {}) {
  const opts = { ...options, headers: { ...(options.headers || {}) } };
  if (opts.body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  if (opts.method === "POST") opts.headers["X-Apollo-Claw-Token"] = token;
  const response = await fetch(path, opts);
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
  renderAI(null);
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

async function loadExperiment(id) {
  if (!id) { state.experiment = null; state.experimentId = ""; renderExperiment(); renderReport(null); return; }
  state.experimentId = id;
  state.experiment = await api(`/api/experiments/${encodeURIComponent(id)}`);
  renderExperiments();
  renderExperiment();
  renderAI(state.experiment.ai);
  try {
    const report = await api(`/api/experiments/${encodeURIComponent(id)}/report`);
    renderReport(report);
  } catch {
    renderReport(null);
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
  setPill("report-status", status, status === "empty_record" || status.includes("failed") ? "bad" : "ok");
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

function renderReport(report) {
  const box = $("report-view");
  if (!report) {
    box.textContent = "选择已有实验并导出报告后，这里显示状态、指标和证据。";
    setPill("report-status", "尚无报告");
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
  setPill("report-status", meta.mode === "real" ? "真实数据" : "演示/计划", meta.mode === "real" ? "ok" : "");
}

async function actionBody(action) {
  const execute = $("execute").checked;
  const task = state.task || { id: "crosswalk", title: "人行道避让" };
  if (action === "doctor") return { task: task.id, scenario: task.title };
  if (action === "record") return { experiment_id: state.experimentId || undefined, task: task.id, scenario: task.title, tag: task.id, seconds: Number($("seconds").value || 25), execute };
  if (action === "report") return { experiment_id: state.experimentId, record: state.experiment?.record?.path, execute };
  if (action === "export") return { experiment_id: state.experimentId };
  if (action === "explain") return { experiment_id: state.experimentId, question: $("ai-question").value.trim() || "请分析当前实验证据并给出下一步建议。", log: $("ai-log").value.trim() };
  return {};
}

async function runAction(action) {
  if (state.jobId) return;
  try {
    setPill("job-status", "提交中");
    const payload = await actionBody(action);
    if (action === "report" && !payload.record) throw new Error("请先完成一次 record，或选择已有实验");
    if ((action === "report" || action === "export" || action === "explain") && !payload.experiment_id) throw new Error("请先选择或创建实验记录");
    const data = await api(`/api/actions/${action}`, { method: "POST", body: payload });
    state.jobId = data.job.job_id;
    state.experimentId = data.experiment_id;
    $("console").textContent = `[${action}] 任务已启动：${state.jobId}\n`;
    setPill("job-status", "运行中", "ok");
    await pollJob(state.jobId);
  } catch (error) {
    setPill("job-status", "失败", "bad");
    $("console").textContent = `错误：${error.message}`;
    state.jobId = "";
  }
}

async function pollJob(jobId) {
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    const output = [job.stdout, job.stderr].filter(Boolean).join("\n");
    $("console").textContent = `[${job.action}] ${job.status}\n${output || "等待输出..."}\n`;
    setPill("job-status", job.status, job.status === "failed" ? "bad" : job.status === "succeeded" ? "ok" : "");
    if (job.status === "running") {
      state.pollTimer = setTimeout(() => pollJob(jobId), 1200);
      return;
    }
    state.jobId = "";
    if (state.jobTimer) clearTimeout(state.jobTimer);
    await loadExperiments();
    await loadExperiment(state.experimentId || job.experiment_id);
  } catch (error) {
    state.jobId = "";
    setPill("job-status", "失败", "bad");
    $("console").textContent = `轮询失败：${error.message}`;
  }
}

async function init() {
  try {
    const session = await api("/api/session");
    state.tasks = session.tasks?.tasks || [];
    setPill("deepseek-status", session.deepseek_configured ? "DeepSeek 已配置" : "规则降级模式", session.deepseek_configured ? "ok" : "");
    const params = new URLSearchParams(location.search);
    const wanted = params.get("task");
    selectTask(state.tasks.find((task) => task.id === wanted) || state.tasks[0] || { id: "crosswalk", title: "人行道避让" });
    await loadExperiments();
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
  init();
});
