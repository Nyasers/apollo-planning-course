(() => {
  "use strict";
  const root = document.querySelector("[data-start-guide]");
  if (!root) return;
  const storageKey = "apollo-start-guide-v1";
  const panels = Array.from(root.querySelectorAll("[data-start-panel]"));
  const navButtons = Array.from(root.querySelectorAll("[data-start-nav]"));
  const requirementsBox = root.querySelector("[data-start-requirements]");
  const materialsBox = root.querySelector("[data-start-materials]");
  const scenariosBox = root.querySelector("[data-competition-scenarios]");
  const requirementConfirm = root.querySelector("[data-start-confirm]");
  const materialsConfirm = root.querySelector("[data-materials-confirm]");
  let manifest = null;
  let current = 0;
  let maxStep = 0;

  const demos = [
    { kicker: "Environment", title: "环境检查与 AI 诊断", text: "系统检查 Linux、Docker、Apollo 和 DreamView；AI 只解释检查结果，并给出下一步验证建议。", data: ["Linux 已运行", "Docker 未就绪", "AI：先启动 Docker，再重新检查 Apollo"] },
    { kicker: "Scenario", title: "运行人行道避让场景", text: "在 DreamView 和 SimControl 中选择地图与人行横道场景，观察车辆接近停止线和行人通过。", data: ["车辆接近停止线", "行人仍在横道内", "目标：停车等待，不抢行"] },
    { kicker: "AI Diagnosis", title: "AI 解释异常，不替代判断", text: "学生提供日志和代码片段，AI 将事实、推测和建议分开，学生确认后再执行下一步。", data: ["事实：TTC 低于阈值", "推测：减速时机偏晚", "建议：检查速度边界与停车点"] },
    { kicker: "Record & Metrics", title: "录制数据并查看指标", text: "开始 record，采集 planning、control、localization 等 channel；完成后查看 TTC、Jerk、急刹和速度曲线。", data: ["6 个核心 channel", "record 已保存", "指标报告已生成"] },
    { kicker: "Evidence", title: "形成报告与提交预览", text: "系统汇总环境、record、指标、评分和 AI 数据，形成 report.json 与实验报告，供核查和提交。", data: ["doctor.json", "record / CSV / PNG", "report.json / report.md"] }
  ];
  let demoIndex = 0;

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      current = Number.isInteger(saved.current) ? Math.max(0, Math.min(4, saved.current)) : 0;
      maxStep = Number.isInteger(saved.maxStep) ? Math.max(current, Math.min(4, saved.maxStep)) : current;
      if (requirementConfirm) requirementConfirm.checked = Boolean(saved.requirements);
      if (materialsConfirm) materialsConfirm.checked = Boolean(saved.materials);
    } catch (error) {}
  }
  function saveState() {
    localStorage.setItem(storageKey, JSON.stringify({
      current, maxStep,
      requirements: requirementConfirm ? requirementConfirm.checked : false,
      materials: materialsConfirm ? materialsConfirm.checked : false
    }));
  }
  function setStep(index) {
    current = Math.max(0, Math.min(4, index));
    maxStep = Math.max(maxStep, current);
    panels.forEach((panel, i) => panel.classList.toggle("is-active", i === current));
    navButtons.forEach((button, i) => {
      button.classList.toggle("is-active", i === current);
      button.disabled = i > maxStep;
    });
    root.querySelectorAll("[data-start-next]").forEach((button) => {
      const panel = button.closest("[data-start-panel]");
      const step = Number(panel && panel.dataset.startPanel);
      if (step === 1) button.disabled = !(requirementConfirm && requirementConfirm.checked);
      if (step === 2) button.disabled = !(materialsConfirm && materialsConfirm.checked);
    });
    saveState();
    window.scrollTo({ top: root.offsetTop, behavior: "smooth" });
  }
  function renderDemo() {
    const item = demos[demoIndex];
    const set = (selector, value) => { const el = root.querySelector(selector); if (el) el.textContent = value; };
    set("[data-demo-count]", String(demoIndex + 1).padStart(2, "0") + " / " + String(demos.length).padStart(2, "0"));
    set("[data-demo-index]", String(demoIndex + 1).padStart(2, "0"));
    set("[data-demo-kicker]", item.kicker);
    set("[data-demo-title]", item.title);
    set("[data-demo-text]", item.text);
    const data = root.querySelector("[data-demo-data]");
    if (data) {
      data.innerHTML = "";
      item.data.forEach((value, i) => {
        const row = document.createElement("div");
        row.innerHTML = '<span>' + String(i + 1).padStart(2, "0") + '</span><strong></strong>';
        row.querySelector("strong").textContent = value;
        data.appendChild(row);
      });
    }
  }
  function formatBytes(bytes) {
    const n = Number(bytes);
    if (!Number.isFinite(n) || n <= 0) return "待确认";
    if (n >= 1024 ** 3) return (n / 1024 ** 3).toFixed(1) + " GB";
    if (n >= 1024 ** 2) return (n / 1024 ** 2).toFixed(1) + " MB";
    return Math.round(n / 1024) + " KB";
  }
  function renderRequirements() {
    if (!requirementsBox || !manifest) return;
    const req = manifest.onboarding.requirements;
    const items = [
      ["操作系统", req.os], ["内存", req.memoryGb + " GB 及以上"], ["可用磁盘", req.diskGb + " GB 及以上"],
      ["处理器", req.cpu], ["权限", req.adminRequired ? "需要管理员权限" : "无需管理员权限"], ["网络", req.networkRequired ? "需要下载镜像和 Harness" : "无需联网"]
    ];
    requirementsBox.innerHTML = "";
    items.forEach(([label, value]) => {
      const card = document.createElement("article");
      card.innerHTML = "<span></span><strong></strong>";
      card.querySelector("span").textContent = label; card.querySelector("strong").textContent = value;
      requirementsBox.appendChild(card);
    });
  }
  function materialCard(item, kind) {
    const card = document.createElement("article");
    card.className = "start-material-card";
    const ready = item.status === "ready" && item.url;
    card.innerHTML = '<div class="start-material-head"><span></span><span class="lab-chip"></span></div><p></p><dl><div><dt>版本</dt><dd></dd></div><div><dt>大小</dt><dd></dd></div><div><dt>SHA256</dt><dd></dd></div></dl><div class="start-material-actions"></div><small></small>';
    card.querySelector(".start-material-head > span").textContent = item.label || kind;
    const status = card.querySelector(".lab-chip");
    status.textContent = ready ? "可下载" : "待发布";
    status.classList.toggle("is-demo", !ready);
    card.querySelector("p").textContent = item.note || "";
    card.querySelectorAll("dd")[0].textContent = item.version || "待确认";
    card.querySelectorAll("dd")[1].textContent = formatBytes(item.sizeBytes);
    card.querySelectorAll("dd")[2].textContent = item.sha256 || "待补充";
    const actions = card.querySelector(".start-material-actions");
    if (ready) {
      const a = document.createElement("a"); a.className = "button-primary"; a.href = item.url; a.textContent = "下载 " + (kind === "image" ? "WSL 镜像" : "Harness 包"); actions.appendChild(a);
    }
    if (kind === "image") {
      const manual = document.createElement("a"); manual.className = "button-secondary"; manual.href = manifest.onboarding.manualSetupUrl; manual.textContent = "查看手动配置"; actions.appendChild(manual);
    }
    if (kind === "harness") {
      const guide = document.createElement("a"); guide.className = "button-secondary"; guide.href = "../setup/index.html#harness-config"; guide.textContent = "查看配置说明"; actions.appendChild(guide);
    }
    card.querySelector("small").textContent = ready ? "下载后请核对 SHA256。" : "请联系项目负责人获取发布版本。";
    return card;
  }
  function renderCompetitionScenarios(data) {
    if (!scenariosBox || !data || !Array.isArray(data.scenarios)) return;
    scenariosBox.innerHTML = "";
    data.scenarios.forEach((scenario) => {
      const card = document.createElement("article");
      const open = scenario.status === "open";
      card.className = "competition-card " + (open ? "is-open" : "is-planned");
      const head = document.createElement("div");
      head.className = "competition-card-head";
      const number = document.createElement("span");
      number.className = "competition-number";
      number.textContent = scenario.number || "实验";
      const status = document.createElement("span");
      status.className = "competition-status " + (open ? "is-open" : "is-planned");
      status.textContent = open ? "可开始" : "待接入";
      head.append(number, status);
      const title = document.createElement("h3");
      title.textContent = scenario.title || "未命名场景";
      const goal = document.createElement("p");
      goal.className = "competition-goal";
      goal.textContent = scenario.goal || "";
      const details = document.createElement("details");
      details.className = "competition-rules";
      const summary = document.createElement("summary");
      summary.textContent = "查看扣分规则";
      details.appendChild(summary);
      const list = document.createElement("ul");
      (scenario.penalties || []).forEach((text) => {
        const li = document.createElement("li");
        li.textContent = text;
        list.appendChild(li);
      });
      details.appendChild(list);
      const actions = document.createElement("div");
      actions.className = "competition-actions";
      if (open && scenario.page) {
        const link = document.createElement("a");
        link.className = "button-primary";
        link.href = scenario.page;
        link.textContent = "进入真实实验";
        actions.appendChild(link);
      } else {
        const pending = document.createElement("span");
        pending.className = "competition-pending";
        pending.textContent = "实验页面待接入";
        actions.appendChild(pending);
      }
      card.append(head, title, goal, details, actions);
      scenariosBox.appendChild(card);
    });
  }

  async function loadCompetitionScenarios() {
    if (!scenariosBox) return;
    try {
      const response = await fetch("../harness/competition-scenarios.json?v=20261021-competition-scenarios-v2", { cache: "no-store" });
      if (!response.ok) throw new Error("scenarios unavailable");
      renderCompetitionScenarios(await response.json());
    } catch (error) {
      scenariosBox.innerHTML = '<div class="lab-report-empty">实验信息暂时无法读取。</div>';
    }
  }

  async function loadManifest() {
    try {
      const response = await fetch("../harness/manifest.json?v=20261021-competition-scenarios-v2", { cache: "no-store" });
      if (!response.ok) throw new Error("manifest unavailable");
      manifest = await response.json();
      renderRequirements();
      if (materialsBox) {
        materialsBox.innerHTML = "";
        materialsBox.append(materialCard(manifest.onboarding.wslImage, "image"), materialCard(manifest.onboarding.harnessPackage, "harness"));
      }
    } catch (error) {
      if (materialsBox) materialsBox.innerHTML = '<div class="lab-report-empty">材料信息暂时无法读取，请稍后重试或查看手动配置说明。</div>';
    }
  }

  navButtons.forEach((button) => button.addEventListener("click", () => setStep(Number(button.dataset.startNav))));
  root.querySelectorAll("[data-start-next]").forEach((button) => button.addEventListener("click", () => setStep(current + 1)));
  root.querySelectorAll("[data-start-prev]").forEach((button) => button.addEventListener("click", () => setStep(current - 1)));
  root.querySelector("[data-start-reset]")?.addEventListener("click", () => { localStorage.removeItem(storageKey); current = 0; maxStep = 0; if (requirementConfirm) requirementConfirm.checked = false; if (materialsConfirm) materialsConfirm.checked = false; setStep(0); });
  requirementConfirm?.addEventListener("change", () => { const next = root.querySelector('[data-start-panel="1"] [data-start-next]'); if (next) next.disabled = !requirementConfirm.checked; saveState(); });
  materialsConfirm?.addEventListener("change", () => { const next = root.querySelector('[data-start-panel="2"] [data-start-next]'); if (next) next.disabled = !materialsConfirm.checked; saveState(); });
  root.querySelector("[data-demo-next]")?.addEventListener("click", () => { demoIndex = (demoIndex + 1) % demos.length; renderDemo(); });
  root.querySelector("[data-demo-prev]")?.addEventListener("click", () => { demoIndex = (demoIndex + demos.length - 1) % demos.length; renderDemo(); });

  loadState();
  if (new URLSearchParams(location.search).get("step") === "experiments") {
    current = 4;
    maxStep = 4;
  }
  renderDemo(); setStep(current); loadManifest(); loadCompetitionScenarios();
})();
