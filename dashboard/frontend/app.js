// Trading Dashboard — full frontend
const API = "http://localhost:8000";

// ── Active universe ───────────────────────────────────────────────────────────
let activeUniverse = "core";
function qs(extra = {}) {
  return "?" + new URLSearchParams({ universe: activeUniverse, ...extra }).toString();
}

// ── Chart defaults ────────────────────────────────────────────────────────────
const CHART_DEFAULTS = {
  animation: false,
  responsive: true,
  scales: {
    x: { ticks: { color: "#8da0b8", maxTicksLimit: 10, maxRotation: 0, font: { size: 11 } }, grid: { color: "#152035" } },
    y: { ticks: { color: "#8da0b8", font: { size: 11 } }, grid: { color: "#152035" } },
  },
  plugins: { legend: { labels: { color: "#e8edf5", font: { size: 11 }, usePointStyle: true, pointStyleWidth: 10 } } },
};

function pct(v)      { return (v * 100).toFixed(1) + "%"; }
function valClass(v) { return v > 0 ? "pos" : v < 0 ? "neg" : "neu"; }

// ── Health ────────────────────────────────────────────────────────────────────
async function checkHealth() {
  const el = document.getElementById("status");
  try {
    const j = await fetch(`${API}/health`).then(r => r.json());
    el.textContent = "backend: " + j.status;
    el.className = j.status === "ok" ? "ok" : "err";
  } catch {
    el.textContent = "backend not reachable — start uvicorn";
    el.className = "err";
  }
}

// ── Chart mode (line / candlestick) ──────────────────────────────────────────
let chartMode    = "line";
let currentSymbol = "";

function setChartMode(mode) {
  chartMode = mode;
  document.getElementById("btnLine").classList.toggle("active",   mode === "line");
  document.getElementById("btnCandle").classList.toggle("active", mode === "candle");
  loadPriceChart(currentSymbol);
}

// ── Price chart (line + SMA or candlestick) ───────────────────────────────────
let priceChart = null;

async function loadPriceChart(symbol) {
  currentSymbol = symbol;
  const ctx = document.getElementById("priceChart").getContext("2d");
  if (priceChart) priceChart.destroy();

  if (chartMode === "candle") {
    const r = await fetch(`${API}/ohlc/${symbol}${qs()}`);
    if (!r.ok) return;
    const { dates, open, high, low, close } = await r.json();

    const data = dates.map((d, i) => ({
      x: new Date(d).getTime(),
      o: open[i], h: high[i], l: low[i], c: close[i],
    })).filter(d => d.o !== null);

    priceChart = new Chart(ctx, {
      type: "candlestick",
      data: {
        datasets: [{
          label: symbol,
          data,
          color: { up: "#3fb950", down: "#f85149", unchanged: "#8b949e" },
        }],
      },
      options: {
        animation: false,
        responsive: true,
        scales: {
          x: { type: "time", time: { unit: "month" }, ticks: { color: "#8b949e" }, grid: { color: "#21262d" } },
          y: { ticks: { color: "#8b949e" }, grid: { color: "#21262d" } },
        },
        plugins: { legend: { labels: { color: "#e6edf3" } } },
      },
    });
  } else {
    const [pr, ir] = await Promise.all([
      fetch(`${API}/prices/${symbol}${qs()}`),
      fetch(`${API}/indicators/${symbol}${qs({ window: 20 })}`),
    ]);
    const { dates, close } = await pr.json();
    const { sma }          = await ir.json();

    priceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: dates,
        datasets: [
          { label: symbol,   data: close, borderColor: "#58a6ff", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
          { label: "SMA 20", data: sma,   borderColor: "#f0883e", borderWidth: 1.5, pointRadius: 0, tension: 0.1, spanGaps: false },
        ],
      },
      options: { ...CHART_DEFAULTS },
    });
  }
}

