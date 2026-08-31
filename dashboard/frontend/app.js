// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";
let priceChartInstance = null;
let equityChartInstance = null;

// Single shared palette so both charts read as one system:
// primary = the "asset" line (price / strategy), secondary = the "reference" line (SMA / benchmark).
const COLOR_PRIMARY = "#5b9dfa";
const COLOR_SECONDARY = "#f0a857";
const COLOR_GRID = "#1b2438";
const COLOR_TEXT = "#c9d1d9";
const COLOR_TEXT_DIM = "#8a94a6";

const sharedGridX = { ticks: { maxTicksLimit: 8, color: COLOR_TEXT_DIM }, grid: { color: COLOR_GRID } };

const state = {
  universe: "core",
  benchmark: "equal_weight",
  commission: 0.005,
  metricsStrategy: "mean_reversion",
};

async function checkHealth() {
  const pill = document.getElementById("statusPill");
  const label = document.getElementById("statusLabel");
  try {
    const r = await fetch(`${API}/health`);
    const j = await r.json();
    pill.classList.add("online");
    pill.classList.remove("offline");
    label.textContent = "backend: " + j.status;
  } catch (e) {
    pill.classList.add("offline");
    pill.classList.remove("online");
    label.textContent = "backend not reachable — start uvicorn";
  }
}
checkHealth();

async function drawPriceChart(symbol) {
  const [pricesRes, indicatorsRes] = await Promise.all([
    fetch(`${API}/prices/${symbol}?universe=${state.universe}`),
    fetch(`${API}/indicators/${symbol}?window=20&universe=${state.universe}`),
  ]);
  const { dates, close } = await pricesRes.json();
  const { sma } = await indicatorsRes.json();

  document.getElementById("priceChartTitle").textContent = `${symbol} — Price & 20-Day Trend`;
  document.getElementById("priceChartSubtitle").textContent = `${dates[0]} → ${dates[dates.length - 1]}`;

  if (priceChartInstance) priceChartInstance.destroy();
  priceChartInstance = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: symbol, data: close, borderColor: COLOR_PRIMARY, backgroundColor: COLOR_PRIMARY, borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: `${symbol} SMA(20)`, data: sma, borderColor: COLOR_SECONDARY, backgroundColor: COLOR_SECONDARY, borderWidth: 1.5, pointRadius: 0, tension: 0.1, spanGaps: true },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: {
        x: sharedGridX,
        y: { ticks: { color: COLOR_TEXT_DIM }, grid: { color: COLOR_GRID } },
      },
    },
  });
}

async function setupSymbolDropdown() {
  const res = await fetch(`${API}/universe?universe=${state.universe}`);
  const symbols = await res.json();
  const select = document.getElementById("symbolSelect");
  select.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join("");
  select.addEventListener("change", () => drawPriceChart(select.value));
  if (symbols.length) drawPriceChart(symbols[0]);
}
setupSymbolDropdown();

function setupUniverseToggle() {
  const buttons = document.querySelectorAll("#universeToggle .segmented-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active")) return;
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.universe = btn.dataset.universe;
      // Universe affects the symbol list, the price chart, and the backtest
      // (equal-weight benchmark and the strategy's own weights both depend
      // on which assets are in play), so refresh everything downstream.
      setupSymbolDropdown();
      drawEquityChart();
      loadMetrics();
    });
  });
}
setupUniverseToggle();

function setupBacktestControls() {
  const benchmarkSelect = document.getElementById("benchmarkSelect");
  const commissionSelect = document.getElementById("commissionSelect");

  benchmarkSelect.value = state.benchmark;
  commissionSelect.value = state.commission;

  benchmarkSelect.addEventListener("change", () => {
    state.benchmark = benchmarkSelect.value;
    drawEquityChart();
    loadMetrics();
  });

  commissionSelect.addEventListener("change", () => {
    state.commission = parseFloat(commissionSelect.value);
    drawEquityChart();
    loadMetrics();
  });
}
setupBacktestControls();

