// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";
let priceChartInstance = null;
let equityChartClassicInstance = null;
let equityChartMLInstance = null;

// Single shared palette so all charts read as one system:
// primary = the "asset" line (price / strategy), secondary = the "reference" line (SMA / benchmark).
const COLOR_PRIMARY = "#5b9dfa";
const COLOR_SECONDARY = "#f0a857";
const COLOR_GRID = "#1b2438";
const COLOR_TEXT = "#c9d1d9";
const COLOR_TEXT_DIM = "#8a94a6";

const sharedGridX = { ticks: { maxTicksLimit: 8, color: COLOR_TEXT_DIM }, grid: { color: COLOR_GRID } };

// Strategies are split into two groups because they run over two different
// calendar windows:
//   - "classic" strategies (mean reversion, SMA) run over ~the full history.
//   - "ml" strategies (MLP single/universe) only run over the out-of-sample
//     tail AFTER split_day, and the backend rebases their own equity curve
//     (and their own benchmark) to 1,000 EGP at THAT start date.
// Plotting an ml curve on the classic date axis was the bug: aligning a
// series that legitimately starts at 1,000 EGP partway through the timeline
// onto an axis where every other line has already drifted away from 1,000
// makes it look like a cliff-edge drop, when nothing actually fell — it's
// just two different "growth of 1,000 EGP" baselines sharing one axis. Each
// group now gets its own panel, its own master date axis, and its own
// benchmark line, so every curve's baseline is genuinely comparable to the
// other curves in its panel.
const CLASSIC_KEYS = ["mean_reversion", "sma"];
const ML_KEYS = ["mlp_single", "mlp_universe", "lstm"];
const STRATEGY_KEYS = [...CLASSIC_KEYS, ...ML_KEYS];

const STRATEGY_COLORS = {
  mean_reversion: COLOR_PRIMARY,
  sma: "#a78bfa",
  mlp_single: "#f472b6",
  mlp_universe: "#22d3ee",
  lstm: "#facc15",
};
const BACKTEST_ENDPOINTS = {
  mean_reversion: "/backtest/sample_strategy",
  sma: "/backtest",
  mlp_single: "/backtest/mlp_single",
  mlp_universe: "/backtest/mlp_universe",
  lstm: "/backtest/lstm",
};
const METRICS_ENDPOINTS = {
  mean_reversion: "/metrics/sample_strategy",
  sma: "/metrics/sma",
  mlp_single: "/metrics/mlp_single",
  mlp_universe: "/metrics/mlp_universe",
  lstm: "/metrics/lstm",
};
// Fallback so a missing/failed strategy_label from the backend never shows
// as a bare "undefined" in the legend or tooltip -- it shows a real name
// instead, and the console still gets the real error for debugging.
const STRATEGY_DISPLAY_FALLBACK = {
  mean_reversion: "Mean Reversion",
  sma: "SMA Crossover",
  mlp_single: "MLP Single-Stock",
  mlp_universe: "MLP Whole-Universe",
  lstm: "LSTM Whole-Universe",
};

// The classic panel (Mean Reversion, SMA) and the ML panel (MLP, LSTM) each
// get their own benchmark/commission controls -- they're separate backtest
// windows, so there's no reason toggling one panel's commission should
// silently re-run the other.
const state = {
  universe: "core",
  benchmark: "equal_weight",
  commission: 0.005,
  benchmarkML: "equal_weight",
  commissionML: 0.005,
  metricsStrategyClassic: "mean_reversion",
  metricsStrategyML: "mlp_single",
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
      // Universe affects the symbol list, the price chart, and both backtest
      // panels (equal-weight benchmark and every strategy's own weights all
      // depend on which assets are in play), so refresh everything downstream.
      setupSymbolDropdown();
      refreshBacktests();
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
    drawEquityChartClassic();
    loadMetricsClassic();
  });

  commissionSelect.addEventListener("change", () => {
    state.commission = parseFloat(commissionSelect.value);
    drawEquityChartClassic();
    loadMetricsClassic();
  });
}
setupBacktestControls();

function setupBacktestControlsML() {
  const benchmarkSelect = document.getElementById("benchmarkSelectML");
  const commissionSelect = document.getElementById("commissionSelectML");

  benchmarkSelect.value = state.benchmarkML;
  commissionSelect.value = state.commissionML;

  benchmarkSelect.addEventListener("change", () => {
    state.benchmarkML = benchmarkSelect.value;
    drawEquityChartML();
    loadMetricsML();
  });

  commissionSelect.addEventListener("change", () => {
    state.commissionML = parseFloat(commissionSelect.value);
    drawEquityChartML();
    loadMetricsML();
  });
}
setupBacktestControlsML();

function refreshBacktests() {
  drawEquityChartClassic();
  drawEquityChartML();
  loadMetricsClassic();
  loadMetricsML();
}

