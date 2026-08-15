(function (global) {
  const NAV = [
    { href: "/live", id: "live", label: "Güzergâh" },
    { href: "/detect", id: "detect", label: "Tespit" },
    { href: "/map", id: "map", label: "Harita" },
  ];

  function mountNav(active) {
    const el = document.getElementById("nav");
    if (!el) return;
    el.innerHTML = NAV.map(
      (item) =>
        `<a href="${item.href}" class="${item.id === active ? "active" : ""}">${item.label}</a>`
    ).join("");
  }

  // Operator credential. Set once per browser, e.g. from the console:
  //   CV.setToken("<jwt from POST /api/auth/login>")
  // Deployments with no API key and no JWT secret need none.
  const TOKEN_KEY = "cv_token";

  function getToken() {
    const fromUrl = qs("token");
    if (fromUrl) {
      try {
        localStorage.setItem(TOKEN_KEY, fromUrl);
      } catch (_) {}
      return fromUrl;
    }
    try {
      return localStorage.getItem(TOKEN_KEY) || "";
    } catch (_) {
      return "";
    }
  }

  function setToken(token) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (_) {}
  }

  async function j(url, opts) {
    const options = Object.assign({}, opts);
    const token = getToken();
    if (token) {
      options.headers = Object.assign({}, options.headers, {
        Authorization: "Bearer " + token,
      });
    }
    const r = await fetch(url, options);
    if (r.status === 401) throw new Error("Yetki gerekli — CV.setToken(...) ile giriş yapın");
    if (!r.ok) {
      const text = await r.text();
      throw new Error(text || r.statusText);
    }
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("application/json")) return r.json();
    return r;
  }

  function statusColor(status) {
    switch (status) {
      case "under_review":
        return "#fbbf24";
      case "confirmed":
        return "#22d3ee";
      case "work_order_created":
        return "#34d399";
      case "false_positive":
        return "#6b7280";
      case "resolved":
        return "#5d6e8c";
      default:
        return "#8fa0bd";
    }
  }

  function severityRadius(severity) {
    switch (severity) {
      case "critical":
      case "high":
        return 10;
      case "medium":
        return 7;
      default:
        return 6;
    }
  }

  function qs(id) {
    const params = new URLSearchParams(window.location.search);
    return params.get(id);
  }

  function eventIdFromPath() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts[0] === "events" && parts[1]) return decodeURIComponent(parts[1]);
    return qs("id");
  }

  async function pingHealth() {
    const el = document.getElementById("health");
    if (!el) return;
    try {
      const h = await j("/health");
      el.textContent = h.status === "ok" ? "PostGIS bağlı" : "DB sorunlu";
    } catch (_) {
      el.textContent = "API yok";
    }
  }

  global.CV = {
    mountNav,
    j,
    getToken,
    setToken,
    statusColor,
    severityRadius,
    qs,
    eventIdFromPath,
    pingHealth,
  };
})(window);
