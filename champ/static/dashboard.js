// champ/static/dashboard.js


// -----------------------------
// API helpers
// -----------------------------
const api = {
  chat: async (userId, question) => {
    const res = await fetch("/api/champ/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: String(userId || "1"), question })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw Object.assign(new Error("Request failed"), { details: err });
    }
    return res.json();
  },

  // UPDATED: fetch aggregates directly from metrics endpoint (decoupled from chat)
  overview: async (userId) => {
    const res = await fetch(`/api/metrics/overview_aggregates?user_id=${encodeURIComponent(userId)}`);
    if (!res.ok) throw new Error("Failed to load aggregates");
    return res.json();
  },

  series: async (userId) => {
    const res = await fetch(`/api/metrics/overview_series?user_id=${encodeURIComponent(userId)}`);
    if (!res.ok) throw new Error("Failed to load series");
    return res.json();
  }
};


// -----------------------------
// Assistant text formatting
// -----------------------------
function sanitizePlainText(s) {
  return String(s ?? "").replace(/\r\n/g, "\n");
}


// Convert stray asterisks and simple emphasis to clean output:
// - *text* or _text_ -> **text**
// - Lines starting with "* " -> "- "
// - Remove lone asterisks not part of **bold**
function formatAssistantText(raw) {
  let s = sanitizePlainText(raw);

  // Emphasis to bold (avoid code/backticks scope)
  s = s.replace(/(^|[\s(])\*([^*\n]+)\*([\s).,!?:;]|$)/g, "$1**$2**$3");
  s = s.replace(/(^|[\s(])_([^_\n]+)_([\s).,!?:;]|$)/g, "$1**$2**$3");

  // Bullet asterisks to dashes
  s = s.replace(/^[ \t]*\*[ \t]+/gm, "- ");

  // Collapse 3+ asterisks to 2
  s = s.replace(/\*{3,}/g, "**");

  // Remove leftover single asterisks not belonging to bold pairs
  s = s.replace(/(^|[^*\w])\*([^*\n]|$)/g, (m, p1, p2) => `${p1}${p2}`);

  return s;
}


// Allow only minimal bold rendering: **text** -> <strong>text</strong>
function renderMinimalMarkdownToHTML(s) {
  const escaped = s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
}


// -----------------------------
// DOM helpers & formatting
// -----------------------------
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}


// Removed router prefix usage; keep signature simple
function addMessage(role, text) {
  const wrap = el("div", "msg");
  const who = el("div", "who", role === "user" ? "You" : "Assistant");
  const bubble = el("div", "bubble");

  let content = text ?? "";
  if (role !== "user") {
    content = formatAssistantText(content);
    content = renderMinimalMarkdownToHTML(content);
    bubble.innerHTML = content;
  } else {
    bubble.textContent = content;
  }

  wrap.appendChild(who);
  wrap.appendChild(bubble);
  const box = document.getElementById("messages");
  if (box) {
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
  }
}


const fmtNum = (v) =>
  v == null ? "—" : typeof v === "number" ? Math.round(v * 100) / 100 : String(v);


