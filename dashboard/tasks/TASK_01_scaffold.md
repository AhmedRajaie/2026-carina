# Task 01 — Scaffold (Day 2)

**Goal:** get the empty dashboard running and talking to the backend.

**Context:** `dashboard/backend/main.py` has a `/health` endpoint.
`dashboard/frontend/` has `index.html` + `app.js` that call it.

**Steps**
1. Start the backend:
   `uv run uvicorn dashboard.backend.main:app --reload --port 8000`
2. Open `dashboard/frontend/index.html` in your browser.
3. The status panel should say `backend: ok`.

**Verify:** you see `backend: ok`. If it says "not reachable", the backend isn't
running or the port is wrong.

**Copilot prompt (if stuck):**
> The frontend status panel says "backend not reachable". The backend runs on
> http://localhost:8000 and has a /health route returning {"status":"ok"}. Check
> app.js fetch URL and CORS, and tell me what to fix.
