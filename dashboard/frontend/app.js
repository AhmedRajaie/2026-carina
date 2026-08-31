// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";
let priceChart;

async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const j = await r.json();
    document.getElementById("status").textContent = "backend: " + j.status;
  } catch (e) {
    document.getElementById("status").textContent = "backend not reachable — start uvicorn";
  }
}
checkHealth();

async function loadPriceChart(symbol) {
  let prices;
  let indicators;

  if (symbol === "FULL_MARKET") {
    const marketResponse = await fetch(`${API}/market`);
    prices = await marketResponse.json();
    const marketIndicatorsResponse = await fetch(`${API}/indicators/full_market?window=20`);
    indicators = await marketIndicatorsResponse.json();
  } else {
    const pricesResponse = await fetch(`${API}/prices/${symbol}`);
    prices = await pricesResponse.json();
    const indicatorsResponse = await fetch(`${API}/indicators/${symbol}?window=20`);
    indicators = await indicatorsResponse.json();
  }

  if (priceChart) {
    priceChart.destroy();
  }

  const label = symbol === "FULL_MARKET" ? "EGX full market" : symbol;
  document.getElementById("priceTitle").textContent = `${label} closing price and 20-day SMA`;
  priceChart = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: prices.dates,
      datasets: [{
        label: `${label} close`,
        data: prices.close,
        borderColor: "#58a6ff",
        backgroundColor: "rgba(88, 166, 255, 0.15)",
        pointRadius: 0,
        tension: 0.15,
        fill: true,
      }, {
        label: `${label} SMA (20)`,
        data: indicators.sma,
        borderColor: "#f2cc60",
        pointRadius: 0,
        tension: 0.15,
        fill: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
    },
  });
}

async function setupSymbolSelector() {
  const response = await fetch(`${API}/universe`);
  const symbols = await response.json();
  const select = document.getElementById("symbolSelect");

  const fullMarketOption = document.createElement("option");
  fullMarketOption.value = "FULL_MARKET";
  fullMarketOption.textContent = "Full market";
  select.appendChild(fullMarketOption);

  symbols.forEach((symbol) => {
    const option = document.createElement("option");
    option.value = symbol;
    option.textContent = symbol;
    select.appendChild(option);
  });

  select.addEventListener("change", () => loadPriceChart(select.value));
  select.value = "FULL_MARKET";
  await loadPriceChart("FULL_MARKET");
}

setupSymbolSelector();

async function loadEquityChart() {
  const response = await fetch(`${API}/backtest`);
  const result = await response.json();

  new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: result.dates,
      datasets: [{
        label: "SMA strategy",
        data: result.portfolio,
        borderColor: "#7ee787",
        pointRadius: 0,
        tension: 0.15,
      }, {
        label: "EGX30 benchmark",
        data: result.benchmark,
        borderColor: "#ff7b72",
        pointRadius: 0,
        tension: 0.15,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        title: {
          display: true,
          text: "Strategy vs EGX30 Equity (EGP)",
        },
      },
      scales: {
        y: {
          title: {
            display: true,
            text: "EGP",
          },
        },
      },
    },
  });
}

loadEquityChart();

async function loadMetrics() {
  const response = await fetch(`${API}/metrics`);
  const metrics = await response.json();
  document.getElementById("totalReturn").textContent = `${(metrics.total_return * 100).toFixed(1)}%`;
  document.getElementById("sharpe").textContent = metrics.sharpe.toFixed(3);
  document.getElementById("maxDrawdown").textContent = `${(metrics.max_drawdown * 100).toFixed(1)}%`;
}

loadMetrics();
