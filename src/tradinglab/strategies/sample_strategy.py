"""
sample_strategy.py — the "TikTok" dollar-cost-averaging rule applied
simultaneously across every stock in the universe.

Rule (checked every trading day for every stock at once):
    • 5-day return ≤ -5 %  → BUY  $5  (stock fell last week, average down)
    • 5-day return ≥ +10 % → SELL $10 (stock ran last week, take profit)
    • otherwise            → hold current position unchanged

This is a mean-reversion bet: losers tend to bounce, winners tend to cool off.

Display name (charts, frontend, API): "Mean Reversion Strategy"
Internal code name                  :  sample_strategy / SampleStrategy

Why a class, not a plain function?
───────────────────────────────────
The rule is STATEFUL — how much you own in each stock today depends on all the
buy/sell decisions made on every prior day. A plain function (observation → weights)
has no memory. The class keeps a dollar-position ledger that persists across days.

Dollar amounts → weights
────────────────────────
The simulator expects weights that are non-negative and sum to 1. We maintain a
per-stock dollar ledger, then normalise:

    weight[i] = dollar_position[i] / sum(dollar_positions)

If nothing is owned yet (first days before any signal fires) we return equal-weight
so capital is deployed rather than sitting idle.

Feature index inside the observation tensor (see features.py):
    0 return  1 p/sma_fast  2 p/sma_slow  3 rsi  4 volatility
    5 macd_hist  6 return_5d  7 return_10d  8 volume_ratio
"""

from __future__ import annotations
import numpy as np

# "Last week" = 5 trading days.  return_5d is pre-computed in features.py at index 6.
_RETURN_5D_IDX = 6

# Strategy display name used in charts and the frontend.
DISPLAY_NAME = "Mean Reversion Strategy"

# Default rule parameters (match the original TikTok video exactly).
DEFAULT_BUY_THRESHOLD  = -0.05   # down  ≥ 5 %  → buy
DEFAULT_SELL_THRESHOLD =  0.10   # up    ≥ 10 % → sell
DEFAULT_BUY_DOLLARS    =  5.0    # dollars added per buy signal
DEFAULT_SELL_DOLLARS   = 10.0    # dollars removed per sell signal
_INITIAL_STAKE         =  5.0    # starting dollars when opening a new position


class SampleStrategy:
    """Stateful dollar-cost-averaging strategy — plug directly into run_backtest.

    The instance is callable (observation → weights), matching the Strategy type
    expected by run_backtest, so no glue code is needed:

        strategy = SampleStrategy(feed.n_assets)
        result   = run_backtest(sim, strategy, lookback=10)

    Parameters
    ----------
    n_assets       : number of stocks in the universe.
    buy_threshold  : weekly return at or below which we buy   (default -0.05).
    sell_threshold : weekly return at or above which we sell  (default  0.10).
    buy_dollars    : dollars added to position per buy signal (default  $5).
    sell_dollars   : dollars removed per sell signal          (default $10).
    """

    #: Display label for any chart or UI element that names this strategy.
    display_name: str = DISPLAY_NAME

    def __init__(
        self,
        n_assets: int,
        buy_threshold: float  = DEFAULT_BUY_THRESHOLD,
        sell_threshold: float = DEFAULT_SELL_THRESHOLD,
        buy_dollars: float    = DEFAULT_BUY_DOLLARS,
        sell_dollars: float   = DEFAULT_SELL_DOLLARS,
    ):
        self.n_assets       = n_assets
        self.buy_threshold  = buy_threshold
        self.sell_threshold = sell_threshold
        self.buy_dollars    = buy_dollars
        self.sell_dollars   = sell_dollars

        # Dollar-position ledger: how many notional dollars we hold in each stock.
        self._dollars = np.zeros(n_assets, dtype=float)

    def reset(self) -> None:
        """Clear all positions — call this before re-running a backtest."""
        self._dollars[:] = 0.0

    # ------------------------------------------------------------------
    # Core rule — called once per trading day by run_backtest
    # ------------------------------------------------------------------

    def __call__(self, observation: np.ndarray) -> np.ndarray:
        """Apply the buy/sell rule and return a normalised weight vector.

        Parameters
        ----------
        observation : ndarray, shape (n_assets, lookback, n_features)
            Window built by build_observation().  We only look at the last
            timestep (today) and a single feature (return_5d).

        Returns
        -------
        weights : ndarray, shape (n_assets,), non-negative, sums to 1.
        """
        # 5-day return for every stock as of today — the "last week" signal.
        ret_5d = observation[:, -1, _RETURN_5D_IDX]   # shape (n_assets,)

        buy_mask  = ret_5d <= self.buy_threshold    # fell ≥ 5 %  last week
        sell_mask = ret_5d >= self.sell_threshold   # rose ≥ 10 % last week

        # Open new positions at the initial stake; add to existing ones.
        new_position = self._dollars == 0.0
        self._dollars[buy_mask & new_position]  = _INITIAL_STAKE
        self._dollars[buy_mask & ~new_position] += self.buy_dollars

        # Reduce winners; clamp at 0 (no short-selling).
        self._dollars[sell_mask] -= self.sell_dollars
        np.clip(self._dollars, 0.0, None, out=self._dollars)

        # Normalise to weights.
        total = self._dollars.sum()
        if total <= 0.0:
            # Nothing held yet — deploy capital equally so it isn't idle.
            return np.ones(self.n_assets, dtype=float) / self.n_assets

        return self._dollars / total


def make_sample_strategy(
    n_assets: int,
    buy_threshold: float  = DEFAULT_BUY_THRESHOLD,
    sell_threshold: float = DEFAULT_SELL_THRESHOLD,
    buy_dollars: float    = DEFAULT_BUY_DOLLARS,
    sell_dollars: float   = DEFAULT_SELL_DOLLARS,
) -> SampleStrategy:
    """Return a freshly reset SampleStrategy — convenience factory for notebooks.

    Example
    -------
    >>> from tradinglab.strategies.sample_strategy import make_sample_strategy
    >>> strategy = make_sample_strategy(feed.n_assets)
    >>> result   = run_backtest(sim, strategy, lookback=10)
    """
    return SampleStrategy(n_assets, buy_threshold, sell_threshold, buy_dollars, sell_dollars)