// ── Metrics strip ─────────────────────────────────────────────────────────────
function renderMetrics(port, portNet, tik, bench, ew) {
  const items = [
    { label: "Total return", val: pct(port.total_return), cls: valClass(port.total_return),
      sub: `${pct(portNet.total_return)} SMA net · ${pct(tik.total_return)} TikTok · ${pct(bench.total_return)} EGX30 · ${pct(ew.total_return)} EW` },
    { label: "Sharpe ratio", val: port.sharpe.toFixed(2), cls: valClass(port.sharpe),
      sub: `${portNet.sharpe.toFixed(2)} SMA net · ${tik.sharpe.toFixed(2)} TikTok · ${bench.sharpe.toFixed(2)} EGX30 · ${ew.sharpe.toFixed(2)} EW` },
    { label: "Max drawdown", val: pct(port.max_drawdown), cls: "neg",
      sub: `${pct(portNet.max_drawdown)} SMA net · ${pct(tik.max_drawdown)} TikTok · ${pct(bench.max_drawdown)} EGX30 · ${pct(ew.max_drawdown)} EW` },
  ];
  document.getElementById("metricsStrip").innerHTML = items.map(({ label, val, cls, sub }) => `
    <div class="metric">
      <span class="metric-label">${label}</span>
      <div class="metric-row">
        <span class="metric-val ${cls}">${val}</span>
        <span class="metric-sub">${sub}</span>
      </div>
    </div>`).join("");
}

// ── Equity chart ──────────────────────────────────────────────────────────────
let equityChart = null;

async function loadEquityChart() {
  const [br, mr] = await Promise.all([
    fetch(`${API}/backtest${qs()}`),
    fetch(`${API}/metrics${qs()}`),
  ]);
  const { dates, portfolio, portfolio_net, tiktok, benchmark, equal_weight } = await br.json();
  const { portfolio: port, portfolio_net: portNet, tiktok: tik, benchmark: bench, equal_weight: ew } = await mr.json();

  renderMetrics(port, portNet, tik, bench, ew);

  const ctx = document.getElementById("equityChart").getContext("2d");
  if (equityChart) equityChart.destroy();
  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: "SMA (gross)",         data: portfolio,     borderColor: "#3fb950", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "SMA (net 0.5% comm)", data: portfolio_net, borderColor: "#56d364", borderWidth: 1.5, pointRadius: 0, tension: 0.1, borderDash: [5,4] },
        { label: "TikTok (contrarian)", data: tiktok,        borderColor: "#ffa657", borderWidth: 1.5, pointRadius: 0, tension: 0.1, borderDash: [6,3] },
        { label: "EGX30",               data: benchmark,     borderColor: "#f85149", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "Equal weight",        data: equal_weight,  borderColor: "#d2a8ff", borderWidth: 1.5, pointRadius: 0, tension: 0.1, borderDash: [4,3] },
      ],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, title: { display: true, text: "EGP", color: "#8b949e" } } },
    },
  });
}

// ── ML Models chart ───────────────────────────────────────────────────────────
let modelChart = null;

async function loadModelChart() {
  const r = await fetch(`${API}/models`);
  if (!r.ok) return;
  const { dates, lstm, mlp, metrics: mx } = await r.json();

  // Model metrics strip
  const models = [{ key: "lstm", label: "LSTM" }, { key: "mlp", label: "MLP" }];
  document.getElementById("modelMetricsStrip").innerHTML = models.map(({ key, label }) => {
    const mt = mx[key]; if (!mt) return "";
    return `<div class="metric">
      <span class="metric-label">${label}</span>
      <div class="metric-row">
        <span class="metric-val ${valClass(mt.total_return)}">${pct(mt.total_return)}</span>
        <span class="metric-sub">Sharpe ${mt.sharpe.toFixed(2)} · DD ${pct(mt.max_drawdown)}</span>
      </div>
    </div>`;
  }).join("");

  const ctx = document.getElementById("modelChart").getContext("2d");
  if (modelChart) modelChart.destroy();
  modelChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: "LSTM", data: lstm, borderColor: "#79c0ff", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "MLP",  data: mlp,  borderColor: "#ff7b72", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
      ],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, title: { display: true, text: "EGP", color: "#8b949e" } } },
    },
  });
}

// ── Symbol dropdown ───────────────────────────────────────────────────────────
async function refreshSymbolDropdown() {
  const { symbols } = await fetch(`${API}/universe${qs()}`).then(r => r.json());
  const sel = document.getElementById("symbolSelect");
  sel.innerHTML = "";
  symbols.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s; opt.textContent = s;
    sel.appendChild(opt);
  });
  return symbols[0];
}

