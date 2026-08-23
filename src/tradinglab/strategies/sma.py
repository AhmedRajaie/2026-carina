"""
sma.py — the SMA crossover strategy as a `observation -> weights` function.
YOURS to write in week 1. Also the baseline the RL agent must beat later.
"""
from __future__ import annotations
import numpy as np
from tradinglab.indicators import sma          # your graduated function from NB2


def sma_crossover_weights(observation, fast=9, slow=20):
    """Hold when the fast average price is above the slow average price.

    If NOTHING qualifies as an uptrend, hold nothing (cash) — same principle as
    the predictor from week 2: don't force a bet just because something has to
    be picked. An empty portfolio some days is honest; a forced equal-weight
    bet on stocks that aren't actually trending up is not.
    """
    n_assets = observation.shape[0]
    lookback = observation.shape[1]

    # Start by assuming we hold nothing.
    hold = np.zeros(n_assets)

    # Check each stock one at a time.
    for asset in range(n_assets):

        # Rebuild this stock's price path from its returns (see section 3 — this
        # gives the exact same crossover signal as using real prices would).
        daily_returns = observation[asset, :, 0]
        price = np.cumprod(1 + daily_returns)

        # Need enough history to compute the slow average.
        if lookback < slow:
            continue   # not enough history yet — stay out of this stock

        fast_average_today = sma(price, fast)[-1]
        slow_average_today = sma(price, slow)[-1]

        if fast_average_today > slow_average_today:
            hold[asset] = 1.0

    # Nothing qualified as an uptrend — hold NOTHING (cash), rather than forcing
    # a bet on stocks that aren't actually trending up just because one has to
    # be picked.
    if hold.sum() == 0:
        return np.zeros(n_assets)

    # Split money equally across everything held.
    weights = hold / hold.sum()
    return weights
