const token = window.__APOLLO_CLAW_TOKEN__;
const state = { tasks: [], experiments: [], task: null, experiment: null, experimentId: "", jobId: "", pollTimer: null, token: "", context: { lesson: "", source: "", returnUrl: "" } };
const $ = (id) => document.getElementById(id);
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }

const allowedCourseHosts = new Set(["apc.nyase.ru", "tyler-fqx.github.io", "localhost", "127.0.0.1"]);

function safeCourseUrl(raw) {
  if (!raw) return "";
  try {
    const url = new URL(raw);
    const localHttp = url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname);
    if (url.protocol !== "https:" && !localHttp) return "";
    if (!allowedCourseHosts.has(url.hostname)) return "";
    return url.href;
  } catch {
    return "";
  }
}

function courseReportUrl(report) {
  if (!state.context.returnUrl) return "";
  try {
    const url = new URL(state.context.returnUrl);
    if (/\.html?$/i.test(url.pathname)) url.pathname = url.pathname.replace(/[^/]+$/, "report.html");
    else url.pathname = url.pathname.replace(/\/?$/, "/report.html");
    const params = new URLSearchParams({ apc_status: "done", apc_source: "local-harness" });
    if (report?.meta?.experiment_id) params.set("apc_run", report.meta.experiment_id);
    if (report?.score?.value !== null && report?.score?.value !== undefined) params.set("apc_score", String(report.score.value));
    url.search = params.toString();
    url.hash = "";
    return url.href;
  } catch {
    return "";
  }
}

function renderCourseContext() {
  const box = $("course-context");
  if (!box) return;
  const { lesson, source, returnUrl } = state.context;
  if (!lesson && !source && !returnUrl) { box.hidden = true; return; }
  box.hidden = false;
  const sourceLabel = source === "apc" ? "Apollo Planning Lab 课程网站" : "课程网站";
  $("course-context-text").textContent = `来自${sourceLabel}`;
  $("course-context-detail").textContent = lesson ? `课程单元：${lesson}` : "已通过课程实验台进入";
  const back = $("course-return");
  if (returnUrl) { back.href = returnUrl; back.hidden = false; }
  else back.hidden = true;
}

function configureReportActions(report) {
  const box = $("report-actions");
  if (!box) return;
  const id = report?.meta?.experiment_id || state.experimentId;
  if (!report || !id) { box.hidden = true; return; }
  box.hidden = false;
  $("download-report-json").href = `/api/experiments/${encodeURIComponent(id)}/report.json`;
  $("download-report-md").href = `/api/experiments/${encodeURIComponent(id)}/report.md`;
  const course = $("return-report-course");
  const target = courseReportUrl(report);
  if (target) { course.href = target; course.hidden = false; }
  else course.hidden = true;
}

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

function renderReport(report) {
  const box = $("report-view");
  if (!report) {
    box.textContent = "选择已有实验并导出报告后，这里显示状态、指标和证据。";
    setPill("report-status", "尚无报告");
    configureReportActions(null);
    if ($("metric-score")) $("metric-score").textContent = "—";
    if ($("metric-evidence")) $("metric-evidence").textContent = "—";
    return;
  }
  configureReportActions(report);
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
  const emptyRecord = record.channel_count === 0 || record.status === "empty" || String(meta.status || "").includes("empty");
  setPill("report-status", emptyRecord ? "空 record" : meta.mode === "real" ? "真实数据" : "演示/计划", emptyRecord ? "bad" : meta.mode === "real" ? "ok" : "");
  if ($("metric-status")) $("metric-status").textContent = meta.status || "—";
  if ($("metric-channels")) $("metric-channels").textContent = record.channel_count ?? "—";
  if ($("metric-score")) $("metric-score").textContent = score.value ?? "—";
  if ($("metric-evidence")) $("metric-evidence").textContent = (report.evidence || []).length;
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
    state.token = session.token || "";
    state.tasks = session.tasks?.tasks || [];
    setDeepSeekStatus(Boolean(session.deepseek_configured));
    await loadDeepSeekSettings();
    const params = new URLSearchParams(location.search);
    state.context = {
      lesson: params.get("lesson") || "",
      source: params.get("source") || "",
      returnUrl: safeCourseUrl(params.get("return")),
    };
    renderCourseContext();
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
  $("deepseek-save").addEventListener("click", saveDeepSeekSettings);
  $("deepseek-test").addEventListener("click", testDeepSeekConnection);
  $("deepseek-clear").addEventListener("click", clearDeepSeekKey);
  init();
});
