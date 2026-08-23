"""
backtester.py — WEEK 1 face of the simulator.

A strategy is any function: observation -> weights. The backtester just loops
over history, asks the strategy for weights each day, and hands them to the
simulator. No gym, no RL vocabulary. A beginner reads this top to bottom.

In week 3 the very same simulator is wrapped by PortfolioEnv instead. Same core,
different caller. Open both files side by side on pivot day.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .observation import build_observation
from .simulator import PortfolioSimulator

# A strategy takes one day's observation and returns weights over the universe.
Strategy = Callable[[np.ndarray], np.ndarray]


def run_backtest(
    sim: PortfolioSimulator,
    strategy: Strategy,
    lookback: int,
    start: int | None = None,
    end: int | None = None,
):
    """Loop a strategy over history and return value curves vs the benchmark."""
    feed = sim.feed
    start = lookback if start is None else max(start, lookback)
    end = feed.n_days - 1 if end is None else min(end, feed.n_days - 1)

    weights_by_day = np.zeros((feed.n_days, feed.n_assets))
    for t in range(start, end):
        obs = build_observation(feed, t, lookback)
        weights_by_day[t] = strategy(obs)

    result = sim.run(weights_by_day, start, end)
    result["weights"] = weights_by_day[start:end]   # (T, n_assets) — what was actually held each day
    return result