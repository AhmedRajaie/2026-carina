# Glossary — every term, one line

A quick reference. Full explanations live in `learn/`. Keep this open while you work.

## Markets
- **OHLCV** — Open, High, Low, Close, Volume: one day's price record.
- **Return** — percent change in price from one day to the next.
- **Benchmark** — what you compare against. Here: the EGX index (or an equal-weight basket). Beating it is the goal.
- **Universe** — the set of stocks you're allowed to trade.

## Indicators (week 1)
- **SMA** — Simple Moving Average: mean of the last N prices. Smooths noise, shows trend.
- **EMA** — Exponential Moving Average: like SMA but recent days count more; reacts faster.
- **RSI** — Relative Strength Index (0–100): how hard price has been pushed up vs down. >70 overbought, <30 oversold.
- **Crossover** — when a fast average crosses a slow one; a classic trend signal (e.g. 9/20).

## Performance & risk (week 1–2)
- **Equity curve** — the growth of 1.0 over time as you follow a strategy.
- **Total return** — compounded gain over the whole period.
- **Volatility** — standard deviation of returns; how bumpy the ride is (risk).
- **Max drawdown** — worst peak-to-trough drop; the deepest hole you sat in.
- **Sharpe ratio** — return per unit of risk; higher is better.
- **Backtest** — running a strategy over historical data to measure it.
- **Lookahead bias** — accidentally using future information; makes a backtest lie.

## Machine learning (week 2)
- **Feature** — an input number the model learns from (an indicator value, a return).
- **Label** — the thing you're trying to predict (here: next-day return).
- **Train / test split** — fit on the early period, judge on the later one it never saw.
- **Overfitting** — memorizing the past (including noise); great on train, bad on test.
- **Underfitting** — too simple to catch the real pattern; bad on both.
- **MLP** — a plain fully-connected neural network.
- **LSTM** — a network that reads a sequence of days.
- **Loss** — how wrong the model is; training pushes it down.

## Portfolio (week 2)
- **Weights** — how your money is split across stocks; they sum to 1.
- **Diversification** — spreading across assets to cut risk.
- **MPT** — Modern Portfolio Theory: choose weights to balance return vs risk.
- **Inverse-volatility** — a simple allocation: more money in calmer stocks.

## Reinforcement learning (week 3)
- **MDP** — the loop: state → action → reward → next state.
- **State** — what the market looks like now (the observation window).
- **Action** — what you do (the weight vector).
- **Reward** — the signal you learn from (here: return, or return vs benchmark).
- **Agent** — whatever picks the action from the state.
- **Policy** — the agent's rule for choosing actions.
- **Q-value** — how good an action is in a state, learned from experience.
- **Explore vs exploit** — try something new vs use what already works.
- **PPO** — the deep-RL algorithm you train in week 3.
- **Episode** — one full run through the data during training.
