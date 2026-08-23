"""
mean_reversion.py — the opposite bet from trend-following.

SMA crossover (week 1) bets that a stock going UP will keep going up. Mean
reversion bets the opposite: a stock pushed too far from "normal" tends to snap
back. Same interface as every other strategy — observation -> weights — so it
drops straight into the same backtester and leaderboard.
"""
from __future__ import annotations
import numpy as np


def rsi_mean_reversion_weights(observation: np.ndarray, oversold: float = 30.0, top_k: int = 2) -> np.ndarray:
    """Hold the most OVERSOLD stocks — the ones RSI says have been beaten down
    the hardest — betting they bounce back toward normal.

    observation: (n_assets, lookback, n_features). Feature 3 is RSI (0-100),
    already computed for you — this is the SAME rsi() you built in week 1,
    reused here as a signal instead of just a chart overlay.

    Rule: rank stocks by today's RSI, lowest first (most oversold). Hold the
    `top_k` lowest, equal-weight. If nothing is actually oversold (below the
    `oversold` threshold), hold nothing — genuine cash, all-zero weights —
    instead of forcing a bet that isn't there.
    """
    n_assets = observation.shape[0]
    rsi_today = observation[:, -1, 3]              # today's RSI, per stock

    # ---8<--- solution
    oversold_mask = rsi_today < oversold
    candidates = np.where(oversold_mask)[0]

    if len(candidates) == 0:
        return np.zeros(n_assets)          # nothing oversold — hold cash

    # among the oversold candidates, take the top_k MOST oversold (lowest RSI)
    ranked = candidates[np.argsort(rsi_today[candidates])]
    chosen = ranked[:top_k]

    weights = np.zeros(n_assets)
    weights[chosen] = 1.0 / len(chosen)
    return weights
    # ---8<--- end
