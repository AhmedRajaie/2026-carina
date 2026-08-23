# Task 04 — Equity curve vs benchmark (Day 4)

**Goal:** the money chart — your strategy's growth vs the real benchmark, in EGP,
on a real time axis.

**Prompt (backend):**
> Add `/backtest` that runs the SMA crossover strategy and returns
> `{ "dates":[...], "portfolio":[...], "benchmark":[...] }`, scaled to start from
> 1000 EGP rather than 1.0. Use:
>   from tradinglab.data_feed import DataFeed
>   from tradinglab.simulator import PortfolioSimulator
>   from tradinglab.backtester import run_backtest
>   from tradinglab.strategies.sma import sma_crossover_weights
> Build the feed with `DataFeed.from_dir("data/egx", symbols=["COMI","HRHO","TMGH","SWDY","FWRY"])`,
> the simulator with `PortfolioSimulator(feed, benchmark="egx30")` (the real EGX30
> index, not equal-weight), call run_backtest with lookback=30, and return
> `result['dates']` (as "YYYY-MM-DD" strings), and `result['portfolio']` /
> `result['benchmark']` each multiplied by 1000.

**Prompt (frontend):**
> Add a new `.panel` with `<canvas id="equityChart">`. Fetch `/backtest` and draw
> two lines (strategy vs benchmark) using the real `dates` as the x-axis labels,
> values in EGP. Title it clearly, and label the y-axis "EGP".

**Verify:** two equity curves, real dates on the x-axis, values starting near 1000
EGP. Compare what you see to your own NB4 result — they should match, since it's
the same strategy, same universe, same real benchmark.