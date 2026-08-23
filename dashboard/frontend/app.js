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
checkHealth();
// TASK_02+ : fetch /prices and render a chart, etc.
