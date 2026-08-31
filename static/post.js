(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const id = params.get("id");
  const article = document.getElementById("article");
  const errorEl = document.getElementById("error");
  const btnEdit = document.getElementById("btnEdit");

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function showEditIfAuthed(postId) {
    if (!btnEdit || !postId) return;
    try {
      const me = await Moji.api("/api/auth/me");
      if (!me.authenticated) return;
      btnEdit.href = `/editor.html?id=${encodeURIComponent(postId)}`;
      btnEdit.hidden = false;
    } catch {
      /* 未登录或鉴权失败：不展示编辑入口 */
    }
  }

  async function init() {
    if (!id) {
      errorEl.textContent = "缺少文章 id";
      return;
    }
    try {
      const post = await Moji.api(`/api/posts/${encodeURIComponent(id)}`);
      document.title = `${post.title} · 墨记`;
      document.getElementById("title").textContent = post.title;
      const tagHtml = (post.tags || [])
        .map((t) => `<span class="tag-chip">${escapeHtml(t)}</span>`)
        .join("");
      document.getElementById("meta").innerHTML =
        `${post.category ? `<span class="cat-chip">${escapeHtml(post.category)}</span>` : ""}更新于 ${Moji.formatTime(post.updatedAt)} ${tagHtml}`;
      document.getElementById("content").innerHTML = Moji.renderMarkdown(post.content, {
        articleDir: post.category || "",
      });
      article.hidden = false;
      errorEl.hidden = true;
      await showEditIfAuthed(post.id);
    } catch (e) {
      errorEl.textContent = e.status === 404 ? "文章不存在" : "加载失败：" + e.message;
    }
  }

  init();
})();
