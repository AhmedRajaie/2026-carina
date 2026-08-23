"""
evaluation.py — honest testing helpers. Home of WALK-FORWARD.

A single train/test split checks one future. Walk-forward checks several: train on
a window, test on the next unseen window, roll both forward, repeat. It's the
honest way to ask "does this hold up across different market regimes, not just one
lucky stretch?"
"""
from __future__ import annotations
import numpy as np
from .data_feed import DataFeed
from .simulator import PortfolioSimulator
from .backtester import run_backtest


def walk_forward(feed: DataFeed, strategy, lookback=30, n_folds=4):
    """Evaluate a strategy across rolling out-of-sample windows.

    Splits history into n_folds consecutive test windows. For each, we report the
    strategy's return and the benchmark's return over that *unseen* window. A
    strategy that only wins in one fold is not a strategy — it's a coincidence.
    """
    sim = PortfolioSimulator(feed)
    days = feed.n_days
    edges = np.linspace(lookback, days - 1, n_folds + 1).astype(int)

    results = []
    for i in range(n_folds):
        start, end = edges[i], edges[i + 1]
        res = run_backtest(sim, strategy, lookback=lookback, start=start, end=end)
        results.append({
            "fold": i + 1,
            "days": f"{start}-{end}",
            "strategy": float(res["portfolio"][-1]),
            "benchmark": float(res["benchmark"][-1]),
            "beat": bool(res["portfolio"][-1] > res["benchmark"][-1]),
        })
    return results
