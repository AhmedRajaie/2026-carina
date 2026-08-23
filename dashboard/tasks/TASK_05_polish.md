# Task 05 — Polish v1 (Day 5)

**Goal:** make it presentable for the four-minute demo.

**Ideas (pick what improves it):**
- A dropdown to switch symbols (fetch `/universe` to fill it).
- Show the key metrics as text (total return, Sharpe, max drawdown) next to the
  equity curve. Add a `/metrics` endpoint using `tradinglab.metrics`.
- Tidy the layout: titles, spacing, consistent colors.

**Prompt (metrics endpoint):**
> Add `/metrics` returning total_return, sharpe, and max_drawdown of the backtest
> portfolio returns, using functions from `tradinglab.metrics`. Round to 3 dp.

**Verify:** one clean page — price + indicator, equity curve vs benchmark, and the
three numbers. Demo it.