// ── Universe toggle ───────────────────────────────────────────────────────────
async function switchUniverse(univ) {
  activeUniverse = univ;
  document.querySelectorAll(".univ-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.univ === univ));
  const first = await refreshSymbolDropdown();
  await Promise.all([
    loadPriceChart(first),
    loadEquityChart(),
    loadDrawdownChart(),
    loadRollingChart(),
    loadCorrHeatmap(),
    loadMonthlyHeatmap(),
    loadTradeLog(),
    loadComparisonTable(),
    loadWinrateTable(),
    loadVolatilityChart(),
    loadScatterChart(),
  ]);
  await runCustomBacktest();
}

// ── Drawdown chart ────────────────────────────────────────────────────────────
let drawdownChart = null;

async function loadDrawdownChart() {
  const r = await fetch(`${API}/drawdown${qs()}`);
  if (!r.ok) return;
  const { dates, portfolio, benchmark } = await r.json();

  const ctx = document.getElementById("drawdownChart").getContext("2d");
  if (drawdownChart) drawdownChart.destroy();
  drawdownChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: "Portfolio DD%", data: portfolio, borderColor: "#3fb950", borderWidth: 1.5, pointRadius: 0, tension: 0.1, fill: true, backgroundColor: "rgba(63,185,80,0.08)" },
        { label: "EGX30 DD%",    data: benchmark,  borderColor: "#f85149", borderWidth: 1.5, pointRadius: 0, tension: 0.1, fill: true, backgroundColor: "rgba(248,81,73,0.08)" },
      ],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        y: { ...CHART_DEFAULTS.scales.y, reverse: true, title: { display: true, text: "Drawdown %", color: "#8b949e" } },
      },
    },
  });
}

// ── Rolling Sharpe chart ──────────────────────────────────────────────────────
let rollingChart = null;

async function loadRollingChart() {
  const r = await fetch(`${API}/rolling-sharpe${qs()}`);
  if (!r.ok) return;
  const { dates, sharpe } = await r.json();

  const ctx = document.getElementById("rollingChart").getContext("2d");
  if (rollingChart) rollingChart.destroy();
  rollingChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [{
        label: "Rolling Sharpe (90d)",
        data: sharpe,
        borderColor: "#79c0ff",
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.1,
        spanGaps: false,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        y: {
          ...CHART_DEFAULTS.scales.y,
          title: { display: true, text: "Sharpe", color: "#8b949e" },
        },
      },
      plugins: {
        ...CHART_DEFAULTS.plugins,
        annotation: {},
      },
    },
  });
}

// ── Colour helpers for heatmaps ───────────────────────────────────────────────
function corrColor(v) {
  // -1 → red, 0 → dark, +1 → green
  if (v > 0) return `rgba(63,185,80,${(v * 0.8).toFixed(2)})`;
  return `rgba(248,81,73,${(Math.abs(v) * 0.8).toFixed(2)})`;
}
function retColor(v) {
  if (v > 0) return `rgba(63,185,80,${Math.min(v / 10, 1).toFixed(2)})`;
  return `rgba(248,81,73,${Math.min(Math.abs(v) / 10, 1).toFixed(2)})`;
}

