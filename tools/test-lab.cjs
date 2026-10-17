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

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url("lab/crosswalk.html"), { waitUntil: "networkidle" });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 1) throw new Error("Lab mobile overflow: " + overflow + "px");

  await browser.close();
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Lab checks passed: entry, stage, agent, run, report, mobile.");
})().catch((error) => { console.error(error); process.exit(1); });