# Week 2 — from predicting prices to allocating capital

Five notebooks, named by idea (not day). A notebook can span more than one day —
the instructor paces it. All tests live in one place: `week2/tests/`.

Run the whole week's suite:  `uv run pytest week2/tests/`

## The arc
1. **01-features-and-model** — build the feature table (your week-1 indicators),
   train your first neural net, and *fire it through the backtester the same day*.
2. **02-backtesting** — judge a model honestly: directional accuracy, an LSTM, and
   why the best in-sample model isn't the best out-of-sample.
3. **03-pivot** — the turning point: a model with real (small) predictive signal
   still doesn't beat the market. Predicting price is the wrong objective.
4. **04-mpt-foundations** — Modern Portfolio Theory: the equations
   (E[r]=wᵀμ, σ²=wᵀΣw, Sharpe), max-Sharpe, and the look-ahead trap.
5. **05-mpt-walkforward** — the honest backtest: estimate μ and Σ from only the
   trailing window (our backtester is walk-forward by construction), plus
   whole-share rounding and frictions.

## Rough day mapping (flexible)
- Day 1 → NB1 · Day 2 → NB2 · Day 3 → NB3 · Day 4 → NB4 · Day 5 → NB5
  (MPT can breathe across days 4–5; fast groups start NB5 early.)

## Every notebook ends the same way
Build → backtest on the real env → `report()` (your week-1 chart + metrics) →
honest verdict. You fire what you build the day you build it.

## Concepts
`learn/03-quant-and-ai/neural-nets-no-math`, `.../portfolio-theory`,
`.../risk-and-volatility`, `.../walk-forward`.
