// Dashboard frontend. Talks to the FastAPI backend and renders all panels.
const API = "http://localhost:8000";

// Series colors (mint/white theme).
const COLORS = {
  price: "#1e293b",
  sma: "#10b981",
  strategy: "#10b981",
  benchmark: "#94a3b8",
  mpt: "#0ea5e9",
  nn: "#059669",
  lstm: "#34d399",
  rl: "#10b981",
  qagent: "#6ee7b9",
};

Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
Chart.defaults.color = "#64748b";
Chart.defaults.borderColor = "#d1fae5";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function getJSON(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

function setUnavailable(el, msg) {
  el.innerHTML = `<span class="note">${msg || "data unavailable"}</span>`;
}

function seqLabels(n) {
  return Array.from({ length: n }, (_, i) => i + 1);
}

// Base options for a line chart.
function lineOpts(yTitle) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: true, position: "top", labels: { boxWidth: 12, usePointStyle: true } },
      tooltip: { enabled: true },
    },
    scales: {
      x: { ticks: { maxTicksLimit: 8, autoSkip: true }, grid: { display: false } },
      y: { title: { display: !!yTitle, text: yTitle || "" }, grid: { color: "#eef7f3" } },
    },
  };
}

function lineDataset(label, data, color, opts = {}) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color,
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.2,
    ...opts,
  };
}

// ---------------------------------------------------------------------------
// Health pill
// ---------------------------------------------------------------------------
async function checkHealth() {
  const pill = document.getElementById("status");
  const text = document.getElementById("status-text");
  try {
    const j = await getJSON("/health");
    text.textContent = "backend: " + j.status;
  } catch (e) {
    pill.classList.add("err");
    text.textContent = "backend not reachable — start uvicorn";
  }
}

// ---------------------------------------------------------------------------
// Universe → fill both symbol dropdowns
// ---------------------------------------------------------------------------
async function loadUniverse() {
  const priceSel = document.getElementById("price-symbol");
  const featSel = document.getElementById("feature-symbol");
  try {
    const symbols = await getJSON("/universe");
    for (const sel of [priceSel, featSel]) {
      sel.innerHTML = "";
      for (const s of symbols) {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        sel.appendChild(opt);
      }
    }
    priceSel.value = symbols[0];
    featSel.value = symbols[0];
    await loadPricePanel();
    await loadFeaturesPanel();
  } catch (e) {
    setUnavailable(document.getElementById("price-chart").parentElement, "universe unavailable");
  }
}

// ---------------------------------------------------------------------------
// Price + SMA panel
// ---------------------------------------------------------------------------
let priceChart;
async function loadPricePanel() {
  const symbol = document.getElementById("price-symbol").value;
  const canvas = document.getElementById("price-chart");
  try {
    const [price, ind] = await Promise.all([
      getJSON(`/prices/${symbol}`),
      getJSON(`/indicators/${symbol}?window=20`),
    ]);
    const labels = price.dates;
    if (priceChart) priceChart.destroy();
    priceChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          lineDataset("Close", price.close, COLORS.price),
          lineDataset("SMA 20", ind.sma, COLORS.sma),
        ],
      },
      options: lineOpts("Price (EGP)"),
    });
  } catch (e) {
    setUnavailable(canvas.parentElement, "price data unavailable");
  }
}

// ---------------------------------------------------------------------------
// Equity vs EGX30 + metric chips
// ---------------------------------------------------------------------------
let equityChart;
async function loadEquityPanel() {
  const canvas = document.getElementById("equity-chart");
  const chips = document.getElementById("metric-chips");
  try {
    const [bt, m] = await Promise.all([getJSON("/backtest"), getJSON("/metrics")]);
    const labels = bt.dates;
    if (equityChart) equityChart.destroy();
    equityChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          lineDataset("SMA strategy", bt.portfolio, COLORS.strategy),
          lineDataset("EGX30", bt.benchmark, COLORS.benchmark),
        ],
      },
      options: lineOpts("Equity (EGP)"),
    });
    chips.innerHTML = `
      <div class="chip">Total return<b>${fmtPct(m.total_return)}</b></div>
      <div class="chip">Sharpe<b>${m.sharpe.toFixed(2)}</b></div>
      <div class="chip">Max drawdown<b>${fmtPct(m.max_drawdown)}</b></div>
      <div class="chip">Volatility<b>${fmtPct(m.volatility)}</b></div>`;
  } catch (e) {
    setUnavailable(canvas.parentElement, "backtest unavailable");
  }
}

function fmtPct(x) {
  return (x * 100).toFixed(1) + "%";
}

// ---------------------------------------------------------------------------
// Leaderboard + risk table
// ---------------------------------------------------------------------------
let leaderboardChart;
async function loadLeaderboardPanel() {
  const canvas = document.getElementById("leaderboard-chart");
  const table = document.getElementById("risk-table");
  try {
    const [lb, risk] = await Promise.all([getJSON("/leaderboard"), getJSON("/risk")]);
    const labels = lb.dates;
    if (leaderboardChart) leaderboardChart.destroy();
    leaderboardChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          lineDataset("SMA", lb.sma, COLORS.strategy),
          lineDataset("MPT", lb.mpt, COLORS.mpt),
          lineDataset("EGX30", lb.benchmark, COLORS.benchmark),
        ],
      },
      options: lineOpts("Equity (EGP)"),
    });
    table.innerHTML = riskTable(risk);
  } catch (e) {
    setUnavailable(canvas.parentElement, "leaderboard unavailable");
  }
}

