import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { COMMIT, courseGroups, lessons, roadmap } from "./site-data.mjs";

const root = path.resolve(import.meta.dirname, "..");
const siteDir = path.join(root, "site");
const assetsDir = path.join(siteDir, "assets");
const markedPath = "C:/Users/FQX/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/marked/lib/marked.esm.js";
const { marked } = await import(pathToFileURL(markedPath).href);

marked.setOptions({ gfm: true, breaks: false });

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function slugify(value) {
  return String(value)
    .replace(/<[^>]+>/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
    .replace(/^-+|-+$/g, "") || "section";
}

function addHeadingIds(html) {
  const used = new Set();
  return html.replace(/<h([23])([^>]*)>([\s\S]*?)<\/h\1>/g, (match, level, attrs, body) => {
    const text = body.replace(/<[^>]+>/g, "").trim();
    let id = slugify(text);
    let suffix = 2;
    while (used.has(id)) id = slugify(text) + "-" + suffix++;
    used.add(id);
    const cleanAttrs = attrs.replace(/\s+id="[^"]*"/g, "");
    return `<h${level}${cleanAttrs} id="${id}">${body}</h${level}>`;
  });
}

function renderSidebar(activeId = "") {
  let nextUsed = false;
  const groups = courseGroups.map((group, groupIndex) => {
    const items = group.items.map((item) => {
      const isActive = activeId === item.id;
      const completeClass = "";
      let statusClass = "";
      if (item.status === "planned" && !nextUsed) {
        statusClass = " is-next";
        nextUsed = true;
      }
      if (item.status === "planned") statusClass = statusClass || " is-planned";
      const common = `nav-link${statusClass}${completeClass}`;
      const content = `<span class="nav-index">${item.index}</span><span class="nav-title">${item.title}</span><span class="nav-state" aria-hidden="true"></span>`;
      if (item.href) {
        return `<li><a class="${common}" href="${item.href}" data-lesson-id="${item.id}"${isActive ? ' aria-current="page"' : ""}>${content}</a></li>`;
      }
      return `<li><span class="${common}" data-lesson-id="${item.id}" aria-disabled="true">${content}</span></li>`;
    }).join("");
    return `<section class="nav-group"><p class="nav-label">${group.label}</p><ul class="nav-list">${items}</ul></section>`;
  }).join("");

  return `<aside class="sidebar" aria-label="课程导航">
    <div class="sidebar-progress">
      <div class="progress-head"><span>学习进度</span><strong data-progress-value>0%</strong></div>
      <div class="progress-track" aria-hidden="true"><div class="progress-fill" data-progress-fill></div></div>
      <p class="sidebar-note"><span data-progress-count>0 / 21</span> 个单元已完成。进度只保存在你的浏览器。</p>
    </div>
    ${groups}
    <section class="nav-group"><p class="nav-label">实验平台</p><ul class="nav-list"><li><a class="nav-link" href="lab/index.html"><span class="nav-index">LAB</span><span class="nav-title">MVP 实验中心</span><span class="nav-state" aria-hidden="true"></span></a></li></ul></section>
  </aside>`;
}

function topbar() {
  return `<header class="topbar">
    <a class="brand" href="index.html" aria-label="返回课程首页">
      <span class="brand-mark" aria-hidden="true"></span>
      <span class="brand-copy"><strong>APOLLO / PLANNING LAB</strong><span>从仿真环境到 Scenario 与 Task</span></span>
    </a>
    <div class="top-actions">
      <a class="action-button lab-entry-button" href="lab/index.html"><span>实验中心</span><span class="button-label">进入 MVP</span></a>
      <span class="commit-pill">commit ${COMMIT.slice(0, 8)}</span>
      <button class="action-button" type="button" data-search-open aria-label="搜索课程"><span>搜索</span><span class="button-label">课程内容</span><span aria-hidden="true">/</span></button>
      <button class="icon-button" type="button" data-theme-toggle aria-label="切换深浅主题" aria-pressed="false">◐</button>
      <button class="icon-button menu-button" type="button" data-menu-toggle aria-label="打开课程目录" aria-expanded="false">≡</button>
    </div>
  </header>`;
}

function searchDialog() {
  return `<div class="search-dialog" data-search-dialog aria-hidden="true" role="dialog" aria-modal="true" aria-label="搜索课程内容">
    <div class="search-panel">
      <div class="search-input-wrap"><span>SEARCH</span><input class="search-input" data-search-input type="search" placeholder="搜索 Task、指针、WSL、Scenario..." autocomplete="off"><span>ESC</span></div>
      <div class="search-results" data-search-results></div>
    </div>
  </div>`;
}

function head(title, description, includeMermaid = false) {
  const mermaidScript = includeMermaid ? `<script defer src="assets/vendor/mermaid/mermaid.min.js"></script>` : "";
  return `<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="${escapeHtml(description)}">
    <title>${escapeHtml(title)} | Apollo Planning 自学站</title>
    <link rel="stylesheet" href="assets/css/site.css">
    ${mermaidScript}
    <script>try{var t=localStorage.getItem("apollo-planning-theme");if(t){document.documentElement.dataset.theme=t}}catch(e){}</script>
  </head>`;
}

function shellFooter() {
  return `<footer class="site-footer"><p><strong>Apollo Planning 自学站</strong> · 代码核对基线 <code>${COMMIT}</code></p><p>教程内容只用于学习。运行环境依据 Apollo EDU PnC 安装指南整理，源码结构以固定官方提交为准。</p></footer>`;
}

function renderLessonPage(lesson, body, prev, next) {
  const prevHtml = prev
    ? `<a class="page-link prev" href="${prev.output}"><small>上一课</small><strong>${prev.number} · ${prev.title}</strong></a>`
    : `<a class="page-link prev" href="index.html"><small>返回</small><strong>课程路线图</strong></a>`;
  const nextHtml = next
    ? `<a class="page-link next" href="${next.output}"><small>下一课</small><strong>${next.number} · ${next.title}</strong></a>`
    : `<a class="page-link next" href="index.html"><small>下一步</small><strong>回到路线图</strong></a>`;

  return `<!doctype html>
<html lang="zh-CN">
${head(lesson.title, lesson.summary, body.includes("language-mermaid"))}
<body data-page="lesson" data-lesson-id="${lesson.id}">
  <a class="skip-link" href="#main-content">跳到正文</a>
  ${topbar()}
  <div class="site-layout">
    ${renderSidebar(lesson.id)}
    <main class="main" id="main-content">
      <article class="lesson-shell">
        <header class="lesson-header reveal">
          <p class="lesson-kicker">${lesson.kicker}</p>
          <h1>${lesson.title}</h1>
          <p class="lesson-summary">${lesson.summary}</p>
          <div class="lesson-meta">
            <span class="meta-pill"><strong>难度</strong>${lesson.difficulty}</span>
            <span class="meta-pill"><strong>用时</strong>${lesson.time}</span>
            <span class="meta-pill"><strong>前置</strong>${lesson.prereq}</span>
          </div>
        </header>
        <div class="lesson-content">${body}</div>
        <footer class="lesson-footer">
          <div class="complete-row">
            <p>完成实验和自测后，再标记本课完成。进度只保存在当前浏览器。</p>
            <button class="complete-button" type="button" data-complete-lesson aria-pressed="false">标记本课完成</button>
          </div>
          <nav class="lesson-pagination" aria-label="课程翻页">${prevHtml}${nextHtml}</nav>
        </footer>
      </article>
    </main>
    <aside class="toc" aria-label="本页目录"><p class="toc-label">本页目录</p><ul class="toc-list" data-toc></ul></aside>
  </div>
  <div class="mobile-scrim" aria-hidden="true"></div>
  ${searchDialog()}
  ${shellFooter()}
  <script src="assets/js/search-index.js"></script>
  <script src="assets/js/site.js"></script>
</body>
</html>`;
}
function renderRoadmap() {
  return roadmap.map(([number, title, detail, status]) => {
    const lessonHref = status === "ready" ? `lesson-${number}.html` : "";
    const label = status === "ready" ? "可学习" : status === "next" ? "下一步" : "规划中";
    const titleHtml = lessonHref ? `<a href="${lessonHref}">${title}</a>` : title;
    return `<tr data-status="${status}" data-course-unit="lesson-${number}"><td>${number}</td><td>${titleHtml}</td><td>${detail}</td><td><span class="course-status">${label}</span></td></tr>`;
  }).join("");
}

function renderHome() {
  const routeSteps = [
    ["lesson-00", "准备 Linux 环境", "虚拟机、双系统或 WSL2，先让 Apollo 跑起来。", "可学习", "is-active"],
    ["lesson-01", "建立 Apollo 地图", "知道 Planning 在哪里，以及 Scenario、Stage、Task 的关系。", "可学习", ""],
    ["lesson-02", "看懂一轮 Planning", "从输入到轨迹，只看主线，不先钻算法。", "下一步", ""],
    ["lesson-10", "深入 Scenario 与 Task", "围绕常见场景和任务读源码。", "规划中", ""],
    ["lesson-15", "补齐 C++ 生存技能", "指针、引用、类和继承，只为读懂项目服务。", "规划中", ""],
    ["lesson-20", "完成小型实战", "修改一个简单任务并运行验证。", "规划中", ""]
  ].map(([id, title, detail, state, active]) => `<li class="route-step ${active}" data-route-unit="${id}"><span class="route-node" aria-hidden="true"></span><span><strong>${title}</strong><small>${detail}</small></span><span class="route-state">${state}</span></li>`).join("");

  const body = `<main id="main-content">
    <section class="hero">
      <div class="hero-inner">
        <div class="reveal">
          <p class="hero-kicker">Apollo Planning Self-Study</p>
          <h1>先跑起来，<span>再读懂规划。</span></h1>
          <p class="hero-summary">这不是一份从函数细节开始的“劝退教程”。路线从 Linux 仿真环境出发，先建立 Apollo 与 Planning 的整体地图，再逐步进入 Scenario、Task 和读懂代码所需的 C++。</p>
          <div class="hero-actions">
            <a class="button-primary" href="lab/index.html">进入实验中心</a>
            <a class="button-secondary" href="lesson-00.html">从第 00 课开始</a>
            <a class="button-secondary" href="#roadmap">查看完整路线</a>
          </div>
        </div>
        <div class="route-board reveal" aria-label="课程路线状态">
          <ol class="route-steps">${routeSteps}</ol>
        </div>
      </div>
    </section>

    <section class="page-section">
      <figure class="lesson-illustration reveal">
        <img src="assets/images/apollo-pipeline-comic.webp" alt="Apollo 从感知、预测、规划到控制的漫画示意" loading="lazy">
        <figcaption><strong>先建立一条完整链路：</strong>感知看环境，预测猜未来，Planning 生成轨迹，Control 执行动作。后面的 21 课都围绕这条链路逐步展开。</figcaption>
      </figure>
    </section>

    <section class="page-section">
      <div class="section-intro reveal">
        <div><p class="section-kicker">Learning Model</p><h2>每一课都让学生自己走完闭环</h2></div>
        <p>先理解场景，再看源码，再做小实验，最后用自测题确认自己是否真的会了。没有老师现场补充，所有关键概念、命令和答案都写进页面。</p>
      </div>
      <div class="learning-grid">
        <article class="learning-card wide reveal">
          <div><span class="card-index">MAIN LINE</span><h3>围绕项目，而不是围绕语法书</h3><p>先看 Apollo 如何接收数据、选择场景、执行任务，再把指针、引用、类和继承放回真实源码里解释。学 C++ 的目的是读懂项目，不是先背完一门语言。</p></div>
          <ul><li>先看输入和输出，再看实现。</li><li>先看 Scenario 和 Task，再看复杂优化。</li><li>算法数学放到进阶，不影响入门过关。</li></ul>
        </article>
        <article class="learning-card reveal"><span class="symbol">01</span><div><h3>环境是入口</h3><p>虚拟机、双系统或 WSL2 只是路线差异，最终都必须能启动 Docker、AEM 和 DreamView。</p></div></article>
        <article class="learning-card reveal"><span class="symbol">02</span><div><h3>任务认知</h3><p>Scenario 决定“遇到什么情况”，Stage 决定“进行到哪一步”，Task 负责“具体做什么”。</p></div></article>
      </div>
    </section>

    <section class="page-section" id="roadmap">
      <div class="section-intro reveal">
        <div><p class="section-kicker">Course Roadmap</p><h2>从安装到小型修改</h2></div>
        <p>课程只保留必要路径。每一行都是一个自学单元，先完成可学习单元，再逐步解锁场景、任务和 C++。</p>
      </div>
      <table class="roadmap-table reveal">
        <thead><tr><th>编号</th><th>主题</th><th>你会得到什么</th><th>状态</th></tr></thead>
        <tbody>${renderRoadmap()}</tbody>
      </table>
    </section>

    <section class="page-section">
      <div class="section-intro reveal">
        <div><p class="section-kicker">Source Discipline</p><h2>环境跟指南，源码跟官方</h2></div>
        <p>安装过程依据 Apollo EDU PnC 安装指南；代码阅读以官方 <code>ApolloAuto/apollo</code> 固定提交为准。当前提交为 <code>${COMMIT}</code>。</p>
      </div>
      <div class="callout warning reveal"><strong>开始前请记住</strong><p>Apollo 仿真运行在 Linux 上。Windows 用户必须先准备 Ubuntu 虚拟机、双系统或 WSL2；WSL2 虽然方便，但 Docker、GUI 和端口兼容性需要单独验证。</p></div>
      <div class="callout reveal"><strong>建议的自学顺序</strong><p>先完成第 00 课安装检查，再读第 01 课全景地图。环境没有跑通时可以做静态阅读，但不要假装完成运行实验。</p></div>
    </section>
  </main>`;

  return `<!doctype html>
<html lang="zh-CN">
${head("Apollo Planning 小白自学路线", "从 Linux 仿真环境出发，学习 Apollo Planning 架构、Scenario、Task 与 C++ 基础。")}
<body data-page="home">
  <a class="skip-link" href="#main-content">跳到正文</a>
  ${topbar()}
  ${body}
  <div class="mobile-scrim" aria-hidden="true"></div>
  ${searchDialog()}
  ${shellFooter()}
  <script src="assets/js/search-index.js"></script>
  <script src="assets/js/site.js"></script>
</body>
</html>`;
}

async function build() {
  await fs.mkdir(assetsDir, { recursive: true });
  const searchIndex = [];
  const builtLessons = [];

  for (const lesson of lessons) {
    const markdown = await fs.readFile(path.join(root, lesson.source), "utf8");
    const markdownBody = markdown.replace(/^# .+\r?\n/, "");
    const html = addHeadingIds(marked.parse(markdownBody));
    builtLessons.push({ ...lesson, html });
    searchIndex.push({
      title: `第 ${lesson.number} 课 · ${lesson.title}`,
      href: lesson.output,
      text: lesson.summary,
      keywords: lesson.keywords
    });
    const headingPattern = /^(#{2,3})\s+(.+)$/gm;
    for (const match of markdown.matchAll(headingPattern)) {
      const heading = match[2].replace(/[`*_]/g, "").trim();
      searchIndex.push({
        title: `第 ${lesson.number} 课 · ${heading}`,
        href: `${lesson.output}#${slugify(heading)}`,
        text: lesson.title,
        keywords: lesson.keywords
      });
    }
  }

  await fs.writeFile(path.join(siteDir, "index.html"), renderHome(), "utf8");

  for (let index = 0; index < builtLessons.length; index += 1) {
    const lesson = builtLessons[index];
    const prev = builtLessons[index - 1];
    const next = builtLessons[index + 1];
    await fs.writeFile(path.join(siteDir, lesson.output), renderLessonPage(lesson, lesson.html, prev, next), "utf8");
  }

  searchIndex.push(
    {
      title: "实验中心 · 城市道路自动驾驶综合仿真实验",
      href: "lab/index.html",
      text: "Apollo Claw 四技能、MVP 范围和实验路线",
      keywords: "实验中心 Apollo Claw MVP 人行道 避让"
    },
    {
      title: "实验 · 人行道避让综合实验",
      href: "lab/crosswalk.html",
      text: "环境检查、场景运行、代码定位、录包、评分与优化闭环",
      keywords: "人行道 避让 apollo-env apollo-dev apollo-test apollo-eval"
    },
    {
      title: "实验报告 · 人行道避让优化前后对比",
      href: "lab/report.html",
      text: "TTC、纵向加速度、Jerk、急刹次数和场景得分对比",
      keywords: "实验报告 评分 TTC Jerk 急刹"
    }
  );

  const searchFile = `window.COURSE_INDEX = ${JSON.stringify(searchIndex, null, 2)};\n`;
  await fs.writeFile(path.join(assetsDir, "js", "search-index.js"), searchFile, "utf8");
  console.log(`Built ${builtLessons.length + 1} HTML pages and ${searchIndex.length} search entries.`);
}

await build();