async function drawEquityChart() {
  const params = new URLSearchParams({
    universe: state.universe,
    benchmark: state.benchmark,
    commission: state.commission,
  });

  // Fetch both strategies in parallel so the chart shows both curves at once.
  const [smaRes, sampleRes] = await Promise.all([
    fetch(`${API}/backtest?${params}`),
    fetch(`${API}/backtest/sample_strategy?${params}`),
  ]);
  const smaData    = await smaRes.json();
  const sampleData = await sampleRes.json();

  const strategyLabel = sampleData.strategy_label || "Mean Reversion Strategy";
  const commissionPct = (state.commission * 100).toFixed(2).replace(/\.?0+$/, "");

  document.getElementById("equityChartSubtitle").textContent =
    `${strategyLabel} vs SMA crossover · growth of 1,000 EGP · ${commissionPct}% commission`;

  if (equityChartInstance) equityChartInstance.destroy();
  equityChartInstance = new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: sampleData.dates,
      datasets: [
        {
          label: strategyLabel,
          data: sampleData.portfolio,
          borderColor: COLOR_PRIMARY,
          backgroundColor: COLOR_PRIMARY,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: "SMA Crossover Strategy",
          data: smaData.portfolio,
          borderColor: "#a78bfa",
          backgroundColor: "#a78bfa",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: sampleData.benchmark_label || "Benchmark",
          data: sampleData.benchmark,
          borderColor: COLOR_SECONDARY,
          backgroundColor: COLOR_SECONDARY,
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: {
        x: sharedGridX,
        y: {
          ticks: { color: COLOR_TEXT_DIM, callback: (v) => `${v.toLocaleString()} EGP` },
          grid: { color: COLOR_GRID },
        },
      },
    },
  });
}
drawEquityChart();

function metricCard(label, value, opts = {}) {
  const { sign = false, suffix = "", colorBySign = false, decimals = 1 } = opts;
  const numeric = typeof value === "number";
  const displayValue = numeric ? `${sign && value > 0 ? "+" : ""}${value.toFixed(decimals)}${suffix}` : value;
  let tone = "neutral";
  if (colorBySign && numeric) tone = value > 0 ? "positive" : value < 0 ? "negative" : "neutral";
  const arrow = colorBySign && numeric && value !== 0 ? `<span class="metric-arrow ${tone}">${value > 0 ? "▲" : "▼"}</span>` : "";
  return `
    <div class="metric-card">
      <span class="metric-label">${label}</span>
      <div class="metric-value-row">
        <span class="metric-value ${tone}">${displayValue}</span>
        ${arrow}
      </div>
    </div>`;
}

async function loadMetrics() {
  const params = new URLSearchParams({
    universe: state.universe,
    benchmark: state.benchmark,
    commission: state.commission,
  });

  // Route to the right endpoint based on the selected strategy tab.
  const endpoint = state.metricsStrategy === "sma"
    ? `${API}/metrics/sma?${params}`
    : `${API}/metrics/sample_strategy?${params}`;

  const res = await fetch(endpoint);
  const { strategy_label, total_return, sharpe, max_drawdown } = await res.json();
  document.getElementById("metricsText").innerHTML =
    metricCard("Total Return", total_return * 100, { sign: true, suffix: "%", colorBySign: true }) +
    metricCard("Sharpe Ratio", sharpe, { decimals: 2, colorBySign: false }) +
    metricCard("Max Drawdown", -Math.abs(max_drawdown) * 100, { sign: true, suffix: "%", colorBySign: true, decimals: 1 });
}

function setupMetricsStrategyToggle() {
  const buttons = document.querySelectorAll("#metricsStrategyToggle .segmented-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active")) return;
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.metricsStrategy = btn.dataset.strategy;
      loadMetrics();
    });
  });
}
setupMetricsStrategyToggle();
loadMetrics();