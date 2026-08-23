# Task 02 — Price chart (Day 2)

**Goal:** show one stock's closing price as a line chart.

**Context:** the backend can import the library:
`from tradinglab.data_feed import DataFeed`. Every later task builds on the same
`feed` — set the universe here once, correctly, so it stays consistent everywhere.

**Prompt (paste into Copilot Chat):**
> In dashboard/backend/main.py, using `from tradinglab.data_feed import DataFeed`
> and `feed = DataFeed.from_dir("data/egx", symbols=["COMI","HRHO","TMGH","SWDY","FWRY"])`,
> add two GET endpoints:
> 1. `/universe` returning the list `feed.symbols`.
> 2. `/prices/{symbol}` returning `{ "dates": [...], "close": [...] }` for that
>    symbol (dates as "YYYY-MM-DD" strings). Return 404 if the symbol is unknown.
> Keep it simple and synchronous.

**Then, frontend:**
> In index.html add a `<canvas id="priceChart">` inside a `.panel`. In app.js,
> fetch `/universe`, pick the first symbol, fetch `/prices/{symbol}`, and draw a
> Chart.js line chart of close vs dates.

**Verify:** a price line appears, and `/universe` returns exactly 5 symbols
(COMI, HRHO, TMGH, SWDY, FWRY) — the same universe every later task uses. Try
changing the symbol in the URL.