// Dashboard frontend for the full demo controls.
const API = "http://localhost:8000";
let priceChart;
let equityChart;

async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const j = await r.json();
    document.getElementById("status").textContent = "backend: " + j.status;
  } catch (e) {
    document.getElementById("status").textContent = "backend not reachable — start uvicorn";
  }
}

async function populateUniverseSelector() {
  const select = document.getElementById("symbolSelect");
  const response = await fetch(`${API}/full_market_universe`);
  const fullMarket = await response.json();
  const defaultSymbols = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"];

  const fullMarketOption = document.createElement("option");
  fullMarketOption.value = "full_market";
  fullMarketOption.textContent = "Full Market";
  select.appendChild(fullMarketOption);

  defaultSymbols.forEach((symbol) => {
    const option = document.createElement("option");
    option.value = symbol;
    option.textContent = symbol;
    select.appendChild(option);
  });

  fullMarket.forEach((symbol) => {
    if (!defaultSymbols.includes(symbol)) {
      const option = document.createElement("option");
      option.value = symbol;
      option.textContent = symbol;
      select.appendChild(option);
    }
  });

  select.value = "full_market";
}

async function loadPriceChart() {
  try {
    const symbol = document.getElementById("symbolSelect").value || "full_market";
    let seriesSymbol = symbol;
    if (symbol === "full_market") {
      seriesSymbol = "COMI";
    }

    const pricesResponse = await fetch(`${API}/prices/${seriesSymbol}`);
    const prices = await pricesResponse.json();
    const indicatorsResponse = await fetch(`${API}/indicators/${seriesSymbol}?window=20`);
    const indicators = await indicatorsResponse.json();

    if (priceChart) {
      priceChart.destroy();
    }

    priceChart = new Chart(document.getElementById("priceChart"), {
      type: "line",
      data: {
        labels: prices.dates,
        datasets: [{
          label: `${seriesSymbol} close`,
          data: prices.close,
          borderColor: "#58a6ff",
          backgroundColor: "rgba(88, 166, 255, 0.15)",
          pointRadius: 0,
          tension: 0.15,
          fill: true,
        }, {
          label: `${seriesSymbol} SMA (20)`,
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
  } catch (e) {
    document.getElementById("status").textContent = "backend not reachable — start uvicorn";
  }
}

async function loadEquityChart() {
  try {
    const benchmark = document.getElementById("benchmarkSelect").value;
    const capital = document.getElementById("capitalInput").value || 1000;
    const commission = document.getElementById("commissionInput").value || 0.005;
    const universe = document.getElementById("symbolSelect").value || "full_market";

    const response = await fetch(`${API}/backtest?universe=${encodeURIComponent(universe)}&benchmark=${encodeURIComponent(benchmark)}&initial_capital=${encodeURIComponent(capital)}&commission=${encodeURIComponent(commission)}`);
    const result = await response.json();

    if (equityChart) {
      equityChart.destroy();
    }

    equityChart = new Chart(document.getElementById("equityChart"), {
      type: "line",
      data: {
        labels: result.dates,
        datasets: [{
          label: "TikTok strategy",
          data: result.portfolio,
          borderColor: "#7ee787",
          pointRadius: 0,
          tension: 0.15,
        }, {
          label: benchmark === "equal_weight" ? "Equal Weight" : "Equal Balance",
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
            text: `Strategy vs ${benchmark === "equal_weight" ? "Equal Weight" : "Equal Balance"} (${capital} EGP)`,
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

    document.getElementById("totalReturn").textContent = `${(result.return_percentage).toFixed(1)}%`;
    document.getElementById("finalPortfolioValue").textContent = `EGP ${result.final_portfolio_value.toFixed(0)}`;
    document.getElementById("finalBenchmarkValue").textContent = `EGP ${result.final_benchmark_value.toFixed(0)}`;
    document.getElementById("profit").textContent = `EGP ${result.profit.toFixed(0)}`;
  } catch (e) {
    document.getElementById("status").textContent = "backend not reachable — start uvicorn";
  }
}

async function refreshDashboard() {
  await loadPriceChart();
  await loadEquityChart();
}

document.getElementById("symbolSelect").addEventListener("change", refreshDashboard);
document.getElementById("benchmarkSelect").addEventListener("change", refreshDashboard);
document.getElementById("capitalInput").addEventListener("change", refreshDashboard);
document.getElementById("commissionInput").addEventListener("change", refreshDashboard);
document.getElementById("runBacktestBtn").addEventListener("click", refreshDashboard);

checkHealth();
populateUniverseSelector().then(refreshDashboard);