// ── Correlation heatmap ───────────────────────────────────────────────────────
async function loadCorrHeatmap() {
  const r = await fetch(`${API}/correlation${qs()}`);
  if (!r.ok) return;
  const { symbols, matrix } = await r.json();

  const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  let html = `<table class="htable"><thead><tr><th></th>${symbols.map(s => `<th>${s}</th>`).join("")}</tr></thead><tbody>`;
  matrix.forEach((row, i) => {
    html += `<tr><td class="row-label">${symbols[i]}</td>`;
    row.forEach(v => {
      html += `<td style="background:${corrColor(v)}">${v.toFixed(2)}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  document.getElementById("corrHeatmap").innerHTML = html;
}

// ── Monthly returns heatmap ───────────────────────────────────────────────────
async function loadMonthlyHeatmap() {
  const r = await fetch(`${API}/monthly-returns${qs()}`);
  if (!r.ok) return;
  const { years, months, matrix } = await r.json();

  const MONTH_NAMES = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  let html = `<table class="htable"><thead><tr><th>Year</th>${months.map(mo => `<th>${MONTH_NAMES[mo]}</th>`).join("")}</tr></thead><tbody>`;
  matrix.forEach((row, i) => {
    html += `<tr><td class="row-label">${years[i]}</td>`;
    row.forEach(v => {
      const sign = v >= 0 ? "+" : "";
      html += `<td style="background:${retColor(v)}">${sign}${v.toFixed(1)}%</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  document.getElementById("monthlyHeatmap").innerHTML = html;
}

// ── Trade log ─────────────────────────────────────────────────────────────────
async function loadTradeLog() {
  const r = await fetch(`${API}/trades${qs()}`);
  if (!r.ok) return;
  const { trades, total } = await r.json();

  let html = `<p style="font-size:0.72rem;color:#8b949e;margin-bottom:8px;">Showing last ${trades.length} of ${total} total trades</p>`;
  html += `<table class="trade-table"><thead><tr>
    <th>Date</th><th>Symbol</th><th>Action</th><th>Price (EGP)</th>
  </tr></thead><tbody>`;
  trades.forEach(t => {
    const cls = t.action === "BUY" ? "buy" : "sell";
    html += `<tr>
      <td>${t.date}</td>
      <td>${t.symbol}</td>
      <td class="${cls}">${t.action}</td>
      <td>${t.price ?? "—"}</td>
    </tr>`;
  });
  html += "</tbody></table>";
  document.getElementById("tradeLog").innerHTML = html;
}

// ── Risk/Return Scatter ───────────────────────────────────────────────────────
let scatterChart = null;

async function loadScatterChart() {
  const r = await fetch(`${API}/scatter${qs()}`);
  if (!r.ok) return;
  const { points } = await r.json();

  const ctx = document.getElementById("scatterChart").getContext("2d");
  if (scatterChart) scatterChart.destroy();

  scatterChart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: points.map(p => ({
        label:           p.label,
        data:            [{ x: p.x, y: p.y }],
        backgroundColor: p.color,
        borderColor:     p.color,
        pointRadius:     8,
        pointHoverRadius:10,
      })),
    },
    options: {
      animation: false,
      responsive: true,
      scales: {
        x: {
          title: { display: true, text: "Volatility % (ann.)", color: "#8b949e" },
          ticks: { color: "#8b949e" }, grid: { color: "#21262d" },
        },
        y: {
          title: { display: true, text: "Ann. Return %", color: "#8b949e" },
          ticks: { color: "#8b949e" }, grid: { color: "#21262d" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e6edf3", usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = points[ctx.datasetIndex];
              return `${p.label} — Return: ${p.y}%  Vol: ${p.x}%  Sharpe: ${p.sharpe}`;
            },
          },
        },
      },
    },
  });
}

