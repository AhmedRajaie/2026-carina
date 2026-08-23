"""
simulator.py — the accounting core. THE SPINE OF THE WHOLE PROGRAM.

Everything shares this one object:
    - Week 1  Backtester  loops a strategy function and calls .step_return()
    - Week 3  PortfolioEnv (gym) calls the SAME .step_return()

If the weights come from an SMA rule or from a neural network makes no
difference here. That is the entire point, and it is why the "prediction failed,
now use an agent" pivot is a real code fact and not a slogan: only the source of
the weights changes, the simulator underneath is identical.

Conventions (say these out loud in week 1):
    - At day t the strategy sees data UP TO AND INCLUDING close[t], then chooses
      weights. It earns the return from close[t] to close[t+1]. You can never
      earn a return you already saw — that one-bar delay is the lookahead guard.
    - Weights are non-negative and sum to 1 (long-only, fully invested).
    - The benchmark is an equal-weight buy-and-hold basket of the whole universe.
      We have no true EGX 30 series, and "beat the equal-weight market" is a real
      benchmark. Swap in a real index later by replacing benchmark_returns.
"""

from __future__ import annotations

import numpy as np

from .data_feed import DataFeed, load_egx30_returns
from .portfolio import portfolio_return


class PortfolioSimulator:
    """Turns a sequence of weight vectors into a portfolio value path.

    This holds NO strategy logic. It is pure bookkeeping: given the weights you
    hold today, what return do you earn tomorrow, and what is the portfolio worth.
    """

    DEFAULT_EGX30_PATH = "data/egx30.csv"

    def __init__(
        self,
        feed: DataFeed,
        benchmark: str = "equal_weight",
        benchmark_returns: np.ndarray | None = None,
        egx30_path: str | None = None,
        commission: float = 0.0,
    ):
        """
        benchmark: which built-in benchmark to use — "equal_weight" (default,
            same behavior as before) or "egx30" (the real index, loaded from
            `egx30_path` or DEFAULT_EGX30_PATH).
        benchmark_returns: pass your OWN array to override either built-in
            option entirely (e.g. a benchmark for a different universe).
        commission: cost per unit of TURNOVER (e.g. 0.001 = 10 bps (basis points) ). Charged
            whenever weights change from one day to the next — rebalancing
            costs money in real life; holding steady is free. Default 0.0
            (frictionless, same behavior as before this option existed).
        """
        self.feed = feed
        self.commission = commission

        if benchmark_returns is not None:
            # Explicit override wins over everything.
            self.benchmark_returns = benchmark_returns
        elif benchmark == "egx30":
            path = egx30_path or self.DEFAULT_EGX30_PATH
            real = load_egx30_returns(path, feed.dates)
            if real is None:
                raise ValueError(
                    f"benchmark='egx30' requested but '{path}' wasn't found or "
                    "doesn't cover enough of your date range. Check the file, "
                    "or pass benchmark='equal_weight' instead."
                )
            self.benchmark_returns = real
        elif benchmark == "equal_weight":
            # Equal-weight buy-and-hold ≈ mean of per-asset returns.
            self.benchmark_returns = feed.returns.mean(axis=1)
        else:
            raise ValueError(f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.")

    def step_return(self, weights: np.ndarray, day_index: int) -> float:
        """Portfolio return earned by holding `weights` from day_index to +1.

        Args:
            weights: (n_assets,), non-negative, sums to 1.
            day_index: the day the weights are CHOSEN (t). Return earned is the
                       return from t to t+1, i.e. feed.returns[t+1].

        Returns:
            The portfolio's simple return for that one day.
        """
        next_returns = self.feed.returns[day_index + 1]
        return portfolio_return(weights, next_returns)

    def benchmark_step_return(self, day_index: int) -> float:
        """Equal-weight benchmark return from day_index to +1."""
        return float(self.benchmark_returns[day_index + 1])

    def run(self, weights_by_day: np.ndarray, start: int, end: int):
        """Walk a full path of weights and return value curves.

        Args:
            weights_by_day: (T, n_assets) weights, row t used on day t.
            start, end: half-open day range [start, end) over which we trade.

        Returns:
            dict with 'portfolio', 'benchmark' (both length end-start, starting
            at 1.0), the per-day return arrays, and 'dates' — the REAL calendar
            date each value in the curve corresponds to. Weights chosen on day t
            earn the return realized on day t+1 (the lookahead-bias guard), so
            dates are offset by one: result['dates'][i] is the day the value at
            result['portfolio'][i] was actually reached.
        """
        port_rets, bench_rets = [], []
        for t in range(start, end):
            port_rets.append(self.step_return(weights_by_day[t], t))
            bench_rets.append(self.benchmark_step_return(t))

        port_rets = np.array(port_rets)
        bench_rets = np.array(bench_rets)

        if self.commission > 0:
            # Turnover on day t = how much the portfolio changed vs the day
            # before (0 = held everything unchanged; up to 2.0 = sold
            # everything and bought a completely different set). Rows before
            # `start` are always zero (untouched by the strategy loop), so day
            # `start` naturally pays to establish the very first position too.
            held = weights_by_day[start:end]
            prev_held = weights_by_day[start - 1:end - 1]
            turnover = np.abs(held - prev_held).sum(axis=1) / 2
            port_rets = port_rets - self.commission * turnover

        return {
            "portfolio": np.cumprod(1.0 + port_rets),
            "benchmark": np.cumprod(1.0 + bench_rets),
            "portfolio_returns": port_rets,
            "benchmark_returns": bench_rets,
            "dates": self.feed.dates[start + 1 : end + 1],
        }