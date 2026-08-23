# extras · week 1 — going further

Optional. Each builds on what you already made, in the same house style: write it,
test it, graduate it.

## 1. Add an indicator (MACD or Bollinger Bands)
Add a new function to `src/tradinglab/indicators.py` and a test beside the others.
- **MACD**: EMA(12) − EMA(26), plus a signal line (EMA of that). A momentum classic.
- **Bollinger Bands**: SMA ± 2 × rolling std. Price near the upper band = stretched.
Then plot it in a notebook using `charting`. Bonus: use it in a strategy.

## 2. A second strategy archetype: mean-reversion
SMA crossover is *trend-following* (buy what's rising). Write the opposite in
`strategies/` — a **mean-reversion** rule that leans toward stocks that dropped
below their average, betting they bounce back. Backtest both. When does each win?
That contrast is a real quant insight.

## 3. Allow short-selling
The simulator already handles any weights. Relax the long-only rule: let a
strategy assign *negative* weights (bet a stock falls), keeping the absolute
weights summing to 1. First taste of how real funds express a negative view.