function riskTable(risk) {
  const rows = [
    ["SMA", risk.sma],
    ["MPT", risk.mpt],
    ["EGX30", risk.benchmark],
  ];
  const cls = (v) => (v >= 0 ? "pos" : "neg");
  return `
    <thead><tr><th>Strategy</th><th>Sharpe</th><th>Volatility</th><th>Max DD</th><th>Total ret</th></tr></thead>
    <tbody>
      ${rows
        .map(([name, r]) => `
        <tr>
          <td>${name}</td>
          <td class="${cls(r.sharpe)}">${r.sharpe.toFixed(2)}</td>
          <td>${fmtPct(r.volatility)}</td>
          <td class="${cls(r.max_drawdown)}">${fmtPct(r.max_drawdown)}</td>
          <td class="${cls(r.total_return)}">${fmtPct(r.total_return)}</td>
        </tr>`)
        .join("")}
    </tbody>`;
}

// ---------------------------------------------------------------------------
// Features panel (HTML bars)
// ---------------------------------------------------------------------------
async function loadFeaturesPanel() {
  const symbol = document.getElementById("feature-symbol").value;
  const el = document.getElementById("feature-bars");
  try {
    const data = await getJSON(`/features/${symbol}`);
    const maxAbs = Math.max(...data.features.map((f) => Math.abs(f.value)), 0.001);
    el.innerHTML = data.features
      .map((f) => {
        const w = (Math.abs(f.value) / maxAbs) * 100;
        const color = f.value >= 0 ? COLORS.sma : "#ef4444";
        return `
          <div class="bar-row">
            <span class="lbl">${f.name}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${w}%;background:${color}"></div></div>
            <span class="val">${f.value.toFixed(3)}</span>
          </div>`;
      })
      .join("");
  } catch (e) {
    setUnavailable(el, "features unavailable");
  }
}

// ---------------------------------------------------------------------------
// Saved-curve panels (no dates → index labels)
// ---------------------------------------------------------------------------
let modelsChart, rlChart, qagentChart;

async function loadModelsPanel() {
  const canvas = document.getElementById("models-chart");
  try {
    const d = await getJSON("/models");
    const n = Math.max(d.nn.portfolio.length, d.lstm.portfolio.length);
    const labels = seqLabels(n);
    if (modelsChart) modelsChart.destroy();
    modelsChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          lineDataset("NN", d.nn.portfolio, COLORS.nn),
          lineDataset("LSTM", d.lstm.portfolio, COLORS.lstm),
        ],
      },
      options: lineOpts("Equity"),
    });
  } catch (e) {
    setUnavailable(canvas.parentElement, "model curves unavailable");
  }
}

async function loadRlPanel() {
  const canvas = document.getElementById("rl-chart");
  try {
    const d = await getJSON("/rl");
    const n = Math.max(d.agent.length, d.benchmark.length);
    const labels = seqLabels(n);
    if (rlChart) rlChart.destroy();
    rlChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          lineDataset("RL agent", d.agent, COLORS.rl),
          lineDataset("Benchmark", d.benchmark, COLORS.benchmark),
        ],
      },
      options: lineOpts("Equity"),
    });
  } catch (e) {
    setUnavailable(canvas.parentElement, "RL curve unavailable");
  }
}

async function loadQagentPanel() {
  const canvas = document.getElementById("qagent-chart");
  try {
    const d = await getJSON("/qagent");
    const n = Math.max(d.portfolio.length, d.benchmark.length);
    const labels = seqLabels(n);
    if (qagentChart) qagentChart.destroy();
    qagentChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          lineDataset("Q-agent", d.portfolio, COLORS.qagent),
          lineDataset("Buy & hold", d.benchmark, COLORS.benchmark),
        ],
      },
      options: lineOpts("Equity"),
    });
  } catch (e) {
    setUnavailable(canvas.parentElement, "Q-agent curve unavailable");
  }
}

// ---------------------------------------------------------------------------
// Allocations panel (HTML bars)
// ---------------------------------------------------------------------------
async function loadAllocationsPanel() {
  const el = document.getElementById("allocation-bars");
  try {
    const d = await getJSON("/allocations");
    const maxW = Math.max(...d.weights.map((w) => w.weight), 0.001);
    el.innerHTML = d.weights
      .map((w) => {
        const pct = (w.weight / maxW) * 100;
        return `
          <div class="bar-row">
            <span class="lbl">${w.symbol}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
            <span class="val">${(w.weight * 100).toFixed(1)}%</span>
          </div>`;
      })
      .join("");
  } catch (e) {
    setUnavailable(el, "allocations unavailable");
  }
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
document.getElementById("price-symbol").addEventListener("change", loadPricePanel);
document.getElementById("feature-symbol").addEventListener("change", loadFeaturesPanel);

async function init() {
  await checkHealth();
  await loadUniverse();
  await loadEquityPanel();
  await loadLeaderboardPanel();
  await loadModelsPanel();
  await loadRlPanel();
  await loadQagentPanel();
  await loadAllocationsPanel();
}
init();
