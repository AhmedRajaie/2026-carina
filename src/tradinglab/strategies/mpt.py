"""
mpt.py — Modern Portfolio Theory. WEEK 2, notebooks 4 & 5.

Markowitz (1952) gave diversification an equation. The core objects:

    E[r_p] = wᵀμ                      expected portfolio return
    σ²_p   = wᵀΣw                     portfolio variance (Σ = covariance matrix)
    Sharpe = (wᵀμ − r_f) / √(wᵀΣw)    return per unit of risk

The magic is in Σ: assets that don't move together combine into a portfolio
calmer than any of them alone. That's why diversification pays.

Two ways to allocate live here:
  - inverse_vol_weights : simple, risk-only (taught first)
  - max_sharpe_weights  : full mean-variance optimization (the real thing)

And the honest version — mpt_window_strategy — computes μ and Σ from only the
trailing window the backtester provides, so it can never see the future.
"""
from __future__ import annotations
import numpy as np

# Egyptian 91-day T-bill — a high risk-free hurdle by global standards.
RISK_FREE = 0.2725
TRADING_DAYS = 252


def inverse_vol_weights(observation: np.ndarray) -> np.ndarray:
    """Weight each asset by 1/volatility, normalized to sum to 1. Calmer assets
    get more. observation: (n_assets, lookback, n_features); feature 0 = returns."""
    n_assets = observation.shape[0]
    # ---8<--- solution
    vols = observation[:, :, 0].std(axis=1)
    vols = np.where(vols < 1e-8, 1e-8, vols)
    inv = 1.0 / vols
    return inv / inv.sum()
    # ---8<--- end


def expected_return_and_risk(weights, mu, Sigma):
    """The two core MPT equations for a portfolio.
    Returns (expected_return, volatility) = (wᵀμ, √(wᵀΣw))."""
    w = np.asarray(weights, dtype=float)
    # ---8<--- solution
    exp_return = float(w @ mu)
    variance = float(w @ Sigma @ w)
    return exp_return, float(np.sqrt(max(variance, 0.0)))
    # ---8<--- end


def max_sharpe_weights(mu, Sigma, rf: float = RISK_FREE) -> np.ndarray:
    """Long-only weights that MAXIMIZE the Sharpe ratio (the tangency portfolio).
    Solved numerically with scipy SLSQP: minimize the negative Sharpe subject to
    weights ≥ 0 and summing to 1."""
    from scipy.optimize import minimize
    mu = np.asarray(mu, dtype=float)
    Sigma = np.asarray(Sigma, dtype=float)
    n = len(mu)

    def neg_sharpe(w):
        ret, vol = expected_return_and_risk(w, mu, Sigma)
        return -(ret - rf) / vol if vol > 1e-12 else 0.0

    # ---8<--- solution
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(0.0, 1.0)] * n
    x0 = np.ones(n) / n
    res = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    w = np.clip(res.x, 0, None)
    return w / w.sum() if w.sum() > 0 else x0
    # ---8<--- end


def mpt_window_strategy(observation: np.ndarray, rf: float = RISK_FREE) -> np.ndarray:
    """WALK-FORWARD max-Sharpe. Estimates μ and Σ from ONLY the trailing window
    the backtester hands us (feature 0 = returns), then optimizes. Because it uses
    only the window, it can never see the future — look-ahead is impossible."""
    rets = observation[:, :, 0]                       # (n_assets, lookback)
    # ---8<--- solution
    mu = rets.mean(axis=1) * TRADING_DAYS             # annualized expected returns
    Sigma = np.cov(rets) * TRADING_DAYS               # annualized covariance
    Sigma = Sigma + 1e-6 * np.eye(len(mu))            # tiny ridge for stability
    return max_sharpe_weights(mu, Sigma, rf)
    # ---8<--- end
