const API = "http://localhost:8000";
const state = { priceChart: null, equityChart: null, symbolRequest: 0 };

function deriveSmaPulse(priceData, indicatorData) {
  const lastIndex = Math.min(priceData.close.length, indicatorData.sma.length) - 1;
  for (let index = lastIndex; index >= 0; index -= 1) {
    const close = priceData.close[index];
    const sma = indicatorData.sma[index];
    if (Number.isFinite(close) && Number.isFinite(sma) && sma !== 0) {
      const distancePct = ((close - sma) / sma) * 100;
      return { date: priceData.dates[index], close, sma, distancePct, position: distancePct >= 0 ? "above" : "below" };
    }
  }
  return null;
}

function formatMetric(name, value) {
  if (name === "sharpe") return value.toFixed(2);
  if (name === "max_drawdown") return `−${(Math.abs(value) * 100).toFixed(1)}%`;
  const percent = value * 100;
  return `${percent >= 0 ? "+" : "−"}${Math.abs(percent).toFixed(1)}%`;
}

async function fetchJson(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function setStatus(message, kind) {
  const element = document.getElementById("status");
  element.textContent = message;
  element.className = `status-pill status-${kind}`;
}

function chartOptions(yTitle, tooltipSuffix = "") {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#f3f7fb", usePointStyle: true, padding: 18 } },
      tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${Number(context.parsed.y).toLocaleString(undefined, { maximumFractionDigits: 2 })}${tooltipSuffix}` } },
    },
    scales: {
      x: { ticks: { color: "#94a7bd", maxTicksLimit: 8 }, grid: { color: "rgba(148,167,189,0.1)" } },
      y: { title: { display: true, text: yTitle, color: "#94a7bd" }, ticks: { color: "#94a7bd" }, grid: { color: "rgba(148,167,189,0.1)" } },
    },
  };
}

function renderPriceChart(priceData, indicatorData, symbol) {
  if (state.priceChart) state.priceChart.destroy();
  state.priceChart = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: { labels: priceData.dates, datasets: [
      { label: `${symbol} close`, data: priceData.close, borderColor: "#45d6c4", backgroundColor: "rgba(69,214,196,0.1)", borderWidth: 2, pointRadius: 0, tension: 0.12 },
      { label: "20-day SMA", data: indicatorData.sma, borderColor: "#f4b860", borderWidth: 2, pointRadius: 0, tension: 0.12, spanGaps: false },
    ] },
    options: chartOptions("EGP per share"),
  });
}

function renderSmaPulse(pulse) {
  const card = document.getElementById("smaPulse");
  card.removeAttribute("data-position");
  if (!pulse) {
    document.getElementById("pulsePosition").textContent = "Not enough history";
    document.getElementById("pulseClose").textContent = "—";
    document.getElementById("pulseSma").textContent = "—";
    document.getElementById("pulseDistance").textContent = "—";
    document.getElementById("pulseDate").textContent = "Waiting for a valid SMA value.";
    return;
  }
  document.getElementById("pulsePosition").textContent = `Close is ${pulse.position} its SMA`;
  document.getElementById("pulseClose").textContent = `${pulse.close.toFixed(2)} EGP`;
  document.getElementById("pulseSma").textContent = `${pulse.sma.toFixed(2)} EGP`;
  document.getElementById("pulseDistance").textContent = `${pulse.distancePct >= 0 ? "+" : ""}${pulse.distancePct.toFixed(2)}%`;
  document.getElementById("pulseDate").textContent = `As of ${pulse.date} · Informational, not a trading recommendation.`;
  card.dataset.position = pulse.position;
}

async function loadSymbol(symbol) {
  const requestId = ++state.symbolRequest;
  const select = document.getElementById("symbolSelect");
  const panel = document.getElementById("pricePanel");
  const title = document.getElementById("priceTitle");
  select.disabled = true;
  panel.setAttribute("aria-busy", "true");
  title.textContent = `Loading ${symbol}…`;
  try {
    const [priceData, indicatorData] = await Promise.all([
      fetchJson(`/prices/${encodeURIComponent(symbol)}`),
      fetchJson(`/indicators/${encodeURIComponent(symbol)}?window=20`),
    ]);
    if (requestId !== state.symbolRequest) return;
    renderPriceChart(priceData, indicatorData, symbol);
    renderSmaPulse(deriveSmaPulse(priceData, indicatorData));
    title.textContent = `${symbol} price + 20-day SMA`;
    document.getElementById("dataRange").textContent = `${priceData.dates[0]} — ${priceData.dates[priceData.dates.length - 1]}`;
    document.getElementById("priceError").hidden = true;
    setStatus("backend: ok", "success");
  } catch (error) {
    if (requestId !== state.symbolRequest) return;
    const errorBox = document.getElementById("priceError");
    errorBox.textContent = `Could not load ${symbol}: ${error.message}`;
    errorBox.hidden = false;
    title.textContent = `${symbol} price + 20-day SMA`;
    setStatus("Data unavailable", "error");
  } finally {
    if (requestId === state.symbolRequest) {
      panel.setAttribute("aria-busy", "false");
      select.disabled = false;
    }
  }
}

function renderEquityChart(data) {
  if (state.equityChart) state.equityChart.destroy();
  state.equityChart = new Chart(document.getElementById("equityChart"), {
    type: "line",
    data: { labels: data.dates, datasets: [
      { label: "SMA strategy", data: data.portfolio, borderColor: "#45d6c4", borderWidth: 2, pointRadius: 0, tension: 0.1 },
      { label: "EGX30 benchmark", data: data.benchmark, borderColor: "#f4b860", borderWidth: 2, pointRadius: 0, tension: 0.1 },
    ] },
    options: chartOptions("Portfolio value (EGP)", " EGP"),
  });
}

async function loadPerformance() {
  try {
    const [backtest, metrics] = await Promise.all([fetchJson("/backtest"), fetchJson("/metrics")]);
    renderEquityChart(backtest);
    document.getElementById("totalReturn").textContent = formatMetric("total_return", metrics.total_return);
    document.getElementById("sharpe").textContent = formatMetric("sharpe", metrics.sharpe);
    document.getElementById("maxDrawdown").textContent = formatMetric("max_drawdown", metrics.max_drawdown);
    document.getElementById("performanceError").hidden = true;
  } catch (error) {
    const errorBox = document.getElementById("performanceError");
    errorBox.textContent = `Could not load performance: ${error.message}`;
    errorBox.hidden = false;
  }
}

async function initializeDashboard() {
  try {
    const health = await fetchJson("/health");
    if (health.status !== "ok") throw new Error("health check failed");
    const symbols = await fetchJson("/universe");
    const select = document.getElementById("symbolSelect");
    select.replaceChildren(...symbols.map((symbol) => new Option(symbol, symbol)));
    select.addEventListener("change", () => loadSymbol(select.value));
    setStatus("backend: ok", "success");
    await Promise.all([loadSymbol(symbols[0]), loadPerformance()]);
  } catch (error) {
    setStatus("backend: not reachable", "error");
    document.getElementById("priceError").textContent = "Start uvicorn on port 8000, then refresh this page.";
    document.getElementById("priceError").hidden = false;
    document.getElementById("performanceError").textContent = "Start uvicorn on port 8000, then refresh this page.";
    document.getElementById("performanceError").hidden = false;
  }
}

if (typeof module !== "undefined" && module.exports) module.exports = { deriveSmaPulse, formatMetric };
if (typeof document !== "undefined") initializeDashboard();
