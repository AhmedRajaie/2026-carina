# Task 03 — Indicator overlay (Day 3)

**Goal:** overlay a moving average on the price chart. Uses YOUR graduated `sma`.

**Prompt (backend):**
> Add `/indicators/{symbol}?window=20` returning `{ "dates":[...], "sma":[...] }`,
> computing the SMA with `from tradinglab.indicators import sma` on the symbol's
> close prices. Replace NaNs with null so JSON is valid.

**Prompt (frontend):**
> Add a second Chart.js dataset to the price chart that plots the SMA line from
> `/indicators/{symbol}?window=20`, in a different color.

**Verify:** price with a smoother SMA line on top. This is your day-2 SMA doing
real work in your product.
