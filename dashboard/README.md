# dashboard/ — your Week 1 product

The Week 1 dashboard is a transparent product demo: one fixed five-stock EGX
universe, a closing-price chart with your 20-day SMA, and a 9/20 SMA crossover
backtest against the real EGX30 benchmark. The Latest SMA Pulse summarizes the
most recent close relative to its average; it is informational, not a trading
recommendation.

## How to use a task file
1. Open the task file for today (e.g. `tasks/TASK_02_price_chart.md`).
2. Read the **Goal** and **Context**.
3. Paste the **Prompt** into Copilot Chat, or work through the numbered steps.
4. Run the **Verify** step. If it works, commit. If not, iterate with Copilot.

## Order
- Day 2: `TASK_01_scaffold` then `TASK_02_price_chart`
- Day 3: `TASK_03_indicators`
- Day 4: `TASK_04_equity_curve`
- Day 5: `TASK_05_polish`
Later weeks add model diagnostics, agent allocations, and risk panels.

## Run the Week 1 dashboard

From the repository root:

1. `uv sync`
2. `uv run uvicorn dashboard.backend.main:app --reload --port 8000`
3. Open `dashboard/frontend/index.html`.

The dashboard uses the canonical universe `COMI`, `HRHO`, `TMGH`, `SWDY`, `FWRY`,
historical data through 2026-07-30, and a 1,000 EGP display base. Results are
historical backtest values, not live performance or financial advice.

## Test

```bash
uv run pytest dashboard/tests/test_api.py -v
node --test dashboard/frontend/app.test.js
uv run pytest -q
```

## Four-minute demo order

Connection/universe → symbol and SMA overlay → Latest SMA Pulse → strategy vs
EGX30 equity curve → total return, Sharpe, and max drawdown.

## Run it (legacy shortcut)
```
uv run uvicorn dashboard.backend.main:app --reload --port 8000
```
Then open `dashboard/frontend/index.html` in your browser.
