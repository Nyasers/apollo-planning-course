const { chromium } = require("C:/Users/FQX/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const path = require("node:path");

const root = path.resolve(__dirname, "..", "site");
const url = (name) => "file:///" + path.join(root, name).replaceAll("\\", "/").replaceAll(" ", "%20");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    args: ["--no-proxy-server"]
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto(url("lab/index.html"), { waitUntil: "networkidle" });
  if (!(await page.title()).includes("实验中心")) throw new Error("Lab title missing");
  if ((await page.locator(".lab-metrics-grid .lab-card").count()) < 4) throw new Error("Experiment introduction cards expected");
  if ((await page.locator(".lab-ai-timeline .lab-ai-stage").count()) !== 5) throw new Error("Five teaching guide stages expected");
  if ((await page.locator('a[href="ai-loop.html"]').count()) < 1) throw new Error("AI teaching guide entry missing");
  if ((await page.locator('a[href="crosswalk.html"]').count()) < 1) throw new Error("Crosswalk entry missing");

  await page.locator('a[href="crosswalk.html"]').first().click();
  await page.waitForLoadState("networkidle");
  if ((await page.locator(".lab-car .lab-wheel").count()) !== 4) throw new Error("Vehicle should show four wheels");
  if ((await page.locator(".lab-car .lab-windshield").count()) !== 1) throw new Error("Vehicle windshield missing");
  const harnessHref = await page.locator("[data-local-panel]").first().getAttribute("href");
  if (!harnessHref.includes("task=crosswalk") || !harnessHref.includes("return=")) throw new Error("Harness deep link contract missing");
  if (await page.locator("[data-lab-results]").isVisible()) throw new Error("Results should stay hidden before the experiment");
  await page.locator('[data-lab-stage="2"]').click();
  if (!(await page.locator("[data-stage-title]").innerText()).includes("运行场景")) throw new Error("Stage switch failed");
  const messagesBefore = await page.locator(".lab-message").count();
  await page.locator('[data-agent-skill="env"]').click();
  await page.waitForTimeout(600);
  if ((await page.locator(".lab-message").count()) <= messagesBefore) throw new Error("Agent demo interaction failed");

  await page.locator("[data-run-demo]").click();
  await page.waitForTimeout(5600);
  if (!(await page.locator("[data-lab-results]").isVisible())) throw new Error("Results were not revealed after run");
  if (!(await page.locator("[data-lab-scene-status]").innerText()).includes("实验完成")) throw new Error("Scene did not finish the stop-and-wait sequence");
  if ((await page.locator("[data-report-link]").getAttribute("aria-disabled")) === "true") throw new Error("Report was not enabled after run");
  const metrics = await page.evaluate(() => JSON.parse(localStorage.getItem("apollo-lab-metrics-v1") || "null"));
  if (!metrics || metrics.after.score !== 94) throw new Error("Metrics were not persisted");

  await page.goto(url("lab/report.html"), { waitUntil: "networkidle" });
  if ((await page.locator("[data-report-bars] .lab-bar-row").count()) !== 4) throw new Error("Report bars missing");
  if ((await page.locator("[data-report-score-after]").innerText()) !== "94") throw new Error("Report score mismatch");
  if (!(await page.locator("[data-report-mode-badge]").innerText()).includes("演示")) throw new Error("Demo report badge missing");

  const sampleReport = {
    meta: { experiment_id: "20261018-test-crosswalk", task: "crosswalk", scenario: "人行道避让", created_at: "2026-10-18T12:00:00+08:00", source: "local-harness", mode: "real", status: "complete" },
    environment: { docker: true },
    record: { duration_sec: 25, channel_count: 7, message_count: 2048, status: "ok" },
    metrics: { min_ttc: 1.5, max_acceleration: 3.4, max_jerk: 4.5, hard_brake: 2 },
    verification: { min_ttc: 2.6, max_acceleration: 1.9, max_jerk: 2.4, hard_brake: 0, score_before: 80, score_after: 91 },
    score: {
      source: "apollo-eval",
      value: 91,
      is_official: false,
      passed_metrics: "2/2",
      metrics: [
        { name: "SpeedLimit", pass: true, score: 100, fail: 0, total: 257 },
        { name: "TTC", pass: false, score: 100, fail: 29, total: 257 }
      ]
    },
    ai: { skills: ["apollo-dev", "apollo-eval"], facts: ["测试事实"], hypotheses: ["测试推测"], suggestions: ["测试建议"], source_refs: ["planning.INFO"], student_confirmed: true },
    evidence: [{ type: "record", path: "outputs/experiments/test/crosswalk.record", summary: "测试记录" }],
    capability: { environment: 90, log_analysis: 80, data_capture: 88, parameter_tuning: 70, reporting: 75, ai_usage: 92 },
    errors: []
  };
  await page.locator("[data-report-file]").setInputFiles({ name: "report.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(sampleReport)) });
  await page.waitForTimeout(500);
  if (!(await page.locator("[data-report-mode-badge]").innerText()).includes("真实 Harness")) throw new Error("Imported report badge mismatch");
  if ((await page.locator("[data-report-score-after]").innerText()) !== "91") throw new Error("Imported score mismatch");
  if ((await page.locator("[data-report-run-id]").innerText()) !== "20261018-test-crosswalk") throw new Error("Imported experiment id missing");
  if ((await page.locator("[data-report-evidence] li").count()) !== 1) throw new Error("Imported evidence missing");
  if ((await page.locator("[data-report-score-table] tbody tr").count()) !== 2) throw new Error("Imported scenario metrics missing");
  if (!(await page.locator("[data-report-environment]").innerText()).includes("已记录")) throw new Error("Environment status missing");
  const storedReport = await page.evaluate(() => localStorage.getItem("apollo-lab-harness-report-v1"));
  if (!storedReport) throw new Error("Imported report was not persisted");

  await page.reload({ waitUntil: "networkidle" });
  if ((await page.locator("[data-report-score-after]").innerText()) !== "91") throw new Error("Imported report did not survive reload");
  await page.locator("[data-report-reset]").click();
  if (!(await page.locator("[data-report-mode-badge]").innerText()).includes("演示")) throw new Error("Demo reset failed");
  await page.goto(url("lab/report.html") + "?apc_run=run-123&apc_status=done&apc_score=99", { waitUntil: "networkidle" });
  if (!(await page.locator("[data-report-import-status]").innerText()).includes("run-123")) throw new Error("Harness run summary was not shown");
  if ((await page.locator("[data-report-score-after]").innerText()) !== "94") throw new Error("URL score must not be trusted without report.json");
  await page.locator("[data-report-file]").setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from("{bad json") });
  await page.waitForTimeout(300);
  if (!(await page.locator("[data-report-import-status]").innerText()).includes("导入失败")) throw new Error("Invalid report should be rejected");
  if (!(await page.locator("[data-report-mode-badge]").innerText()).includes("演示")) throw new Error("Invalid import replaced the demo report");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url("lab/crosswalk.html"), { waitUntil: "networkidle" });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 1) throw new Error("Lab mobile overflow: " + overflow + "px");

  await page.goto(url("lab/report.html"), { waitUntil: "networkidle" });
  const reportOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (reportOverflow > 1) throw new Error("Report mobile overflow: " + reportOverflow + "px");

  await browser.close();
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Lab checks passed: entry, stage, agent, run, report, mobile.");
})().catch((error) => { console.error(error); process.exit(1); });