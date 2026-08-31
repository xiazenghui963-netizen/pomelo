const Api = {
  base: "/api",
  tokenKey: "qy_token",

  token() {
    return localStorage.getItem(this.tokenKey);
  },
  setToken(t) {
    localStorage.setItem(this.tokenKey, t);
  },
  clear() {
    localStorage.removeItem(this.tokenKey);
  },
  requireAuth() {
    if (!this.token()) {
      location.href = "/login.html";
      return false;
    }
    return true;
  },
  logout() {
    this.clear();
    location.href = "/login.html";
  },
  async call(path, options = {}) {
    const opts = {
      method: options.method || "GET",
      headers: { ...(options.headers || {}) },
      body: options.body,
    };
    const t = this.token();
    if (t) opts.headers["Authorization"] = `Bearer ${t}`;
    if (options.json !== false && opts.body && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(this.base + path, opts).catch(() => {
      throw new Error("网络请求失败");
    });
    let data;
    try {
      data = await res.json();
    } catch (_e) {
      throw new Error(`请求失败(${res.status})`);
    }
    if (res.status === 401) {
      this.clear();
      location.href = "/login.html";
      throw new Error(data.message || "登录已失效");
    }
    if (!res.ok || data.code !== 0) {
      throw new Error(data.message || "请求失败");
    }
    return data.data;
  },
  async get(path) {
    return this.call(path);
  },
  async post(path, body) {
    return this.call(path, { method: "POST", body });
  },
  async put(path, body) {
    return this.call(path, { method: "PUT", body });
  },
  async del(path) {
    return this.call(path, { method: "DELETE" });
  },
  async upload(file) {
    const fd = new FormData();
    fd.append("file", file);
    return this.call("/upload", { method: "POST", body: fd, json: false });
  },
};

function toast(msg, type = "ok") {
  const box = document.getElementById("toast");
  if (!box) return;
  box.className = `toast ${type}`;
  box.textContent = msg;
  box.classList.add("show");
  setTimeout(() => box.classList.remove("show"), 2600);
}