# Week 1 — become a programmer who ships

By Friday you can load market data, build indicators, write a strategy, run a real
backtest, report it honestly against the benchmark, and show it on a dashboard —
all on code you wrote. All tests live in `week1/tests/`.  Run:  `uv run pytest week1/tests/`

## The arc
1. **01-setup-and-data** — meet the environment (the `DataFeed`), build your first
   tool: `plot_price`.
2. **02-indicators** — turn prices into signals: `sma`, `rsi`.
3. **03-strategy-and-engine** — a real strategy (`sma_crossover_weights`) and the
   heart of the engine (`portfolio_return`) that every backtest and the week-3 agent
   runs through.
4. **04-backtest-and-report** — run it over history and read an honest verdict:
   `total_return`, `max_drawdown`, and the `report()` scorecard.
5. **05-dashboard** — turn it into a product (vibe-code with `dashboard/tasks/`).

## The graduation habit
Build a function in the notebook, a check passes, then move it into `src/tradinglab/`.
Once it's in the package, the whole system runs on your code — including next week's.

## Every notebook ends on a result
Charts, a one-step engine demo, a full backtest scored with `report()`. Build →
run → report → judge honestly. The same loop all three weeks.

## Concepts
`learn/01-stock-market/`, `learn/02-algo-trading/` (0–4),
`learn/03-quant-and-ai/indicators`, `.../risk-and-volatility`.
