(() => {
  "use strict";

  const els = {
    list: document.getElementById("postList"),
    title: document.getElementById("titleInput"),
    category: document.getElementById("categoryInput"),
    tags: document.getElementById("tagsInput"),
    editor: document.getElementById("editor"),
    preview: document.getElementById("preview"),
    saveStatus: document.getElementById("saveStatus"),
    wordCount: document.getElementById("wordCount"),
    searchInput: document.getElementById("searchInput"),
    tagFilter: document.getElementById("tagFilter"),
    categoryFilter: document.getElementById("categoryFilter"),
    btnNew: document.getElementById("btnNew"),
    btnSave: document.getElementById("btnSave"),
    btnDelete: document.getElementById("btnDelete"),
    btnLogout: document.getElementById("btnLogout"),
  };

  let posts = [];
  let activeId = null;
  let dirty = false;
  let saveTimer = null;
  let searchTimer = null;

  async function ensureAuth() {
    const me = await Moji.api("/api/auth/me");
    if (!me.authenticated) {
      location.replace("/login.html");
      throw new Error("unauthorized");
    }
  }

  function renderPreview() {
    els.preview.innerHTML = Moji.renderMarkdown(els.editor.value, {
      articleDir: (els.category.value || "").trim(),
    });
    els.wordCount.textContent = `${(els.editor.value || "").length} 字`;
  }

  function markDirty() {
    dirty = true;
    els.saveStatus.textContent = "未保存";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveCurrent(false), 800);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function tagsToInput(tags) {
    return (tags || []).join(", ");
  }

  function tagsFromInput() {
    return (els.tags.value || "")
      .split(/[,，;；]+/)
      .map((t) => t.trim())
      .filter(Boolean);
  }

  function buildQuery() {
    const params = new URLSearchParams();
    const q = (els.searchInput.value || "").trim();
    const tag = els.tagFilter.value || "";
    const category = els.categoryFilter.value || "";
    if (q) params.set("q", q);
    if (tag) params.set("tag", tag);
    if (category) params.set("category", category);
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  function flattenCategories(node, acc) {
    if (node.path) acc.push(node.path);
    (node.children || []).forEach((c) => flattenCategories(c, acc));
    return acc;
  }

  function renderList() {
    els.list.innerHTML = posts
      .map((p) => {
        const active = p.id === activeId ? "active" : "";
        const cat = p.category || "根目录";
        return `<li><button type="button" class="${active}" data-id="${p.id}">
          <span class="t">${escapeHtml(p.title) || "无标题"}</span>
          <span class="m">${escapeHtml(cat)} · ${Moji.formatTime(p.updatedAt)}</span>
        </button></li>`;
      })
      .join("");
  }

  async function loadTags() {
    const data = await Moji.api("/api/tags/all");
    const current = els.tagFilter.value;
    els.tagFilter.innerHTML = '<option value="">全部标签</option>';
    (data.tags || []).forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      els.tagFilter.appendChild(opt);
    });
    if (current && [...els.tagFilter.options].some((o) => o.value === current)) {
      els.tagFilter.value = current;
    }
  }

  async function loadCategories() {
    const data = await Moji.api("/api/categories/all");
    const current = els.categoryFilter.value;
    const paths = flattenCategories(data.tree, []);
    els.categoryFilter.innerHTML = '<option value="">全部目录</option>';
    paths.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      els.categoryFilter.appendChild(opt);
    });
    if (current && [...els.categoryFilter.options].some((o) => o.value === current)) {
      els.categoryFilter.value = current;
    }
  }

  async function loadList() {
    posts = await Moji.api(`/api/posts/all${buildQuery()}`);
    renderList();
  }

  async function selectPost(id) {
    if (dirty && activeId) {
      await saveCurrent(false);
    }
    const post = await Moji.api(`/api/posts/${encodeURIComponent(id)}`);
    activeId = post.id;
    els.title.value = post.title || "";
    els.category.value = post.category || "";
    els.tags.value = tagsToInput(post.tags);
    els.editor.value = post.content || "";
    dirty = false;
    els.saveStatus.textContent = "已加载";
    renderPreview();
    renderList();
  }

  async function saveCurrent(showAlert) {
    if (!activeId && !els.title.value.trim() && !els.editor.value.trim()) {
      return;
    }
    const payload = {
      title: els.title.value.trim() || "无标题",
      content: els.editor.value || "",
      tags: tagsFromInput(),
      category: (els.category.value || "").trim(),
    };
    try {
      let saved;
      if (!activeId) {
        saved = await Moji.api("/api/posts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        activeId = saved.id;
      } else {
        saved = await Moji.api(`/api/posts/${encodeURIComponent(activeId)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      }
      dirty = false;
      els.category.value = saved.category || "";
      els.saveStatus.textContent = "已保存 " + Moji.formatTime(saved.updatedAt);
      await loadTags();
      await loadCategories();
      await loadList();
      renderList();
      if (showAlert) els.saveStatus.textContent = "保存成功";
    } catch (e) {
      els.saveStatus.textContent = "保存失败：" + e.message;
    }
  }

  async function createNew() {
    if (dirty) await saveCurrent(false);
    const cat = els.categoryFilter.value || "";
    const created = await Moji.api("/api/posts", {
      method: "POST",
      body: JSON.stringify({
        title: "新文章",
        content: "",
        tags: [],
        category: cat,
      }),
    });
    await loadTags();
    await loadCategories();
    await loadList();
    await selectPost(created.id);
  }

  async function deleteCurrent() {
    if (!activeId) return;
    if (!confirm("确认删除该文章？不可恢复。")) return;
    await Moji.api(`/api/posts/${encodeURIComponent(activeId)}`, { method: "DELETE" });
    activeId = null;
    els.title.value = "";
    els.category.value = "";
    els.tags.value = "";
    els.editor.value = "";
    dirty = false;
    renderPreview();
    await loadTags();
    await loadCategories();
    await loadList();
    if (posts[0]) await selectPost(posts[0].id);
    else els.saveStatus.textContent = "已删除";
  }

  function scheduleSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadList().catch(console.error), 300);
  }

  els.list.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-id]");
    if (btn) selectPost(btn.dataset.id).catch(alert);
  });
  els.title.addEventListener("input", markDirty);
  els.category.addEventListener("input", () => {
    markDirty();
    renderPreview();
  });
  els.tags.addEventListener("input", markDirty);
  els.editor.addEventListener("input", () => {
    markDirty();
    renderPreview();
  });
  els.searchInput.addEventListener("input", scheduleSearch);
  els.tagFilter.addEventListener("change", () => loadList().catch(console.error));
  els.categoryFilter.addEventListener("change", () => loadList().catch(console.error));
  els.btnSave.addEventListener("click", () => saveCurrent(true));
  els.btnNew.addEventListener("click", () => createNew().catch(alert));
  els.btnDelete.addEventListener("click", () => deleteCurrent().catch(alert));
  els.btnLogout.addEventListener("click", async () => {
    await Moji.api("/api/auth/logout", { method: "POST" });
    location.replace("/");
  });

  (async () => {
    await ensureAuth();
    await loadTags();
    await loadCategories();
    const openId = new URLSearchParams(location.search).get("id");
    if (openId) {
      // 深链打开指定文章：清空筛选，避免列表过滤导致侧栏看不到目标
      els.searchInput.value = "";
      els.tagFilter.value = "";
      els.categoryFilter.value = "";
      await loadList();
      try {
        await selectPost(openId);
        return;
      } catch (e) {
        console.warn("深链文章加载失败", e);
      }
    }
    await loadList();
    if (posts[0]) await selectPost(posts[0].id);
    else await createNew();
  })().catch((e) => {
    if (e.message !== "unauthorized") alert(e.message);
  });
})();