// ── CSV Export ────────────────────────────────────────────────────────────────
function downloadCSV(filename, rows) {
  const csv  = rows.map(r => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

async function exportEquityCSV() {
  const r = await fetch(`${API}/backtest${qs()}`);
  if (!r.ok) return;
  const { dates, portfolio, portfolio_net, tiktok, benchmark, equal_weight } = await r.json();
  const rows = [
    ["date","sma_gross","sma_net","tiktok","egx30","equal_weight"],
    ...dates.map((d, i) => [d, portfolio[i], portfolio_net[i], tiktok[i], benchmark[i], equal_weight[i]]),
  ];
  downloadCSV(`equity_${activeUniverse}_${new Date().toISOString().slice(0,10)}.csv`, rows);
}

async function exportTradeCSV() {
  const r = await fetch(`${API}/trades${qs({ max_rows: 10000 })}`);
  if (!r.ok) return;
  const { trades } = await r.json();
  const rows = [
    ["date","symbol","action","price"],
    ...trades.map(t => [t.date, t.symbol, t.action, t.price ?? ""]),
  ];
  downloadCSV(`trades_${activeUniverse}_${new Date().toISOString().slice(0,10)}.csv`, rows);
}

// ── Strategy Comparison Table ─────────────────────────────────────────────────
async function loadComparisonTable() {
  const r = await fetch(`${API}/comparison${qs()}`);
  if (!r.ok) return;
  const { rows } = await r.json();

  // Find best value per metric column (higher is better except drawdown & vol)
  const metrics = ["total_return","ann_return","sharpe","max_drawdown","volatility"];
  const higherBetter = { total_return:true, ann_return:true, sharpe:true, max_drawdown:false, volatility:false };
  const best = {};
  metrics.forEach(k => {
    const vals = rows.map(r => r[k]);
    best[k] = higherBetter[k] ? Math.max(...vals) : Math.min(...vals);
  });

  const headers = ["Strategy","Total Return","Ann. Return","Sharpe","Max Drawdown","Volatility"];
  let html = `<table class="cmp-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>`;
  rows.forEach(row => {
    html += `<tr>
      <td>${row.strategy}</td>
      <td class="${row.total_return  === best.total_return  ? 'best':''}">${row.total_return  > 0 ? '+':''}${row.total_return}%</td>
      <td class="${row.ann_return    === best.ann_return    ? 'best':''}">${row.ann_return    > 0 ? '+':''}${row.ann_return}%</td>
      <td class="${row.sharpe        === best.sharpe        ? 'best':''}">${row.sharpe}</td>
      <td class="${row.max_drawdown  === best.max_drawdown  ? 'best':''}">${row.max_drawdown}%</td>
      <td class="${row.volatility    === best.volatility    ? 'best':''}">${row.volatility}%</td>
    </tr>`;
  });
  html += "</tbody></table>";
  document.getElementById("comparisonTable").innerHTML = html;
}

// ── Win Rate Table ────────────────────────────────────────────────────────────
async function loadWinrateTable() {
  const r = await fetch(`${API}/winrate${qs()}`);
  if (!r.ok) return;
  const { rows } = await r.json();

  const headers = ["Strategy","Win Rate","Avg Win","Avg Loss","Profit Factor","Days"];
  let html = `<table class="cmp-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>`;
  rows.forEach(row => {
    const pfClass = row.profit_factor >= 1.5 ? "best" : "";
    const wrClass = row.win_rate >= 50 ? "best" : "";
    html += `<tr>
      <td>${row.strategy}</td>
      <td class="${wrClass}">${row.win_rate}%</td>
      <td style="color:#3fb950">+${row.avg_win}%</td>
      <td style="color:#f85149">${row.avg_loss}%</td>
      <td class="${pfClass}">${row.profit_factor}</td>
      <td>${row.total_trades}</td>
    </tr>`;
  });
  html += "</tbody></table>";
  document.getElementById("winrateTable").innerHTML = html;
}

// ── Volatility Chart ──────────────────────────────────────────────────────────
let volatilityChart = null;

async function loadVolatilityChart() {
  const r = await fetch(`${API}/volatility${qs()}`);
  if (!r.ok) return;
  const { dates, portfolio, benchmark } = await r.json();

  const ctx = document.getElementById("volatilityChart").getContext("2d");
  if (volatilityChart) volatilityChart.destroy();
  volatilityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: "Portfolio Vol%", data: portfolio, borderColor: "#3fb950", borderWidth: 1.5, pointRadius: 0, tension: 0.1, spanGaps: false },
        { label: "EGX30 Vol%",    data: benchmark,  borderColor: "#f85149", borderWidth: 1.5, pointRadius: 0, tension: 0.1, spanGaps: false },
      ],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        y: { ...CHART_DEFAULTS.scales.y, title: { display: true, text: "Ann. Vol %", color: "#8b949e" } },
      },
    },
  });
}

// ── Strategy Parameters Panel ─────────────────────────────────────────────────
let paramChart = null;

