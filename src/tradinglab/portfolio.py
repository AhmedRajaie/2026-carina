"""
portfolio.py — the single most important idea in the program, and YOURS to write.

`portfolio_return` answers: you hold these weights today, what return do you earn
tomorrow? Every backtest and the RL env run through this function. Once you
implement it and graduate it into the package, the whole engine runs on YOUR code.
"""
from __future__ import annotations
import numpy as np


def portfolio_return(weights: np.ndarray, next_returns: np.ndarray) -> float:
    """Return earned by a portfolio over one day.

    weights:      (n_assets,) fraction of money in each stock, sums to 1
    next_returns: (n_assets,) each stock's return over the coming day

    A portfolio's return is the weighted average of its holdings' returns.
    """
    # ---8<--- solution
    return float(np.dot(weights, next_returns))
    # ---8<--- end


def floor_to_shares(weights, prices, capital):
    """Realize target weights as WHOLE shares. You can't buy 3.7 shares, so:

        shares  = floor(weight * capital / price)
        realized_weight = shares * price / capital   (always <= target)

    Because floor rounds DOWN, the realized weight is always <= the target, and
    the leftover sits as uninvested cash. Expensive shares and small accounts feel
    this most. Returns the realized weights (may sum to < 1)."""
    weights = np.asarray(weights, dtype=float)
    prices = np.asarray(prices, dtype=float)
    # ---8<--- solution
    shares = np.floor(weights * capital / prices)
    value = shares * prices
    return value / capital
    # ---8<--- end
