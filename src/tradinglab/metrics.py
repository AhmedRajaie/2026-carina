"""
metrics.py — how good was a strategy? YOURS to write in week 1.
All take a 1-D array of per-period (daily) returns.
"""
from __future__ import annotations
import numpy as np

TRADING_DAYS = 252


def total_return(returns: np.ndarray) -> float:
    """Total compounded return over the whole period (0.5 = +50%)."""
    # ---8<--- solution
    return float(np.prod(1 + np.asarray(returns)) - 1)
    # ---8<--- end


def annualized_return(returns: np.ndarray) -> float:
    """Total return expressed as a per-year rate."""
    # ---8<--- solution
    r = np.asarray(returns)
    growth = np.prod(1 + r)
    years = len(r) / TRADING_DAYS
    return float(growth ** (1 / years) - 1) if years > 0 else 0.0
    # ---8<--- end


def volatility(returns: np.ndarray) -> float:
    """Annualized standard deviation of returns."""
    # ---8<--- solution
    return float(np.std(np.asarray(returns)) * np.sqrt(TRADING_DAYS))
    # ---8<--- end


def sharpe(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Return per unit of risk. Higher is better."""
    # ---8<--- solution
    r = np.asarray(returns) - risk_free / TRADING_DAYS
    sd = np.std(r)
    return float(np.mean(r) / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    # ---8<--- end


def max_drawdown(returns: np.ndarray) -> float:
    """Worst peak-to-trough drop along the equity curve (0.3 = lost 30%)."""
    # ---8<--- solution
    curve = np.cumprod(1 + np.asarray(returns))
    peak = np.maximum.accumulate(curve)
    return float(np.max((peak - curve) / peak))
    # ---8<--- end


# ---- week 2: are the model's predictions any good? ----

def directional_accuracy(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """Fraction of days the model got the DIRECTION right (up vs down).
    0.5 is a coin flip. This is often more honest than error on the exact value.
    """
    # ---8<--- solution
    p = np.sign(np.asarray(predictions))
    a = np.sign(np.asarray(actuals))
    return float(np.mean(p == a))
    # ---8<--- end


def information_coefficient(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """Correlation between predicted and actual returns, in [-1, 1]. A tiny
    positive IC (say 0.02-0.05) is a *real* edge in this game — but, as the pivot
    shows, a real edge in prediction still may not build a winning portfolio."""
    # ---8<--- solution
    p = np.asarray(predictions); a = np.asarray(actuals)
    if p.std() < 1e-12 or a.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(p, a)[0, 1])
    # ---8<--- end
