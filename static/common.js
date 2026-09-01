/* 用途：前端公共 API 与工具；分层：接入层前端
 * 维护：v1.3 起支持按文章目录改写相对媒体路径 → /media/...
 *       v1.3.6 修复 marked 已 percent-encode 中文路径后再次 encode 导致双重编码 404
 *       v1.3.7 白天/暗夜主题切换（localStorage: moji-theme）
 *       v1.3.8 主题开关改为太阳/月亮图标
 */
(() => {
  "use strict";

  const THEME_KEY = "moji-theme";

  function getTheme() {
    try {
      return localStorage.getItem(THEME_KEY) === "night" ? "night" : "day";
    } catch {
      return "day";
    }
  }

  function syncThemeToggles(theme) {
    const title = theme === "night" ? "切换为白天模式" : "切换为暗夜模式";
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("title", title);
      btn.setAttribute("aria-label", title);
      btn.setAttribute("aria-pressed", theme === "night" ? "true" : "false");
    });
  }

  function applyTheme(theme) {
    const next = theme === "night" ? "night" : "day";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* ignore quota / private mode */
    }
    syncThemeToggles(next);
    return next;
  }

  function toggleTheme() {
    return applyTheme(getTheme() === "night" ? "day" : "night");
  }

  function initTheme() {
    applyTheme(getTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      if (btn.dataset.themeBound) return;
      btn.dataset.themeBound = "1";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        toggleTheme();
      });
    });
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.error || `HTTP ${res.status}`;
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function formatTime(ms) {
    if (!ms) return "";
    const d = new Date(ms);
    return d.toLocaleString("zh-CN", { hour12: false });
  }

  /** 是否为外链 / 已挂载媒体 / data URI，无需改写 */
  function isAbsoluteOrExternal(url) {
    if (!url) return true;
    const u = String(url).trim();
    if (!u) return true;
    if (/^(https?:|data:|blob:|mailto:|tel:|#)/i.test(u)) return true;
    if (u.startsWith("//")) return true;
    if (u.startsWith("/media/")) return true;
    return false;
  }

  /** marked 会对中文 URL 先做 percent-encode；还原后再统一 encode，避免 %25xx 双重编码 */
  function safeDecodeURIComponent(value) {
    const s = String(value || "");
    try {
      return decodeURIComponent(s);
    } catch {
      return s;
    }
  }

  /**
   * 将相对路径解析到 /media/{文章目录}/...
   * articleDir：相对 posts_dir 的目录（即 category），空=根
   */
  function joinMediaPath(articleDir, rel) {
    const raw = safeDecodeURIComponent(String(rel || "").replace(/\\/g, "/").trim());
    const baseParts = String(articleDir || "")
      .replace(/\\/g, "/")
      .split("/")
      .filter((p) => p && p !== ".");
    const relParts = raw.replace(/^\.\/+/, "").split("/");
    const stack = baseParts.slice();
    for (const part of relParts) {
      if (!part || part === ".") continue;
      if (part === "..") {
        if (stack.length) stack.pop();
        continue;
      }
      stack.push(safeDecodeURIComponent(part));
    }
    return "/media/" + stack.map(encodeURIComponent).join("/");
  }

  function rewriteMediaUrls(html, articleDir) {
    if (!html) return html;
    const wrap = document.createElement("div");
    wrap.innerHTML = html;
    wrap.querySelectorAll("img[src], a[href], source[src], video[src]").forEach((el) => {
      const attr = el.hasAttribute("src") ? "src" : "href";
      const val = el.getAttribute(attr);
      if (isAbsoluteOrExternal(val)) return;
      // 以 / 开头但非 /media 的站点路径：不改写（避免误伤）
      if (String(val).trim().startsWith("/")) return;
      el.setAttribute(attr, joinMediaPath(articleDir, val));
    });
    return wrap.innerHTML;
  }

  /**
   * @param {string} text Markdown
   * @param {{ articleDir?: string }} [opts] articleDir=文章相对目录（category）
   */
  function renderMarkdown(text, opts) {
    const raw = typeof marked !== "undefined" ? marked.parse(text || "") : text || "";
    const clean =
      typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(raw) : raw;
    const articleDir = (opts && opts.articleDir) || "";
    return rewriteMediaUrls(clean, articleDir);
  }

  window.Moji = {
    api,
    formatTime,
    renderMarkdown,
    joinMediaPath,
    rewriteMediaUrls,
    getTheme,
    applyTheme,
    toggleTheme,
    initTheme,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTheme);
  } else {
    initTheme();
  }
})();