// Aligns a shorter/later-starting series onto a shared date axis by finding
// where its first date actually falls, rather than assuming index 0 = index 0.
// Used within a panel to line up strategies that share the same "start of
// history" but may differ slightly in how much lookback padding they burn
// (e.g. SMA's 30-day lookback vs mean reversion's 10-day one).
function alignToLabels(masterDates, seriesDates, seriesValues) {
  const padded = new Array(masterDates.length).fill(null);
  if (!seriesDates.length) return padded;
  const startIdx = masterDates.indexOf(seriesDates[0]);
  if (startIdx === -1) return padded; // dates didn't line up -- draw nothing rather than misplace the curve
  for (let i = 0; i < seriesValues.length && startIdx + i < padded.length; i++) {
    padded[startIdx + i] = seriesValues[i];
  }
  return padded;
}

// Never lets one bad strategy endpoint take the whole panel down. On
// failure, logs the real error/status to the console (so the actual bug is
// visible) and returns null instead of throwing -- callers skip null
// entries rather than crashing mid-render.
async function fetchBacktest(key, benchmark, commission) {
  const params = new URLSearchParams({
    universe: state.universe,
    benchmark,
    commission,
  });
  const url = `${API}${BACKTEST_ENDPOINTS[key]}?${params}`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail || ""; } catch (_) {}
      console.error(`[backtest:${key}] ${res.status} ${res.statusText} ${detail} (${url})`);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.error(`[backtest:${key}] request failed:`, err, url);
    return null;
  }
}