// -----------------------------
// Count-up animations (KPIs)
// -----------------------------
function animateCount(el, target, opts = {}) {
  if (!el) return;
  if (target == null || target === "—" || target === "") {
    el.textContent = "—";
    return;
  }

  const decimals = typeof target === "number" && !Number.isInteger(target) ? 2 : 0;
  const duration = opts.duration || 800; // ms
  const start = performance.now();
  const from = 0;
  const to = Number(target);

  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
    let val = from + (to - from) * eased;
    if (decimals) val = Math.round(val * 100) / 100;
    else val = Math.round(val);
    el.textContent = String(val);
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function animateCountStable(el, target, opts = {}) {
  if (!el) return;
  const next = target == null ? "" : String(target);
  const prev = el.getAttribute("data-last");
  if (prev === next) return;
  el.setAttribute("data-last", next);
  animateCount(el, target, opts);
}

function animateCompound(el, leftVal, rightVal, separator = " / ") {
  if (!el) return;
  el.textContent = ""; // clear
  const leftSpan = document.createElement("span");
  const sepSpan = document.createElement("span");
  const rightSpan = document.createElement("span");
  sepSpan.textContent = separator;
  el.appendChild(leftSpan);
  el.appendChild(sepSpan);
  el.appendChild(rightSpan);

  animateCountStable(leftSpan, leftVal);
  animateCountStable(rightSpan, rightVal);
}


// -----------------------------
// Chat flow
// -----------------------------
async function sendMessage() {
  const userId = (document.getElementById("userId") || {}).value || "1";
  const input = document.getElementById("input");
  const q = input ? input.value.trim() : "";
  if (!q) return;
  addMessage("user", q);
  if (input) input.value = "";
  try {
    const data = await api.chat(userId, q);

    const ans = data.answer || JSON.stringify(data, null, 2);
    addMessage("assistant", ans);

    // If you re-add a debug panel, this guard prevents null derefs
    const sqlbox = document.getElementById("sqlbox");
    if (sqlbox && data.data_used) {
      const dbg = {
        sql: data.data_used.sql,
        params: data.data_used.params,
        row_count: data.data_used.row_count,
        aggregates: data.data_used.aggregates || null,
        llm_unavailable: data.data_used.llm_unavailable || false,
        router_mode: data.data_used.router_mode || null,
        router_intent: data.data_used.router_intent || null,
        router_meta: data.data_used.router_meta || null
      };
      sqlbox.textContent = JSON.stringify(dbg, null, 2);
    }
  } catch (e) {
    const details = e.details || {};
    addMessage("assistant", `Error: ${details.error || e.message}\nDetails: ${details.details || ""}`);
  }
}


// -----------------------------
// Overview + Charts
// -----------------------------
async function refreshOverview() {
  const userId = (document.getElementById("userId") || {}).value || "1";

  // 1) Overview aggregates (UPDATED: read from metrics endpoint shape)
  try {
    const data = await api.overview(userId);
    const ag = (data && data.aggregates) || null;
    if (ag) {
      animateCountStable(document.getElementById("kpi-total"), Number(ag.total_sessions) || 0);

      const nodePosture = document.getElementById("kpi-posture");
      if (nodePosture) animateCompound(nodePosture, Number(ag.avg_posture_all) || 0, Number(ag.avg_posture_10) || 0);

      const nodeGait = document.getElementById("kpi-gait");
      if (nodeGait) animateCompound(nodeGait, Number(ag.avg_gait_all) || 0, Number(ag.avg_gait_10) || 0);

      const nodeBalance = document.getElementById("kpi-balance");
      if (nodeBalance) animateCompound(nodeBalance, Number(ag.avg_balance_all) || 0, Number(ag.avg_balance_10) || 0);

      const nodeSteps = document.getElementById("kpi-steps");
      if (nodeSteps) animateCompound(nodeSteps, Number(ag.avg_steps_all) || 0, Number(ag.avg_steps_10) || 0);

      animateCountStable(document.getElementById("kpi-short"), Number(ag.short_sessions_10) || 0);
      animateCountStable(document.getElementById("kpi-alerts"), Number(ag.recent_alerts) || 0);
      animateCountStable(document.getElementById("kpi-recs"), Number(ag.recent_recs) || 0);
    }
  } catch (_) {
    // ignore overview load errors
  }

  // 2) Last-10 series for charts
  try {
    const s = await api.series(userId);
    if (s && s.series) renderCharts(s.series);
  } catch (_) {
    // ignore chart errors
  }
}


// -----------------------------
// Charts (2×2 grid friendly)
// -----------------------------
let CH_TREND, CH_DUR, CH_STEPS, CH_AR;

function renderCharts(series) {
  // Compact labels
  const labels = (series.labels || []).map((s) => String(s).replace("T", " ").slice(0, 16));
  const posture = series.posture || [];
  const gait = series.gait || [];
  const balance = series.balance || [];
  const steps = series.steps || [];
  const duration = series.duration_sec || [];
  const durMedian = series.duration_median_sec;
  const alertsCount = series.alerts_count || 0;
  const recsCount = series.recs_count || 0;

  // Teal-blue palette
  const cTeal = "#0fa7b6";
  const cTealLight = "#36d6cc";
  const cBlue = "#2563eb";
  const cAmber = "#f59e0b";
  const cGray = "#94a3b8";

  // 1) Trend (line)
  const elTrend = document.getElementById("chart-trend");
  if (elTrend && window.Chart) {
    const cfg = {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "Posture", data: posture, borderColor: cTeal, backgroundColor: cTeal, tension: 0.25, pointRadius: 2 },
          { label: "Gait", data: gait, borderColor: cBlue, backgroundColor: cBlue, tension: 0.25, pointRadius: 2 },
          { label: "Balance", data: balance, borderColor: cTealLight, backgroundColor: cTealLight, tension: 0.25, pointRadius: 2 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: false },
        plugins: { legend: { position: "top" } },
        elements: { point: { radius: 2 }, line: { borderWidth: 2 } },
        scales: { x: { ticks: { autoSkip: true, maxTicksLimit: 5 } } }
      }
    };
    if (CH_TREND) { CH_TREND.data = cfg.data; CH_TREND.options = cfg.options; CH_TREND.update(); } else { CH_TREND = new Chart(elTrend, cfg); }
  }

  // 2) Duration (bar) + optional median line
  const elDur = document.getElementById("chart-duration");
  if (elDur && window.Chart) {
    const cfg = {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Duration (sec)", data: duration, backgroundColor: cTeal + "66", borderColor: cTeal }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "top" },
          annotation: durMedian ? {
            annotations: {
              medianLine: {
                type: "line",
                yMin: durMedian,
                yMax: durMedian,
                borderColor: cGray,
                borderWidth: 2,
                label: { enabled: true, content: `Median ${Math.round(durMedian)}s`, position: "start", color: "#0f172a" }
              }
            }
          } : undefined
        },
        scales: {
          x: { ticks: { autoSkip: true, maxTicksLimit: 5 } },
          y: { beginAtZero: true }
        }
      }
    };
    if (CH_DUR) { CH_DUR.data = cfg.data; CH_DUR.options = cfg.options; CH_DUR.update(); } else { CH_DUR = new Chart(elDur, cfg); }
  }

  // 3) Steps (bar)
  const elSteps = document.getElementById("chart-steps");
  if (elSteps && window.Chart) {
    const cfg = {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Steps", data: steps, backgroundColor: cBlue + "66", borderColor: cBlue }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: { x: { ticks: { autoSkip: true, maxTicksLimit: 5 } }, y: { beginAtZero: true } }
      }
    };
    if (CH_STEPS) { CH_STEPS.data = cfg.data; CH_STEPS.options = cfg.options; CH_STEPS.update(); } else { CH_STEPS = new Chart(elSteps, cfg); }
  }

  // 4) Alerts vs Recs (stacked bar)
  const elAR = document.getElementById("chart-ar");
  if (elAR && window.Chart) {
    const cfg = {
      type: "bar",
      data: {
        labels: ["Last 10"],
        datasets: [
          { label: "Alerts", data: [alertsCount], backgroundColor: cAmber + "99", borderColor: cAmber },
          { label: "Recommendations", data: [recsCount], backgroundColor: cTeal + "99", borderColor: cTeal }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, precision: 0 } }
      }
    };
    if (CH_AR) { CH_AR.data = cfg.data; CH_AR.options = cfg.options; CH_AR.update(); } else { CH_AR = new Chart(elAR, cfg); }
  }
}


// -----------------------------
// Wire up
// -----------------------------
function wire() {
  const sendBtn = document.getElementById("send");
  if (sendBtn) sendBtn.addEventListener("click", sendMessage);

  const input = document.getElementById("input");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshOverview);

  const qp = document.getElementById("quick-prompts");
  if (qp) {
    qp.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      const t = btn.getAttribute("data-q");
      const inputEl = document.getElementById("input");
      if (inputEl) {
        inputEl.value = t;
        inputEl.focus();
      }
    });
  }

  // Initial load
  refreshOverview();
}

document.addEventListener("DOMContentLoaded", wire);
