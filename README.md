# EFG Data Science — Algorithmic Trading Internship

Three weeks. You will build a real algorithmic trading system end to end, on the
same conventions the Data Science team uses. By the last day your group presents
its own equity curve against EGX30.

## The arc
- **Week 1** — become a programmer who ships: version control, a full-stack
  dashboard, market data, indicators, backtesting.
- **Week 2** — try to predict prices with neural nets. Discover it isn't enough.
- **Week 3** — reframe: an agent that manages a portfolio to beat the index.

Everything you build in week 1 becomes part of the week 3 system. Same data,
same benchmark, same engine — you just change who chooses the weights.

## Layout
- `learn/` — the concept for the first part of each day (slides / HTML)
- `week1..3/dayN/` — the day's notebook, README, and tests
- `src/tradinglab/` — the shared library (provided; you read and use it)
- `scripts/` — one-off tools (data fetch)
- `notebooks/` — exploration and Colab RL training
- `dashboard/` — your product: FastAPI backend + JS frontend
- `data/` — committed EGX price CSVs and the EGX30 benchmark

## Key docs
- `SETUP.md` — install everything (Windows + macOS), from zero
- `WORKFLOW.md` — how we work: git, branches, groups, roles
- `CONCEPTS.md` — one-line glossary of every term
- `learn/` — the concept for each day (HTML)

## Start here
Read `SETUP.md` and get your machine ready **before** day 1.
