// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";
let priceChart;
let equityChart;

Chart.defaults.color = "#91a4ba";
Chart.defaults.borderColor = "rgba(145, 164, 186, 0.12)";

async function checkHealth() {
  try {
    const response = await fetch(`${API}/health`);
    const result = await response.json();
    document.getElementById("status").textContent = `backend: ${result.status}`;
  } catch (error) {
    document.getElementById("status").textContent = "backend not reachable — start uvicorn";
  }
}

async function drawPriceChart(symbol) {
  const [pricesResponse, indicatorsResponse] = await Promise.all([
    fetch(`${API}/prices/${symbol}`),
    fetch(`${API}/indicators/${symbol}?window=20`),
  ]);
  const [prices, indicators] = await Promise.all([
    pricesResponse.json(),
    indicatorsResponse.json(),
  ]);

  if (priceChart) priceChart.destroy();
  priceChart = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: prices.dates,
      datasets: [
        {
          label: `${symbol} close`,
          data: prices.close,
          borderColor: "#58a6ff",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: `${symbol} SMA (20)`,
          data: indicators.sma,
          borderColor: "#f2cc60",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        title: { display: true, text: `${symbol} Closing Price & SMA` },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { title: { display: true, text: "EGP" } },
      },
    },
  });
}

async function initializeSymbolSelect() {
  const response = await fetch(`${API}/universe`);
  const symbols = await response.json();
  const select = document.getElementById("symbolSelect");

  for (const symbol of symbols) {
    select.add(new Option(symbol, symbol));
  }
  select.addEventListener("change", () => drawPriceChart(select.value));
  await drawPriceChart(symbols[0]);
}

async function drawEquityChart() {
  const response = await fetch(`${API}/backtest`);
  const result = await response.json();

  if (equityChart) equityChart.destroy();
  equityChart = new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: result.dates,
      datasets: [
        {
          label: "SMA crossover strategy",
          data: result.portfolio,
          borderColor: "#3fb950",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: "EGX30 benchmark",
          data: result.benchmark,
          borderColor: "#d29922",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        title: { display: true, text: "1,000 EGP Growth" },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { title: { display: true, text: "EGP" } },
      },
    },
  });
}

async function loadMetrics() {
  const response = await fetch(`${API}/metrics`);
  const metrics = await response.json();
  document.getElementById("totalReturn").textContent = `${(metrics.total_return * 100).toFixed(1)}%`;
  document.getElementById("sharpe").textContent = metrics.sharpe.toFixed(3);
  document.getElementById("maxDrawdown").textContent = `${(metrics.max_drawdown * 100).toFixed(1)}%`;
}

async function loadFeatures() {
  const response = await fetch(`${API}/features`);
  const features = await response.json();
  const entries = Object.entries(features);
  const maxAbsoluteValue = Math.max(...entries.map(([, value]) => Math.abs(value)), 1e-12);
  const list = document.getElementById("featureList");

  for (const [name, value] of entries) {
    const row = document.createElement("div");
    row.className = "feature-row";

    const label = document.createElement("span");
    label.className = "feature-name";
    label.textContent = name;
    label.title = name;

    const track = document.createElement("div");
    track.className = "feature-track";
    const bar = document.createElement("span");
    bar.className = `feature-bar${value < 0 ? " negative" : ""}`;
    bar.style.width = `${Math.abs(value) / maxAbsoluteValue * 50}%`;
    if (value < 0) {
      bar.style.right = "50%";
    } else {
      bar.style.left = "50%";
    }
    track.appendChild(bar);

    const number = document.createElement("span");
    number.className = "feature-value";
    number.textContent = Number(value).toFixed(4);

    row.append(label, track, number);
    list.appendChild(row);
  }
}

checkHealth();
initializeSymbolSelect();
drawEquityChart();
loadMetrics();
loadFeatures();
// TASK_07+ : render additional dashboard panels.
