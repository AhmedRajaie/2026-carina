// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";

async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const j = await r.json();
    document.getElementById("status").textContent = "backend: " + j.status;
  } catch (e) {
    document.getElementById("status").textContent = "backend not reachable — start uvicorn";
  }
}

let priceChart;

async function renderPriceChart(symbol) {
  const pricesResponse = await fetch(`${API}/prices/${symbol}`);
  const prices = await pricesResponse.json();
  const indicatorsResponse = await fetch(`${API}/indicators/${symbol}?window=20`);
  const indicators = await indicatorsResponse.json();

  if (priceChart) priceChart.destroy();
  priceChart = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: prices.dates,
      datasets: [{
        label: `${symbol} close`,
        data: prices.close,
        borderColor: "#58a6ff",
        backgroundColor: "rgba(88, 166, 255, 0.15)",
        fill: true,
        pointRadius: 0,
        tension: 0.2,
      }, {
        label: `${symbol} SMA (20)`,
        data: indicators.sma,
        borderColor: "#f2cc60",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: false } },
    },
  });
}

async function renderEquityChart() {
  const [backtestResponse, metricsResponse] = await Promise.all([
    fetch(`${API}/backtest`),
    fetch(`${API}/metrics`),
  ]);
  const result = await backtestResponse.json();
  const metrics = await metricsResponse.json();

  document.getElementById("totalReturn").textContent = `${metrics.total_return} (${(metrics.total_return * 100).toFixed(1)}%)`;
  document.getElementById("sharpe").textContent = metrics.sharpe;
  document.getElementById("maxDrawdown").textContent = `${metrics.max_drawdown} (${(metrics.max_drawdown * 100).toFixed(1)}%)`;

  new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: result.dates,
      datasets: [{
        label: "SMA strategy",
        data: result.portfolio,
        borderColor: "#58a6ff",
        pointRadius: 0,
        tension: 0.2,
      }, {
        label: "EGX30 benchmark",
        data: result.benchmark,
        borderColor: "#f0883e",
        pointRadius: 0,
        tension: 0.2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { title: { display: true, text: "Strategy vs EGX30 Equity (EGP)" } },
      scales: {
        y: { beginAtZero: false, title: { display: true, text: "EGP" } },
      },
    },
  });
}

checkHealth();
fetch(`${API}/universe`).then((response) => response.json()).then((symbols) => {
  const selector = document.getElementById("symbolSelect");
  symbols.forEach((symbol) => selector.add(new Option(symbol, symbol)));
  selector.addEventListener("change", () => renderPriceChart(selector.value));
  return renderPriceChart(symbols[0]);
}).catch(() => {
  document.getElementById("status").textContent = "price data not reachable";
});
renderEquityChart().catch(() => {
  document.getElementById("status").textContent = "backtest data not reachable";
});
