// Dashboard frontend — Task 05 polish
const API = "http://localhost:8000";

// Keep chart instances so we can destroy before redrawing
let priceChartInstance = null;
let equityChartInstance = null;

// ── chart defaults ────────────────────────────────────────────────
const GRID_COLOR  = "rgba(255,255,255,0.06)";
const TICK_COLOR  = "#8b9baf";
const FONT_FAMILY = "system-ui, -apple-system, sans-serif";

function baseOptions(yLabel = "") {
  return {
    responsive: true,
    animation: { duration: 300 },
    interaction: { mode: "index", intersect: false },
    scales: {
      x: {
        ticks: { color: TICK_COLOR, font: { family: FONT_FAMILY, size: 11 }, maxTicksLimit: 10 },
        grid: { color: GRID_COLOR },
      },
      y: {
        ticks: { color: TICK_COLOR, font: { family: FONT_FAMILY, size: 11 } },
        grid: { color: GRID_COLOR },
        title: yLabel
          ? { display: true, text: yLabel, color: TICK_COLOR, font: { size: 11 } }
          : { display: false },
      },
    },
    plugins: {
      legend: { labels: { color: "#c9d1d9", font: { family: FONT_FAMILY, size: 12 } } },
      tooltip: {
        backgroundColor: "#0e1826",
        borderColor: "#1a2840",
        borderWidth: 1,
        titleColor: "#e6edf3",
        bodyColor: "#8b9baf",
      },
    },
  };
}

// ── health check ─────────────────────────────────────────────────
async function checkHealth() {
  const badge = document.getElementById("statusBadge");
  try {
    const r = await fetch(`${API}/health`);
    const j = await r.json();
    badge.textContent = "backend " + j.status;
    badge.className = "ok";
  } catch {
    badge.textContent = "backend offline";
    badge.className = "err";
  }
}

// ── price + indicator chart ───────────────────────────────────────
async function drawPriceChart(symbol) {
  const [priceRes, smaRes] = await Promise.all([
    fetch(`${API}/prices/${symbol}`),
    fetch(`${API}/indicators/${symbol}?window=20`),
  ]);
  const priceData = await priceRes.json();
  const smaData   = await smaRes.json();

  document.getElementById("priceTitle").textContent = `${symbol} — Price & SMA(20)`;

  if (priceChartInstance) priceChartInstance.destroy();
  priceChartInstance = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: priceData.dates,
      datasets: [
        {
          label: symbol + " Close",
          data: priceData.close,
          borderColor: "#4da3ff",
          backgroundColor: "rgba(77,163,255,0.08)",
          fill: true,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
        {
          label: "SMA 20",
          data: smaData.sma,
          borderColor: "#ffb84d",
          borderWidth: 1.5,
          borderDash: [4, 3],
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: baseOptions("EGP"),
  });
}

// ── equity curve chart ────────────────────────────────────────────
async function drawEquityChart() {
  const r    = await fetch(`${API}/backtest`);
  const data = await r.json();

  if (equityChartInstance) equityChartInstance.destroy();
  equityChartInstance = new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: data.dates,
      datasets: [
        {
          label: "Strategy",
          data: data.portfolio,
          borderColor: "#26c466",
          backgroundColor: "rgba(38,196,102,0.08)",
          fill: true,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
        {
          label: "Benchmark (EGX30)",
          data: data.benchmark,
          borderColor: "#ff4d6a",
          backgroundColor: "rgba(255,77,106,0.06)",
          fill: true,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: baseOptions("EGP"),
  });
}

// ── metrics cards ─────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const r = await fetch(`${API}/metrics`);
    const m = await r.json();

    const trEl = document.getElementById("mTotalReturn");
    const pct  = (m.total_return * 100).toFixed(1) + "%";
    trEl.textContent = pct;
    trEl.className   = "metric-value " + (m.total_return >= 0 ? "positive" : "negative");

    const shEl = document.getElementById("mSharpe");
    shEl.textContent = m.sharpe.toFixed(2);
    shEl.className   = "metric-value " + (m.sharpe >= 1 ? "positive" : m.sharpe < 0 ? "negative" : "");

    const ddEl = document.getElementById("mMaxDrawdown");
    ddEl.textContent = (m.max_drawdown * 100).toFixed(1) + "%";
    ddEl.className   = "metric-value negative";   // drawdown is always a loss
  } catch {
    ["mTotalReturn", "mSharpe", "mMaxDrawdown"].forEach(
      id => (document.getElementById(id).textContent = "err")
    );
  }
}

// ── symbol dropdown ───────────────────────────────────────────────
async function buildDropdown() {
  const r       = await fetch(`${API}/universe`);
  const symbols = await r.json();
  const select  = document.getElementById("symbolSelect");

  symbols.forEach(sym => {
    const opt = document.createElement("option");
    opt.value = sym;
    opt.textContent = sym;
    select.appendChild(opt);
  });

  select.addEventListener("change", () => drawPriceChart(select.value));
  return symbols[0];
}

// ── bootstrap ────────────────────────────────────────────────────
async function init() {
  await checkHealth();
  const firstSymbol = await buildDropdown();
  await Promise.all([
    drawPriceChart(firstSymbol),
    drawEquityChart(),
    loadMetrics(),
  ]);
}

init();
