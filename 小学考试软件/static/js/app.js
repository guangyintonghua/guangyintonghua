// ── 公共工具函数 ──────────────────────────────

async function apiFetch(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function toast(msg, type = "info") {
  const box = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// 轮询后台任务，直到 done/error
async function pollTask(taskId, onDone, onError, interval = 1500) {
  const timer = setInterval(async () => {
    const t = await apiFetch(`/api/tasks/${taskId}`);
    if (t.status === "done") {
      clearInterval(timer);
      onDone(t.result);
    } else if (t.status === "error") {
      clearInterval(timer);
      onError(t.error || "未知错误");
    }
  }, interval);
}

// URL 参数工具
function getParam(key) {
  return new URLSearchParams(location.search).get(key);
}

function setParam(key, val) {
  const p = new URLSearchParams(location.search);
  p.set(key, val);
  history.pushState({}, "", "?" + p.toString());
}

// 格式化日期
function fmtDate(s) {
  return s ? s.slice(0, 10) : "";
}

// 得分颜色
function scoreColor(rate) {
  if (rate >= 0.9) return "var(--success)";
  if (rate >= 0.7) return "var(--primary)";
  if (rate >= 0.5) return "var(--warning)";
  return "var(--danger)";
}

// 掌握度标签
function masteryBadge(rate) {
  if (rate >= 0.9) return '<span class="badge badge-green">掌握良好</span>';
  if (rate >= 0.7) return '<span class="badge badge-blue">基本掌握</span>';
  if (rate >= 0.5) return '<span class="badge badge-orange">需要加强</span>';
  return '<span class="badge badge-red">严重薄弱</span>';
}

// 当前学生 ID（存 sessionStorage，避免每页重新拿）
async function ensureStudent() {
  const s = await apiFetch("/api/students/current");
  return s;
}

// 激活侧边栏当前项
function activateNav() {
  const path = location.pathname.replace(/\/$/, "") || "/";
  document.querySelectorAll(".nav-item").forEach(el => {
    const href = el.getAttribute("href") || "";
    const active = href === path || (href !== "/" && path.startsWith(href));
    el.classList.toggle("active", active);
  });
}

document.addEventListener("DOMContentLoaded", activateNav);
