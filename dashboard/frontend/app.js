// Dashboard frontend. Grows via dashboard/tasks/.
const API = "http://localhost:8000";
let priceChartInstance = null;

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

async function drawPriceChart(symbol) {
  const [pricesRes, indicatorsRes] = await Promise.all([
    fetch(`${API}/prices/${symbol}`),
    fetch(`${API}/indicators/${symbol}?window=20`),
  ]);
  const { dates, close } = await pricesRes.json();
  const { sma } = await indicatorsRes.json();

  if (priceChartInstance) priceChartInstance.destroy();
  priceChartInstance = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: symbol, data: close, borderColor: "#4dabf7", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: `${symbol} SMA(20)`, data: sma, borderColor: "#ffa94d", borderWidth: 1.5, pointRadius: 0, tension: 0.1, spanGaps: true },
      ],
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: `${symbol} Price & SMA(20)`, color: "#e6edf3" } },
      scales: { x: { ticks: { maxTicksLimit: 8 } } },
    },
  });
}

async function setupSymbolDropdown() {
  const res = await fetch(`${API}/universe`);
  const symbols = await res.json();
  const select = document.getElementById("symbolSelect");
  select.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join("");
  select.addEventListener("change", () => drawPriceChart(select.value));
  if (symbols.length) drawPriceChart(symbols[0]);
}
setupSymbolDropdown();

async function drawEquityChart() {
  const res = await fetch(`${API}/backtest`);
  const { dates, portfolio, benchmark } = await res.json();

  new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        { label: "Strategy", data: portfolio, borderColor: "#63e6be", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "EGX30 Benchmark", data: benchmark, borderColor: "#e6e6e6", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
      ],
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: "SMA Crossover Strategy vs EGX30 Benchmark", color: "#e6edf3" } },
      scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: "EGP", color: "#e6edf3" } } },
    },
  });
}
drawEquityChart();

async function loadMetrics() {
  const res = await fetch(`${API}/metrics`);
  const { total_return, sharpe, max_drawdown } = await res.json();
  document.getElementById("metricsText").innerHTML = `
    <div><span class="metric-label">Total Return</span><span class="metric-value">${(total_return * 100).toFixed(1)}%</span></div>
    <div><span class="metric-label">Sharpe Ratio</span><span class="metric-value">${sharpe}</span></div>
    <div><span class="metric-label">Max Drawdown</span><span class="metric-value">${(max_drawdown * 100).toFixed(1)}%</span></div>
  `;
}
loadMetrics();