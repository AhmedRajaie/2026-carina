// Dashboard frontend — Task 05 polish
const API = "http://localhost:8000";

// Keep chart instances so we can destroy before redrawing
let priceChartInstance = null;
let rsiChartInstance   = null;
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
async function drawEquityChart(strategy = "sma") {
  const endpoint = strategy === "dip" ? `${API}/backtest/dip` : `${API}/backtest`;
  const r    = await fetch(endpoint);
  const data = await r.json();

  const labels = {
    sma: "SMA Crossover",
    dip: "Dip-Buy (−5% / +10%)",
  };

  if (equityChartInstance) equityChartInstance.destroy();
  equityChartInstance = new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: data.dates,
      datasets: [
        {
          label: labels[strategy],
          data: data.portfolio,
          borderColor: "#26c466",
          backgroundColor: "rgba(38,196,102,0.08)",
          fill: true,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
        {
          label: "Benchmark — EGX30",
          data: data.benchmark_egx30,
          borderColor: "#ff4d6a",
          backgroundColor: "rgba(255,77,106,0.04)",
          fill: false,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
        {
          label: "Benchmark — Equal Weight",
          data: data.benchmark_equal,
          borderColor: "#a78bfa",
          backgroundColor: "rgba(167,139,250,0.04)",
          fill: false,
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: baseOptions("EGP"),
  });
}

// ── metrics cards ─────────────────────────────────────────────────
async function loadMetrics(strategy = "sma") {
  try {
    const r = await fetch(`${API}/metrics?strategy=${strategy}`);
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

    const commEl = document.getElementById("mCommission");
    commEl.textContent = (m.commission * 100).toFixed(1) + "%";
    commEl.className   = "metric-value";
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

  select.addEventListener("change", () => {
    drawPriceChart(select.value);
    drawRsiChart(select.value);
  });
  return symbols[0];
}

// ── RSI chart ─────────────────────────────────────────────────────
async function drawRsiChart(symbol) {
  const r    = await fetch(`${API}/indicators/${symbol}/rsi`);
  const data = await r.json();

  document.getElementById("rsiTitle").textContent = `${symbol} — RSI (14)`;

  if (rsiChartInstance) rsiChartInstance.destroy();
  rsiChartInstance = new Chart(document.getElementById("rsiChart"), {
    type: "line",
    data: {
      labels: data.dates,
      datasets: [
        {
          label: "RSI 14",
          data: data.rsi,
          borderColor: "#ffb84d",
          borderWidth: 1.8,
          pointRadius: 0,
          tension: 0.15,
          fill: false,
        },
        // Overbought line at 70
        {
          label: "Overbought (70)",
          data: data.dates.map(() => 70),
          borderColor: "rgba(255,77,106,0.5)",
          borderWidth: 1,
          borderDash: [4, 3],
          pointRadius: 0,
          fill: false,
        },
        // Oversold line at 30
        {
          label: "Oversold (30)",
          data: data.dates.map(() => 30),
          borderColor: "rgba(38,196,102,0.5)",
          borderWidth: 1,
          borderDash: [4, 3],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      ...baseOptions("RSI"),
      plugins: {
        ...baseOptions().plugins,
        annotation: {},   // placeholder for future annotation plugin
      },
      scales: {
        x: {
          ticks: { color: TICK_COLOR, font: { family: FONT_FAMILY, size: 11 }, maxTicksLimit: 10 },
          grid: { color: GRID_COLOR },
        },
        y: {
          min: 0,
          max: 100,
          ticks: { color: TICK_COLOR, font: { family: FONT_FAMILY, size: 11 },
                   callback: v => v },
          grid: { color: GRID_COLOR },
        },
      },
    },
  });
}

// ── live signals table ────────────────────────────────────────────
async function loadSignals() {
  const tbody = document.getElementById("signalsBody");
  try {
    const r    = await fetch(`${API}/signals`);
    const rows = await r.json();

    if (rows.length) {
      document.getElementById("signalsDate").textContent =
        "as of " + rows[0].date;
    }

    tbody.innerHTML = rows.map(row => {
      // Return colour
      const retClass = row.return_pct > 0 ? "lb-positive"
                     : row.return_pct < 0 ? "lb-negative" : "";
      const retStr = (row.return_pct > 0 ? "+" : "") + row.return_pct.toFixed(2) + "%";

      // RSI zone
      const rsiVal = row.rsi ?? "—";
      let rsiZone = "—", rsiClass = "";
      if (row.rsi !== null) {
        if (row.rsi >= 70)      { rsiZone = "Overbought"; rsiClass = "rsi-ob"; }
        else if (row.rsi <= 30) { rsiZone = "Oversold";   rsiClass = "rsi-os"; }
        else                    { rsiZone = "Neutral";     rsiClass = "rsi-mid"; }
      }

      // SMA signal
      const smaClass = row.sma_signal === "BUY" ? "sig-buy" : "sig-cash";

      // Dip-buy signal
      const dipClass = row.dip_signal === "BUY" ? "sig-buy" : "sig-hold";

      return `<tr>
        <td style="font-weight:600">${row.symbol}</td>
        <td class="${retClass}">${retStr}</td>
        <td>${rsiVal}</td>
        <td class="${rsiClass}">${rsiZone}</td>
        <td class="${smaClass}">${row.sma_signal}</td>
        <td class="${dipClass}">${row.dip_signal}</td>
      </tr>`;
    }).join("");
  } catch {
    tbody.innerHTML =
      `<tr><td colspan="6" style="text-align:center;color:#ff4d6a;">failed to load</td></tr>`;
  }
}
async function loadLeaderboard() {
  const tbody = document.getElementById("leaderboardBody");
  try {
    const r    = await fetch(`${API}/leaderboard`);
    const rows = await r.json();

    tbody.innerHTML = rows.map(row => {
      const totalRetClass = row.total_return >= 0 ? "lb-positive" : "lb-negative";
      const sharpeClass   = row.sharpe >= 1 ? "lb-positive" : row.sharpe < 0 ? "lb-negative" : "";
      const ddClass       = "lb-negative";
      const medal         = row.rank === 1 ? "🥇" : row.rank === 2 ? "🥈" : row.rank === 3 ? "🥉" : row.rank;

      return `<tr class="rank-${row.rank}">
        <td>${medal}</td>
        <td>${row.name}</td>
        <td>${row.final_value.toLocaleString()} EGP</td>
        <td class="${totalRetClass}">${(row.total_return * 100).toFixed(1)}%</td>
        <td class="${sharpeClass}">${row.sharpe.toFixed(2)}</td>
        <td class="${ddClass}">${(row.max_drawdown * 100).toFixed(1)}%</td>
      </tr>`;
    }).join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#ff4d6a;">failed to load</td></tr>`;
  }
}
async function init() {
  await checkHealth();
  const firstSymbol = await buildDropdown();

  // Wire strategy switcher
  const strategySelect = document.getElementById("strategySelect");
  strategySelect.addEventListener("change", () => {
    const s = strategySelect.value;
    drawEquityChart(s);
    loadMetrics(s);
  });

  await Promise.all([
    drawPriceChart(firstSymbol),
    drawRsiChart(firstSymbol),
    drawEquityChart(strategySelect.value),
    loadMetrics(strategySelect.value),
    loadSignals(),
    loadLeaderboard(),
  ]);
}

init();
