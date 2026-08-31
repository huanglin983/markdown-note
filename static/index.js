(() => {
  "use strict";

  const listEl = document.getElementById("postList");
  const emptyEl = document.getElementById("empty");
  const linkEditor = document.getElementById("linkEditor");
  const searchInput = document.getElementById("searchInput");
  const tagFilter = document.getElementById("tagFilter");
  const catTreeEl = document.getElementById("catTree");

  const floatReader = document.getElementById("floatReader");
  const floatTabs = document.getElementById("floatTabs");
  const floatBody = document.getElementById("floatBody");
  const floatBackdrop = document.getElementById("floatBackdrop");
  const btnFloatEdit = document.getElementById("btnFloatEdit");
  const btnFloatCloseAll = document.getElementById("btnFloatCloseAll");
  const btnFloatMinimize = document.getElementById("btnFloatMinimize");

  let debounceTimer = null;
  let activeCategory = "";
  let isAuthor = false;

  /** @type {{ id: string, title: string, html: string, meta: string, loading?: boolean, error?: string }[]} */
  let tabs = [];
  let activeTabId = "";

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderTags(tags) {
    if (!tags || !tags.length) return "";
    return tags
      .map((t) => `<span class="tag-chip">${escapeHtml(t)}</span>`)
      .join("");
  }

  function buildQuery() {
    const params = new URLSearchParams();
    const q = (searchInput.value || "").trim();
    const tag = tagFilter.value || "";
    if (q) params.set("q", q);
    if (tag) params.set("tag", tag);
    if (activeCategory) params.set("category", activeCategory);
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  function renderTreeNode(node, depth) {
    const active = node.path === activeCategory ? " active" : "";
    const label = node.path === "" ? "全部" : node.name;
    let html = `<button type="button" class="cat-node${active}" data-path="${escapeHtml(
      node.path
    )}" style="padding-left:${8 + depth * 14}px">
      <span class="cat-name">${escapeHtml(label)}</span>
      <span class="cat-count">${node.count}</span>
    </button>`;
    (node.children || []).forEach((child) => {
      html += renderTreeNode(child, depth + 1);
    });
    return html;
  }

  async function loadTree() {
    try {
      const data = await Moji.api("/api/categories");
      catTreeEl.innerHTML = renderTreeNode(data.tree, 0);
    } catch {
      catTreeEl.innerHTML = '<div class="empty" style="padding:12px">目录加载失败</div>';
    }
  }

  async function loadTags() {
    try {
      const data = await Moji.api("/api/tags");
      const current = tagFilter.value;
      tagFilter.innerHTML = '<option value="">全部标签</option>';
      (data.tags || []).forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        tagFilter.appendChild(opt);
      });
      if (current && [...tagFilter.options].some((o) => o.value === current)) {
        tagFilter.value = current;
      }
    } catch {
      /* ignore */
    }
  }

  async function loadPosts() {
    try {
      const posts = await Moji.api(`/api/posts${buildQuery()}`);
      if (!posts.length) {
        listEl.innerHTML = "";
        emptyEl.hidden = false;
        emptyEl.textContent =
          searchInput.value.trim() || tagFilter.value || activeCategory
            ? "没有匹配的文章"
            : "暂无文章";
        return;
      }
      emptyEl.hidden = true;
      listEl.innerHTML = posts
        .map((p) => {
          const cat =
            p.category
              ? `<span class="cat-chip">${escapeHtml(p.category)}</span>`
              : `<span class="cat-chip muted">根目录</span>`;
          return `
        <li>
          <a class="post-item" href="/post.html?id=${encodeURIComponent(p.id)}" data-open-tab="${escapeHtml(p.id)}" data-title="${escapeHtml(p.title)}">
            <h3>${escapeHtml(p.title)}</h3>
            <div class="meta">
              ${cat}
              更新于 ${Moji.formatTime(p.updatedAt)}
              ${renderTags(p.tags)}
            </div>
          </a>
        </li>`;
        })
        .join("");
    } catch (e) {
      emptyEl.hidden = false;
      emptyEl.textContent = "加载失败：" + e.message;
    }
  }

  function showFloat() {
    floatReader.hidden = false;
    floatReader.setAttribute("aria-hidden", "false");
    document.body.classList.add("float-reader-open");
  }

  function hideFloat() {
    floatReader.hidden = true;
    floatReader.setAttribute("aria-hidden", "true");
    document.body.classList.remove("float-reader-open");
  }

  function renderFloatChrome() {
    if (!tabs.length) {
      floatTabs.innerHTML = "";
      floatBody.innerHTML = "";
      if (btnFloatEdit) btnFloatEdit.hidden = true;
      hideFloat();
      return;
    }
    showFloat();
    floatTabs.innerHTML = tabs
      .map((t) => {
        const active = t.id === activeTabId ? " active" : "";
        return `<button type="button" class="float-tab${active}" role="tab" data-tab-id="${escapeHtml(
          t.id
        )}" title="${escapeHtml(t.title)}">
          <span class="float-tab-title">${escapeHtml(t.title) || "无标题"}</span>
          <span class="float-tab-close" data-close-id="${escapeHtml(t.id)}" title="关闭">×</span>
        </button>`;
      })
      .join("");

    const cur = tabs.find((t) => t.id === activeTabId) || tabs[0];
    if (!cur) return;

    if (btnFloatEdit) {
      if (isAuthor && cur.id && !cur.loading && !cur.error) {
        btnFloatEdit.href = `/editor.html?id=${encodeURIComponent(cur.id)}`;
        btnFloatEdit.hidden = false;
      } else {
        btnFloatEdit.hidden = true;
      }
    }

    if (cur.loading) {
      floatBody.innerHTML = '<div class="float-reader-status">加载中…</div>';
      return;
    }
    if (cur.error) {
      floatBody.innerHTML = `<div class="float-reader-status error">${escapeHtml(cur.error)}</div>`;
      return;
    }
    floatBody.innerHTML = `
      <article class="article float-article">
        <h1>${escapeHtml(cur.title)}</h1>
        <div class="meta">${cur.meta}</div>
        <div class="markdown-body">${cur.html}</div>
      </article>`;
  }

  async function openTab(postId, titleHint) {
    if (!postId) return;
    const existing = tabs.find((t) => t.id === postId);
    if (existing) {
      activeTabId = postId;
      renderFloatChrome();
      return;
    }
    const tab = {
      id: postId,
      title: titleHint || "加载中…",
      html: "",
      meta: "",
      loading: true,
    };
    tabs.push(tab);
    activeTabId = postId;
    renderFloatChrome();

    try {
      const post = await Moji.api(`/api/posts/${encodeURIComponent(postId)}`);
      const tagHtml = renderTags(post.tags);
      tab.title = post.title || titleHint || postId;
      tab.meta = `${
        post.category
          ? `<span class="cat-chip">${escapeHtml(post.category)}</span>`
          : ""
      }更新于 ${Moji.formatTime(post.updatedAt)} ${tagHtml}`;
      tab.html = Moji.renderMarkdown(post.content || "", {
        articleDir: post.category || "",
      });
      tab.loading = false;
      tab.error = "";
    } catch (e) {
      tab.loading = false;
      tab.error = e.status === 404 ? "文章不存在" : "加载失败：" + (e.message || "");
    }
    if (activeTabId === postId) renderFloatChrome();
  }

  function closeTab(postId) {
    const idx = tabs.findIndex((t) => t.id === postId);
    if (idx < 0) return;
    tabs.splice(idx, 1);
    if (activeTabId === postId) {
      activeTabId = tabs[idx] ? tabs[idx].id : tabs[idx - 1] ? tabs[idx - 1].id : "";
    }
    renderFloatChrome();
  }

  function closeAllTabs() {
    tabs = [];
    activeTabId = "";
    renderFloatChrome();
  }

  function scheduleReload() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(loadPosts, 300);
  }

  async function init() {
    try {
      const me = await Moji.api("/api/auth/me");
      if (me.authenticated) {
        isAuthor = true;
        linkEditor.textContent = "工作台";
        linkEditor.href = "/editor.html";
      }
    } catch {
      /* ignore */
    }

    await loadTree();
    await loadTags();
    await loadPosts();
  }

  catTreeEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-path]");
    if (!btn) return;
    activeCategory = btn.dataset.path || "";
    loadTree();
    loadPosts();
  });
  searchInput.addEventListener("input", scheduleReload);
  tagFilter.addEventListener("change", loadPosts);

  listEl.addEventListener("click", (ev) => {
    const link = ev.target.closest("a[data-open-tab]");
    if (!link) return;
    // Ctrl/Cmd/中键仍允许浏览器新开；普通点击页内浮动打开
    if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button === 1) return;
    ev.preventDefault();
    openTab(link.getAttribute("data-open-tab"), link.getAttribute("data-title") || "");
  });

  floatTabs.addEventListener("click", (ev) => {
    const closer = ev.target.closest("[data-close-id]");
    if (closer) {
      ev.stopPropagation();
      closeTab(closer.getAttribute("data-close-id"));
      return;
    }
    const tabBtn = ev.target.closest("[data-tab-id]");
    if (tabBtn) {
      activeTabId = tabBtn.getAttribute("data-tab-id") || "";
      renderFloatChrome();
    }
  });

  btnFloatCloseAll.addEventListener("click", closeAllTabs);
  btnFloatMinimize.addEventListener("click", hideFloat);
  floatBackdrop.addEventListener("click", hideFloat);

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !floatReader.hidden) {
      hideFloat();
    }
  });

  init();
})();
