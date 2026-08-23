# Task 09 — Leaderboard + risk (Week 2, Day 5)

**Goal:** every strategy on one chart, plus a risk readout. This is the week-2
finale panel.

**Context:** day-5 notebook saved `dashboard/data/leaderboard.json` (sma, mpt,
benchmark curves).

**Prompt (backend):**
> Add `/leaderboard` returning `dashboard/data/leaderboard.json`.

**Prompt (frontend):**
> Add a panel plotting sma, mpt, and benchmark as three lines. Below it, show a
> small table of volatility and max drawdown per strategy (you can compute these
> in a new `/risk` endpoint using tradinglab.metrics, or hardcode from the notebook
> output for now). Title: "Leaderboard vs EGX benchmark".

**Verify:** SMA, MPT, and benchmark on one chart, with risk numbers. This is the
launchpad into the RL week.
