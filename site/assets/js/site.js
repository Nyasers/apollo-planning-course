(function () {
  "use strict";

  const root = document.documentElement;
  const body = document.body;
  const storageKey = "apollo-planning-course-v1";

  function readStore() {
    try { return JSON.parse(localStorage.getItem(storageKey) || "{}"); }
    catch (error) { return {}; }
  }
  function writeStore(value) { localStorage.setItem(storageKey, JSON.stringify(value)); }

  const store = readStore();
  store.completed = store.completed || {};
  store.checklists = store.checklists || {};

  function mermaidVariables(theme) {
    const dark = theme === "dark";
    return {
      background: dark ? "#17232c" : "#ffffff",
      primaryColor: dark ? "#152b52" : "#e7efff",
      primaryTextColor: dark ? "#e8f0f3" : "#14202a",
      primaryBorderColor: dark ? "#6b9cff" : "#0b5cff",
      lineColor: dark ? "#b8c5cc" : "#4b5965",
      secondaryColor: dark ? "#3d3015" : "#fff3d6",
      tertiaryColor: dark ? "#17352c" : "#e0f2eb",
      fontFamily: "Noto Sans SC, Source Han Sans SC, Microsoft YaHei, sans-serif"
    };
  }

  function prepareMermaidNodes() {
    document.querySelectorAll(".lesson-content pre > code.language-mermaid").forEach((code) => {
      const pre = code.parentElement;
      if (!pre) return;
      const diagram = document.createElement("div");
      diagram.className = "mermaid";
      diagram.dataset.source = code.textContent;
      diagram.textContent = code.textContent;
      pre.replaceWith(diagram);
    });
  }

  async function renderMermaid(force = false) {
    if (!window.mermaid) return;
    prepareMermaidNodes();
    const nodes = Array.from(document.querySelectorAll(".lesson-content .mermaid"));
    if (!nodes.length) return;

    const nextTheme = root.dataset.theme;
    nodes.forEach((node) => {
      if (!force && node.dataset.renderedTheme === nextTheme) return;
      node.removeAttribute("data-processed");
      node.innerHTML = node.dataset.source || node.textContent;
    });

    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      themeVariables: mermaidVariables(nextTheme),
      flowchart: { curve: "basis", htmlLabels: true, useMaxWidth: true },
      sequence: { useMaxWidth: true },
      state: { useMaxWidth: true },
      class: { useMaxWidth: true }
    });

    for (const node of nodes) {
      if (!force && node.dataset.renderedTheme === nextTheme) continue;
      try {
        await window.mermaid.run({ nodes: [node] });
        node.dataset.renderedTheme = nextTheme;
        node.classList.remove("mermaid-error");
      } catch (error) {
        node.classList.add("mermaid-error");
        node.textContent = "Mermaid 图渲染失败：" + error.message;
        console.error(error);
      }
    }
  }

  function setTheme(theme) {
    root.dataset.theme = theme;
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(theme === "dark"));
      button.title = theme === "dark" ? "切换到浅色主题" : "切换到深色主题";
    });
  }

  const savedTheme = localStorage.getItem("apollo-planning-theme");
  setTheme(savedTheme || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem("apollo-planning-theme", next);
      setTheme(next);
      window.setTimeout(() => renderMermaid(true), 50);
    });
  });

  const sidebar = document.querySelector(".sidebar");
  const menuButton = document.querySelector("[data-menu-toggle]");
  const scrim = document.querySelector(".mobile-scrim");

  function closeMenu() {
    if (!sidebar) return;
    sidebar.classList.remove("is-open");
    if (scrim) scrim.classList.remove("is-open");
    if (menuButton) menuButton.setAttribute("aria-expanded", "false");
  }

  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      const open = sidebar.classList.toggle("is-open");
      if (scrim) scrim.classList.toggle("is-open", open);
      menuButton.setAttribute("aria-expanded", String(open));
    });
  }
  if (scrim) scrim.addEventListener("click", closeMenu);

  function updateProgressUI() {
    function getUnitId(el) { return el.dataset.courseUnit || el.dataset.lessonId; }
    const lessonLinks = Array.from(document.querySelectorAll("[data-course-unit], .nav-link[data-lesson-id]"));
    const total = lessonLinks.length;
    const completed = lessonLinks.filter((link) => store.completed[getUnitId(link)]).length;
    const percent = total ? Math.round((completed / total) * 100) : 0;

    document.querySelectorAll("[data-progress-fill]").forEach((el) => { el.style.width = percent + "%"; });
    document.querySelectorAll("[data-progress-value]").forEach((el) => { el.textContent = percent + "%"; });
    document.querySelectorAll("[data-progress-count]").forEach((el) => { el.textContent = completed + " / " + total; });
    lessonLinks.forEach((link) => { link.classList.toggle("is-complete", Boolean(store.completed[getUnitId(link)])); });

    const routeSteps = Array.from(document.querySelectorAll("[data-route-unit]"));
    let nextRouteMarked = false;
    routeSteps.forEach((step) => {
      const done = Boolean(store.completed[step.dataset.routeUnit]);
      const active = !done && !nextRouteMarked;
      if (active) nextRouteMarked = true;
      step.classList.toggle("is-done", done);
      step.classList.toggle("is-active", active);
      const state = step.querySelector(".route-state");
      if (state) state.textContent = done ? "已完成" : active ? "下一步" : "可学习";
    });

    const currentId = body.dataset.lessonId;
    const completeButton = document.querySelector("[data-complete-lesson]");
    if (completeButton && currentId) {
      const done = Boolean(store.completed[currentId]);
      completeButton.classList.toggle("is-complete", done);
      completeButton.textContent = done ? "已完成本课" : "标记本课完成";
      completeButton.setAttribute("aria-pressed", String(done));
    }
  }

  const completeButton = document.querySelector("[data-complete-lesson]");
  if (completeButton && body.dataset.lessonId) {
    completeButton.addEventListener("click", () => {
      const id = body.dataset.lessonId;
      store.completed[id] = !store.completed[id];
      writeStore(store);
      updateProgressUI();
    });
  }

  document.querySelectorAll(".lesson-content input[type='checkbox']").forEach((checkbox, index) => {
    const key = (body.dataset.lessonId || "page") + ":" + index;
    checkbox.disabled = false;
    checkbox.checked = Boolean(store.checklists[key]);
    checkbox.addEventListener("change", () => {
      store.checklists[key] = checkbox.checked;
      writeStore(store);
    });
  });

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true; } catch (error) { /* fall through */ }
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }

  document.querySelectorAll(".lesson-content pre").forEach((pre) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-code";
    button.textContent = "复制";
    button.addEventListener("click", async () => {
      const code = pre.querySelector("code");
      if (!code) return;
      const copied = await copyText(code.innerText);
      button.textContent = copied ? "已复制" : "复制失败";
      window.setTimeout(() => { button.textContent = "复制"; }, 1200);
    });
    pre.appendChild(button);
  });

  const toc = document.querySelector("[data-toc]");
  if (toc) {
    const headings = Array.from(document.querySelectorAll(".lesson-content h2, .lesson-content h3"));
    headings.forEach((heading, index) => {
      if (!heading.id) heading.id = "section-" + (index + 1);
      const link = document.createElement("a");
      link.className = "toc-link" + (heading.tagName === "H3" ? " level-3" : "");
      link.href = "#" + heading.id;
      link.textContent = heading.textContent;
      const item = document.createElement("li");
      item.appendChild(link);
      toc.appendChild(item);
    });

    const tocLinks = Array.from(toc.querySelectorAll(".toc-link"));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      tocLinks.forEach((link) => link.classList.toggle("is-active", link.getAttribute("href") === "#" + visible.target.id));
    }, { rootMargin: "-18% 0px -68% 0px", threshold: [0, 1] });
    headings.forEach((heading) => observer.observe(heading));
  }

  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    const revealTargets = Array.from(document.querySelectorAll(".reveal, .lab-hero, .lab-section"));
    revealTargets.forEach((el) => {
      el.classList.add("reveal");
      revealObserver.observe(el);
    });
  } else {
    document.querySelectorAll(".reveal, .lab-hero, .lab-section").forEach((el) => el.classList.add("reveal", "is-visible"));
  }

  const searchDialog = document.querySelector("[data-search-dialog]");
  const searchInput = document.querySelector("[data-search-input]");
  const searchResults = document.querySelector("[data-search-results]");
  const searchButtons = Array.from(document.querySelectorAll("[data-search-open]"));

  function renderSearch(query) {
    if (!searchResults) return;
    const normalized = query.trim().toLowerCase();
    const data = Array.isArray(window.COURSE_INDEX) ? window.COURSE_INDEX : [];
    const matches = data.filter((item) => {
      if (!normalized) return true;
      return (item.title + " " + (item.text || "") + " " + (item.keywords || "")).toLowerCase().includes(normalized);
    }).slice(0, 14);

    if (!matches.length) {
      searchResults.innerHTML = '<div class="search-empty">没有匹配内容。试试“Task”“指针”或“WSL”。</div>';
      return;
    }
    searchResults.innerHTML = matches.map((item) =>
      '<a class="search-result" href="' + item.href + '"><strong>' + item.title +
      "</strong><span>" + (item.text || item.keywords || "") + "</span></a>"
    ).join("");
  }

  function openSearch() {
    if (!searchDialog || !searchInput) return;
    searchDialog.classList.add("is-open");
    searchDialog.setAttribute("aria-hidden", "false");
    renderSearch("");
    window.setTimeout(() => searchInput.focus(), 20);
  }
  function closeSearch() {
    if (!searchDialog) return;
    searchDialog.classList.remove("is-open");
    searchDialog.setAttribute("aria-hidden", "true");
  }

  searchButtons.forEach((button) => button.addEventListener("click", openSearch));
  if (searchDialog) searchDialog.addEventListener("click", (event) => { if (event.target === searchDialog) closeSearch(); });
  if (searchInput) searchInput.addEventListener("input", (event) => renderSearch(event.target.value));
  window.addEventListener("keydown", (event) => {
    const isTyping = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearch();
    } else if (event.key === "/" && !isTyping) {
      event.preventDefault();
      openSearch();
    } else if (event.key === "Escape") {
      closeSearch();
      closeMenu();
    }
  });

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", () => renderMermaid(false));
  } else {
    renderMermaid(false);
  }

  updateProgressUI();
})();
