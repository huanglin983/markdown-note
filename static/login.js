(() => {
  "use strict";

  const form = document.getElementById("loginForm");
  const errorEl = document.getElementById("error");

  (async () => {
    try {
      const me = await Moji.api("/api/auth/me");
      if (me.authenticated) location.replace("/editor.html");
    } catch {
      /* ignore */
    }
  })();

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    errorEl.textContent = "";
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    try {
      await Moji.api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      location.replace("/editor.html");
    } catch (e) {
      errorEl.textContent = e.message || "登录失败";
    }
  });
})();