// ── Classic strategies panel: full-history axis ──────────────────────────
async function drawEquityChartClassic() {
  const results = await Promise.all(
    CLASSIC_KEYS.map((k) => fetchBacktest(k, state.benchmark, state.commission))
  );
  const dataByKey = Object.fromEntries(CLASSIC_KEYS.map((k, i) => [k, results[i]]));
  const okKeys = CLASSIC_KEYS.filter((k) => dataByKey[k] !== null);

  if (!okKeys.length) {
    document.getElementById("equityChartSubtitleClassic").textContent =
      "Couldn't load strategy data -- check the backend console for errors.";
    return;
  }

  // Mean Reversion has the longest lookback-free run (lookback=10), so its
  // date list anchors the axis; SMA (lookback=30) gets aligned onto it.
  // Falls back to whichever strategy did load if Mean Reversion itself failed.
  const anchorKey = dataByKey.mean_reversion ? "mean_reversion" : okKeys[0];
  const masterDates = dataByKey[anchorKey].dates;
  const benchmarkValues = dataByKey[anchorKey].benchmark;
  const benchmarkLabel = dataByKey[anchorKey].benchmark_label || "Benchmark";

  const active = dataByKey[state.metricsStrategyClassic];
  const commissionPct = (state.commission * 100).toFixed(2).replace(/\.?0+$/, "");
  const activeLabel = active
    ? (active.strategy_label || STRATEGY_DISPLAY_FALLBACK[state.metricsStrategyClassic])
    : `${STRATEGY_DISPLAY_FALLBACK[state.metricsStrategyClassic]} (failed to load)`;
  document.getElementById("equityChartSubtitleClassic").textContent =
    `${activeLabel} highlighted · growth of 1,000 EGP · ${commissionPct}% commission`;

  const datasets = okKeys.map((k) => {
    const d = dataByKey[k];
    const isActive = k === state.metricsStrategyClassic;
    return {
      label: d.strategy_label || STRATEGY_DISPLAY_FALLBACK[k],
      data: alignToLabels(masterDates, d.dates, d.portfolio),
      borderColor: STRATEGY_COLORS[k],
      backgroundColor: STRATEGY_COLORS[k],
      borderWidth: isActive ? 2.5 : 1,
      borderDash: [4, 3],   // strategies are always dotted; only the benchmark is solid
      pointRadius: 0,
      tension: 0.1,
      spanGaps: false,
      order: isActive ? 0 : 1,
    };
  });

  datasets.push({
    label: benchmarkLabel,
    data: benchmarkValues,
    borderColor: COLOR_SECONDARY,
    backgroundColor: COLOR_SECONDARY,
    borderWidth: 1.5,
    pointRadius: 0,
    tension: 0.1,
    order: 2,
  });

  if (equityChartClassicInstance) equityChartClassicInstance.destroy();
  equityChartClassicInstance = new Chart(document.getElementById("equityChartClassic"), {
    type: "line",
    data: { labels: masterDates, datasets },
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

// ── ML strategies panel: out-of-sample window only, own baseline ────────
async function drawEquityChartML() {
  const results = await Promise.all(
    ML_KEYS.map((k) => fetchBacktest(k, state.benchmarkML, state.commissionML))
  );
  const dataByKey = Object.fromEntries(ML_KEYS.map((k, i) => [k, results[i]]));
  // Render whatever loaded successfully rather than letting one failing
  // strategy (e.g. a still-buggy /backtest/lstm) blank out the whole panel.
  const okKeys = ML_KEYS.filter((k) => dataByKey[k] !== null);
  const failedKeys = ML_KEYS.filter((k) => dataByKey[k] === null);

  if (!okKeys.length) {
    document.getElementById("equityChartSubtitleML").textContent =
      "Couldn't load any ML strategy data -- check the backend console for errors.";
    return;
  }

  // The MLP and LSTM strategies all train on the same feed/split_day, so
  // their date lists should already match; pick whichever came back
  // longest as the master axis and align the others onto it defensively,
  // in case one strategy loses a day or two to NaN-feature masking (the
  // LSTM's seq_len window in particular burns a few more warm-up days
  // than the MLP's single-day lookback).
  let masterKey = okKeys[0];
  for (const k of okKeys) {
    if (dataByKey[k].dates.length > dataByKey[masterKey].dates.length) masterKey = k;
  }
  const masterDates = dataByKey[masterKey].dates;
  const benchmarkValues = dataByKey[masterKey].benchmark;
  const benchmarkLabel = dataByKey[masterKey].benchmark_label || "Benchmark";

  const active = dataByKey[state.metricsStrategyML];
  const commissionPct = (state.commissionML * 100).toFixed(2).replace(/\.?0+$/, "");
  const activeLabel = active
    ? (active.strategy_label || STRATEGY_DISPLAY_FALLBACK[state.metricsStrategyML])
    : `${STRATEGY_DISPLAY_FALLBACK[state.metricsStrategyML]} (failed to load -- see console)`;
  const failedNote = failedKeys.length
    ? ` · ${failedKeys.map((k) => STRATEGY_DISPLAY_FALLBACK[k]).join(", ")} failed to load, check console`
    : "";
  document.getElementById("equityChartSubtitleML").textContent =
    `${activeLabel} highlighted · growth of 1,000 EGP from start of out-of-sample window · ${commissionPct}% commission${failedNote}`;

  const datasets = okKeys.map((k) => {
    const d = dataByKey[k];
    const isActive = k === state.metricsStrategyML;
    return {
      label: d.strategy_label || STRATEGY_DISPLAY_FALLBACK[k],
      data: alignToLabels(masterDates, d.dates, d.portfolio),
      borderColor: STRATEGY_COLORS[k],
      backgroundColor: STRATEGY_COLORS[k],
      borderWidth: isActive ? 2.5 : 1,
      borderDash: [4, 3],   // strategies are always dotted; only the benchmark is solid
      pointRadius: 0,
      tension: 0.1,
      spanGaps: false,
      order: isActive ? 0 : 1,
    };
  });

  datasets.push({
    label: benchmarkLabel,
    data: benchmarkValues,
    borderColor: COLOR_SECONDARY,
    backgroundColor: COLOR_SECONDARY,
    borderWidth: 1.5,
    pointRadius: 0,
    tension: 0.1,
    order: 2,
  });

  if (equityChartMLInstance) equityChartMLInstance.destroy();
  equityChartMLInstance = new Chart(document.getElementById("equityChartML"), {
    type: "line",
    data: { labels: masterDates, datasets },
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

async function loadMetricsFor(key, targetElId, benchmark, commission) {
  const params = new URLSearchParams({
    universe: state.universe,
    benchmark,
    commission,
  });
  const url = `${API}${METRICS_ENDPOINTS[key]}?${params}`;
  let payload;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail || ""; } catch (_) {}
      console.error(`[metrics:${key}] ${res.status} ${res.statusText} ${detail} (${url})`);
      document.getElementById(targetElId).innerHTML =
        `<div class="metric-card"><span class="metric-label">Error</span><span class="metric-value negative">Failed to load -- see console</span></div>`;
      return;
    }
    payload = await res.json();
  } catch (err) {
    console.error(`[metrics:${key}] request failed:`, err, url);
    document.getElementById(targetElId).innerHTML =
      `<div class="metric-card"><span class="metric-label">Error</span><span class="metric-value negative">Failed to load -- see console</span></div>`;
    return;
  }
  const { total_return, sharpe, max_drawdown } = payload;
  document.getElementById(targetElId).innerHTML =
    metricCard("Total Return", total_return * 100, { sign: true, suffix: "%", colorBySign: true }) +
    metricCard("Sharpe Ratio", sharpe, { decimals: 2, colorBySign: false }) +
    metricCard("Max Drawdown", -Math.abs(max_drawdown) * 100, { sign: true, suffix: "%", colorBySign: true, decimals: 1 });
}

function loadMetricsClassic() {
  return loadMetricsFor(state.metricsStrategyClassic, "metricsTextClassic", state.benchmark, state.commission);
}
function loadMetricsML() {
  return loadMetricsFor(state.metricsStrategyML, "metricsTextML", state.benchmarkML, state.commissionML);
}

function setupMetricsStrategyToggle(containerId, stateKey, onChange) {
  const buttons = document.querySelectorAll(`#${containerId} .segmented-btn`);
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active")) return;
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state[stateKey] = btn.dataset.strategy;
      onChange();
    });
  });
}
setupMetricsStrategyToggle("metricsStrategyToggleClassic", "metricsStrategyClassic", () => {
  drawEquityChartClassic();
  loadMetricsClassic();
});
setupMetricsStrategyToggle("metricsStrategyToggleML", "metricsStrategyML", () => {
  drawEquityChartML();
  loadMetricsML();
});

refreshBacktests();