async function runCustomBacktest() {
  const fast = parseInt(document.getElementById("paramFast").value);
  const slow = parseInt(document.getElementById("paramSlow").value);
  const metricsEl = document.getElementById("paramMetrics");

  if (fast >= slow) {
    metricsEl.textContent = "⚠ Fast must be less than Slow.";
    metricsEl.style.color = "#f85149";
    return;
  }

  metricsEl.textContent = "Running…";
  metricsEl.style.color = "#8b949e";

  const r = await fetch(`${API}/backtest/custom${qs({ fast, slow })}`);
  if (!r.ok) { metricsEl.textContent = "Error"; return; }
  const { dates, portfolio, benchmark, metrics: mt, params } = await r.json();

  metricsEl.innerHTML = `SMA(${params.fast},${params.slow}) — `
    + `Return: <span style="color:${mt.total_return>=0?'#3fb950':'#f85149'}">${mt.total_return>0?'+':''}${mt.total_return}%</span> · `
    + `Sharpe: <span style="color:#79c0ff">${mt.sharpe}</span> · `
    + `MaxDD: <span style="color:#f85149">${mt.max_drawdown}%</span>`;

  const ctx = document.getElementById("paramChart").getContext("2d");
  if (paramChart) paramChart.destroy();
  paramChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: `SMA(${params.fast},${params.slow}) net`, data: portfolio, borderColor: "#58a6ff", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "EGX30", data: benchmark, borderColor: "#f85149", borderWidth: 1.4, pointRadius: 0, tension: 0.1 },
      ],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        y: { ...CHART_DEFAULTS.scales.y, title: { display: true, text: "EGP", color: "#8b949e" } },
      },
    },
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  await checkHealth();
  document.querySelectorAll(".univ-btn").forEach(btn =>
    btn.addEventListener("click", () => switchUniverse(btn.dataset.univ)));
  document.getElementById("symbolSelect").addEventListener("change", e =>
    loadPriceChart(e.target.value));
  document.getElementById("paramRun").addEventListener("click", runCustomBacktest);

  const first = await refreshSymbolDropdown();
  await Promise.all([
    loadPriceChart(first),
    loadEquityChart(),
    loadModelChart(),
    loadDrawdownChart(),
    loadRollingChart(),
    loadCorrHeatmap(),
    loadMonthlyHeatmap(),
    loadTradeLog(),
    loadComparisonTable(),
    loadWinrateTable(),
    loadVolatilityChart(),
    loadScatterChart(),
  ]);
  // Run default params chart
  await runCustomBacktest();
  renderQuickQuestions();
}

init();

// ── Chatbot ───────────────────────────────────────────────────────────────────
const QUICK_QUESTIONS = [
  "إيه أحسن استراتيجية؟",
  "قارن بين SMA و TikTok",
  "إيه تأثير الـ commission؟",
  "إيه معنى الـ Sharpe ratio؟",
  "أنهي سهم الأفضل؟",
  "فسرلي الـ Max Drawdown",
];

// Chat history stored in memory
let chatHistory = [];

function toggleChat() {
  const win = document.getElementById("chatWindow");
  win.classList.toggle("open");
  if (win.classList.contains("open")) {
    document.getElementById("chatInput").focus();
  }
}

function appendMsg(text, role) {
  const messages = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  // Render markdown-style bold (**text**)
  div.innerHTML = text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function renderQuickQuestions() {
  const container = document.getElementById("quickQuestions");
  if (!container) return;
  container.innerHTML = QUICK_QUESTIONS.map(q => `
    <button class="quick-q" onclick="askQuick('${q}')">${q}</button>
  `).join("");
}

function askQuick(question) {
  document.getElementById("chatInput").value = question;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById("chatInput");
  const btn   = document.getElementById("chatSend");
  const msg   = input.value.trim();
  if (!msg) return;

  input.value  = "";
  btn.disabled = true;

  // Hide quick questions after first message
  const qq = document.getElementById("quickQuestions");
  if (qq) qq.style.display = "none";

  appendMsg(msg, "user");
  const thinking = appendMsg("جاري التفكير…", "thinking");

  // Add to history
  chatHistory.push({ role: "user", text: msg });

  try {
    const r = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message:  msg,
        universe: activeUniverse,
        history:  chatHistory.slice(-10),
      }),
    });
    const { reply } = await r.json();
    thinking.remove();
    appendMsg(reply, "bot");
    chatHistory.push({ role: "bot", text: reply });
  } catch (e) {
    thinking.remove();
    appendMsg("حدث خطأ — تأكد إن الـ backend شغال.", "bot");
  } finally {
    btn.disabled = false;
    input.focus();
  }
}

function clearChat() {
  chatHistory = [];
  const messages = document.getElementById("chatMessages");
  messages.innerHTML = `<div class="msg bot">
    مرحباً! أنا مساعدك لتحليل بيانات البورصة المصرية.<br>
    اسألني عن أي استراتيجية أو سهم أو مقياس في الداشبورد. 📊
  </div>`;
  const qq = document.getElementById("quickQuestions");
  if (qq) qq.style.display = "flex";
}
