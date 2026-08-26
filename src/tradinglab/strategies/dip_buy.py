"""
dip_buy.py — Mean-reversion dip-buy strategy.

Rules:
  BUY  — if a stock drops >= DIP_THRESHOLD (5%) today, enter a position.
  HOLD — keep holding until the position gains >= TAKE_PROFIT (10%) from entry.
  SELL — once the gain reaches 10%, exit fully (weight drops to 0).
  SIZE — available cash is split equally across all new buy signals that day.
         "Available cash" = 1 - sum(current_weights), i.e. whatever isn't
         already invested.

This is a stateful strategy, so it is implemented as a callable class rather
than a plain function. The backtester calls it exactly the same way:
    strategy(observation)  ->  weights

Usage:
    from tradinglab.strategies.dip_buy import DipBuyStrategy
    strategy = DipBuyStrategy()
    result = run_backtest(sim, strategy, lookback=1)
"""
from __future__ import annotations

import numpy as np


class DipBuyStrategy:
    """Stateful dip-buy / mean-reversion strategy.

    Parameters
    ----------
    dip_threshold : float
        Daily return at or below which we consider a stock a buy (default -0.05 = -5%).
    take_profit : float
        Cumulative return from entry at which we close the position (default 0.10 = +10%).
    """

    def __init__(self, dip_threshold: float = -0.05, take_profit: float = 0.10):
        self.dip_threshold = dip_threshold
        self.take_profit   = take_profit

        # Internal state — reset each time a new backtest starts.
        # entry_price[i]: the normalised price at which we entered stock i (1.0 = entry day).
        # current_price[i]: the normalised price today relative to entry.
        # weights[i]: current portfolio weight allocated to stock i.
        self._entry_price:   np.ndarray | None = None
        self._current_price: np.ndarray | None = None
        self._weights:       np.ndarray | None = None

    # ------------------------------------------------------------------
    def reset(self, n_assets: int) -> None:
        """Called automatically on the first observation of a new backtest."""
        self._entry_price   = np.zeros(n_assets)
        self._current_price = np.zeros(n_assets)
        self._weights       = np.zeros(n_assets)

    # ------------------------------------------------------------------
    def __call__(self, observation: np.ndarray) -> np.ndarray:
        """
        observation: (n_assets, lookback, N_FEATURES)
        Returns:     (n_assets,) weight vector, non-negative, sums to <= 1.
        """
        n_assets = observation.shape[0]

        # Initialise state on first call.
        if self._weights is None:
            self.reset(n_assets)

        weights       = self._weights.copy()
        entry_price   = self._entry_price.copy()
        current_price = self._current_price.copy()

        # Today's return for each asset is the last value in the return feature.
        today_return = observation[:, -1, 0]   # shape (n_assets,)

        # ── 1. Update current prices for positions we already hold ──────
        for i in range(n_assets):
            if weights[i] > 0:
                current_price[i] *= (1.0 + today_return[i])

        # ── 2. Check take-profit and exit positions that hit +10% ───────
        for i in range(n_assets):
            if weights[i] > 0:
                gain = (current_price[i] / entry_price[i]) - 1.0
                if gain >= self.take_profit:
                    weights[i]       = 0.0
                    entry_price[i]   = 0.0
                    current_price[i] = 0.0

        # ── 3. Identify new buy signals (dipped today, not already held) ─
        new_buys = [
            i for i in range(n_assets)
            if today_return[i] <= self.dip_threshold and weights[i] == 0.0
        ]

        # ── 4. Allocate available cash equally across new buys ──────────
        if new_buys:
            cash = max(0.0, 1.0 - weights.sum())   # fraction not yet invested
            alloc_each = cash / len(new_buys)       # split cash equally

            for i in new_buys:
                if alloc_each > 0:
                    weights[i]       = alloc_each
                    entry_price[i]   = 1.0           # normalised entry
                    current_price[i] = 1.0 + today_return[i]  # already moved today

        # ── 5. Persist state for next day ───────────────────────────────
        self._weights       = weights
        self._entry_price   = entry_price
        self._current_price = current_price

        return weights
