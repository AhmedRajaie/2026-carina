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

async function renderPriceChart() {
  const universeResponse = await fetch(`${API}/universe`);
  const symbols = await universeResponse.json();
  const symbol = symbols[0];

  const pricesResponse = await fetch(`${API}/prices/${symbol}`);
  const prices = await pricesResponse.json();

  new Chart(document.getElementById("priceChart"), {
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
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: false } },
    },
  });
}

checkHealth();
renderPriceChart().catch(() => {
  document.getElementById("status").textContent = "price data not reachable";
});
