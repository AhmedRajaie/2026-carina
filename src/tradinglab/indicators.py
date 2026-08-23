"""
indicators.py — technical indicators. YOURS to write in week 1.

Pure functions: series in, series out. Same length as input; positions without
enough history are NaN. The provided observation.py uses these same ideas to
build the agent's state in week 3.
"""
from __future__ import annotations
import numpy as np


def sma(prices: np.ndarray, window: int) -> np.ndarray:
    """Simple moving average over `window` days."""
    # ---8<--- solution
    prices = np.asarray(prices, dtype=float)
    out = np.full_like(prices, np.nan)
    for i in range(window - 1, len(prices)):
        out[i] = prices[i - window + 1 : i + 1].mean()
    return out
    # ---8<--- end


def ema(prices: np.ndarray, window: int) -> np.ndarray:
    """Exponential moving average. Weights recent prices more heavily."""
    # ---8<--- solution
    prices = np.asarray(prices, dtype=float)
    out = np.full_like(prices, np.nan)
    alpha = 2.0 / (window + 1.0)
    out[window - 1] = prices[:window].mean()
    for i in range(window, len(prices)):
        out[i] = alpha * prices[i] + (1 - alpha) * out[i - 1]
    return out
    # ---8<--- end


def rsi(prices: np.ndarray, window: int = 14) -> np.ndarray:
    """Relative Strength Index in [0, 100]."""
    # ---8<--- solution
    prices = np.asarray(prices, dtype=float)
    out = np.full_like(prices, np.nan)
    delta = np.diff(prices)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    for i in range(window, len(prices)):
        avg_gain = gains[i - window : i].mean()
        avg_loss = losses[i - window : i].mean()
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out
    # ---8<--- end


def rolling_volatility(returns: np.ndarray, window: int = 20) -> np.ndarray:
    """Rolling standard deviation of returns — a simple risk measure."""
    # ---8<--- solution
    returns = np.asarray(returns, dtype=float)
    out = np.full_like(returns, np.nan)
    for i in range(window - 1, len(returns)):
        out[i] = returns[i - window + 1 : i + 1].std()
    return out
    # ---8<--- end
