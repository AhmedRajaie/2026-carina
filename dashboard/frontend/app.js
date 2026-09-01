// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";
let priceChart;
let equityChart;
let tiktokChart;
let modelLossChart;
let currentScope = "core";
let currentBenchmark = "egx30";
let latestSmaMetrics;
let latestTikTokResult;

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

async function drawPriceChart(symbol, scope = currentScope) {
  const [pricesResponse, indicatorsResponse] = await Promise.all([
    fetch(`${API}/prices/${encodeURIComponent(symbol)}?scope=${scope}`),
    fetch(`${API}/indicators/${encodeURIComponent(symbol)}?window=20&scope=${scope}`),
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

async function loadUniverse(scope) {
  const response = await fetch(`${API}/universe?scope=${scope}`);
  const symbols = await response.json();
  const select = document.getElementById("symbolSelect");
  const previousSymbol = select.value;
  select.replaceChildren();

  for (const symbol of symbols) {
    select.add(new Option(symbol, symbol));
  }
  select.value = symbols.includes(previousSymbol) ? previousSymbol : symbols[0];
  document.getElementById("equitySubtitle").textContent =
    `${scope === "full" ? "Full market" : "Core universe"} (${symbols.length} assets) · Starting capital: 1,000 EGP`;

  await Promise.all([
    drawPriceChart(select.value, scope),
    drawEquityChart(scope),
    loadMetrics(scope),
  ]);
}

async function initializeUniverseControls() {
  const universeSelect = document.getElementById("universeSelect");
  const benchmarkSelect = document.getElementById("benchmarkSelect");
  const symbolSelect = document.getElementById("symbolSelect");
  universeSelect.addEventListener("change", async () => {
    currentScope = universeSelect.value;
    await loadUniverse(currentScope);
  });
  benchmarkSelect.addEventListener("change", async () => {
    currentBenchmark = benchmarkSelect.value;
    await drawEquityChart(currentScope, currentBenchmark);
  });
  symbolSelect.addEventListener("change", () => drawPriceChart(symbolSelect.value));
  await loadUniverse(currentScope);
}

async function drawEquityChart(scope = currentScope, benchmark = currentBenchmark) {
  const response = await fetch(`${API}/backtest?scope=${scope}&benchmark=${benchmark}`);
  const result = await response.json();
  const assetCount = document.getElementById("symbolSelect").options.length;
  document.getElementById("equitySubtitle").textContent =
    `${scope === "full" ? "Full market" : "Core universe"} (${assetCount} assets) · ` +
    `Starting capital: 1,000 EGP · Commission: ${(result.commission * 100).toFixed(1)}% per turnover`;
  const benchmarkLabel = benchmark === "equal_weight"
    ? "Equal-weight benchmark"
    : "EGX30 benchmark";

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
          label: benchmarkLabel,
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

async function loadMetrics(scope = currentScope) {
  const response = await fetch(`${API}/metrics?scope=${scope}`);
  const metrics = await response.json();
  latestSmaMetrics = metrics;
  document.getElementById("totalReturn").textContent = `${(metrics.total_return * 100).toFixed(1)}%`;
  document.getElementById("sharpe").textContent = metrics.sharpe.toFixed(3);
  document.getElementById("maxDrawdown").textContent = `${(metrics.max_drawdown * 100).toFixed(1)}%`;
  renderStrategyComparison();
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

async function loadModelComparison() {
  const response = await fetch(`${API}/compare`);
  if (!response.ok) throw new Error("Model comparison failed");
  const comparison = await response.json();

  // Render loss curves if available
  if (comparison.lstm_train_losses && comparison.lstm_test_losses) {
    const epochs = Array.from({ length: comparison.lstm_train_losses.length }, (_, i) => i + 1);
    if (modelLossChart) modelLossChart.destroy();
    modelLossChart = new Chart(document.getElementById("modelLossChart"), {
      type: "line",
      data: {
        labels: epochs,
        datasets: [
          {
            label: "LSTM train loss",
            data: comparison.lstm_train_losses,
            borderColor: "#bc8cff",
            backgroundColor: "rgba(188, 140, 255, 0.08)",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
          },
          {
            label: "LSTM test loss",
            data: comparison.lstm_test_losses,
            borderColor: "#f2cc60",
            backgroundColor: "rgba(242, 204, 96, 0.08)",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          title: { display: false },
          legend: { display: true, position: "top" },
        },
        scales: {
          y: {
            type: "linear",
            title: { display: true, text: "Loss (MSE)" },
          },
          x: {
            title: { display: true, text: "Epoch" },
          },
        },
      },
    });
  }

  // Render test metric comparison bars
  const models = [
    { name: "MLP", value: comparison.mlp.mse, color: "#58a6ff" },
    { name: "LSTM", value: comparison.lstm.mse, color: "#bc8cff" },
  ];
  const maxValue = Math.max(...models.map((model) => model.value), 1e-12);
  const container = document.getElementById("modelComparison");

  container.innerHTML = models.map((model) => `
    <div class="model-row">
      <div class="model-row-top">
        <strong>${model.name}</strong>
        <span>${model.value.toFixed(6)}</span>
      </div>
      <div class="model-bar-track">
        <span class="model-bar" style="width:${(model.value / maxValue) * 100}%; background:${model.color};"></span>
      </div>
    </div>
  `).join("");
}

function getTikTokParameters() {
  return {
    lookback: Number(document.getElementById("tiktokLookback").value),
    buy_threshold: -Number(document.getElementById("tiktokBuyDrop").value) / 100,
    sell_threshold: Number(document.getElementById("tiktokSellRise").value) / 100,
    buy_amount: Number(document.getElementById("tiktokBuyAmount").value),
    sell_amount: Number(document.getElementById("tiktokSellAmount").value),
    commission: Number(document.getElementById("tiktokCommission").value) / 100,
    initial_cash: Number(document.getElementById("tiktokInitialCash").value),
  };
}

function parameterQuery(parameters) {
  return new URLSearchParams(
    Object.entries(parameters).map(([key, value]) => [key, String(value)])
  ).toString();
}

function money(value) {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function renderStrategyComparison() {
  if (!latestSmaMetrics || !latestTikTokResult) return;
  const tiktok = latestTikTokResult.metrics;
  const assetCount = document.getElementById("symbolSelect").options.length;
  const rows = [
    {
      name: "SMA crossover",
      universe: `${currentScope === "full" ? "Full market" : "Core"} (${assetCount})`,
      final: latestSmaMetrics.final_equity,
      totalReturn: latestSmaMetrics.total_return,
      sharpe: latestSmaMetrics.sharpe,
      drawdown: latestSmaMetrics.max_drawdown,
      fees: latestSmaMetrics.fees_paid,
      activity: `${latestSmaMetrics.activity.toLocaleString()} rebalances`,
    },
    {
      name: "Fixed-dollar",
      universe: `Full market (${latestTikTokResult.symbols.length})`,
      final: tiktok.final_equity,
      totalReturn: tiktok.total_return,
      sharpe: tiktok.sharpe,
      drawdown: tiktok.max_drawdown,
      fees: tiktok.fees_paid,
      activity: `${(tiktok.buy_trades + tiktok.sell_trades).toLocaleString()} orders`,
    },
  ];

  document.getElementById("comparisonBody").innerHTML = rows.map((row) => `
    <tr>
      <td>${row.name}</td>
      <td>${row.universe}</td>
      <td>${money(row.final)}</td>
      <td class="${row.totalReturn >= 0 ? "positive" : "negative-text"}">${(row.totalReturn * 100).toFixed(1)}%</td>
      <td>${row.sharpe.toFixed(3)}</td>
      <td class="negative-text">${(row.drawdown * 100).toFixed(1)}%</td>
      <td>${money(row.fees)}</td>
      <td>${row.activity}</td>
    </tr>
  `).join("");
}

async function loadTikTokSignals(parameters) {
  const response = await fetch(`${API}/tiktok-signals?${parameterQuery(parameters)}`);
  if (!response.ok) throw new Error("Current signal scan failed");
  const result = await response.json();
  const counts = { BUY: 0, SELL: 0, HOLD: 0 };
  for (const row of result.signals) counts[row.signal] += 1;

  document.getElementById("signalDate").textContent =
    `Signals calculated after the ${result.as_of} close for the next session.`;
  document.getElementById("signalSummary").innerHTML =
    `<span class="signal buy">BUY ${counts.BUY}</span>` +
    `<span class="signal sell">SELL ${counts.SELL}</span>` +
    `<span class="signal hold">HOLD ${counts.HOLD}</span>`;
  document.getElementById("signalBody").innerHTML = result.signals
    .sort((a, b) => {
      const priority = { BUY: 0, SELL: 1, HOLD: 2 };
      return priority[a.signal] - priority[b.signal] || a.symbol.localeCompare(b.symbol);
    })
    .map((row) => `
      <tr>
        <td>${row.symbol}</td>
        <td><span class="signal ${row.signal.toLowerCase()}">${row.signal}</span></td>
        <td class="${row.weekly_return >= 0 ? "positive" : "negative-text"}">${(row.weekly_return * 100).toFixed(2)}%</td>
        <td>${row.close.toFixed(3)}</td>
        <td>${money(row.holding_value)}</td>
      </tr>
    `).join("");
}

async function loadTikTokStrategy(requestedParameters = getTikTokParameters()) {
  const response = await fetch(`${API}/tiktok-backtest?${parameterQuery(requestedParameters)}`);
  if (!response.ok) throw new Error("TikTok strategy backtest failed");
  const result = await response.json();
  latestTikTokResult = result;
  const { parameters, metrics } = result;
  const trades = metrics.buy_trades + metrics.sell_trades;

  document.getElementById("tiktokSubtitle").textContent =
    `${result.symbols.length} assets · Buy $${parameters.buy_amount.toFixed(0)} at ≤ ${(parameters.buy_threshold * 100).toFixed(0)}% · ` +
    `Sell $${parameters.sell_amount.toFixed(0)} at ≥ +${(parameters.sell_threshold * 100).toFixed(0)}% · ` +
    `${(parameters.commission * 100).toFixed(1)}% commission`;
  document.getElementById("tiktokFinalEquity").textContent = money(metrics.final_equity);
  document.getElementById("tiktokTotalReturn").textContent = `${(metrics.total_return * 100).toFixed(1)}%`;
  document.getElementById("tiktokSharpe").textContent = metrics.sharpe.toFixed(3);
  document.getElementById("tiktokMaxDrawdown").textContent = `${(metrics.max_drawdown * 100).toFixed(1)}%`;
  document.getElementById("tiktokFees").textContent = money(metrics.fees_paid);
  document.getElementById("tiktokTrades").textContent = trades.toLocaleString();

  if (tiktokChart) tiktokChart.destroy();
  tiktokChart = new Chart(document.getElementById("tiktokChart"), {
    type: "line",
    data: {
      labels: result.dates,
      datasets: [
        {
          label: "Fixed-dollar strategy",
          data: result.portfolio,
          borderColor: "#bc8cff",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: "Equal-weight full market",
          data: result.benchmark,
          borderColor: "#d29922",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          label: "Cash",
          data: result.cash,
          borderColor: "#91a4ba",
          borderWidth: 1,
          borderDash: [5, 5],
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
        title: { display: true, text: "$1,000 Growth Across the Full Market" },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { title: { display: true, text: "Account value ($)" } },
      },
    },
  });
  renderStrategyComparison();
  await loadTikTokSignals(parameters);
}

function initializeTikTokControls() {
  const form = document.getElementById("tiktokControls");
  const button = document.getElementById("runTikTok");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    button.disabled = true;
    button.textContent = "Running…";
    try {
      await loadTikTokStrategy();
    } catch (error) {
      document.getElementById("tiktokSubtitle").textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = "Run backtest";
    }
  });
}

checkHealth();
initializeUniverseControls();
loadFeatures();
loadModelComparison().catch((error) => {
  document.getElementById("modelComparison").innerHTML = `<div class="model-row"><span>${error.message}</span></div>`;
});
initializeTikTokControls();
loadTikTokStrategy().catch((error) => {
  document.getElementById("tiktokSubtitle").textContent = error.message;
});
// TASK_07+ : render additional dashboard panels.
