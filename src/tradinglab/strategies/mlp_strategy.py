"""
mlp_strategy.py — turn the week-2 predictor into a dashboard strategy.

Two variants, both wrapping a plain MLP (see tradinglab.models.MLP):

    MLPSingleStockStrategy   -- one model, trained on ONE stock's history,
                                 goes all-in on that stock when it predicts a
                                 positive next-day return.
    MLPUniverseStrategy      -- one model, trained POOLED across every stock
                                 in the universe, goes long the TOP_N stocks
                                 with the highest predicted (and positive)
                                 next-day return, equal-weighted among them.

Both follow the same "don't force a bet" principle as sma.py: if nothing
qualifies, hold NOTHING (all-zero weights = cash), rather than being forced
into a trade the model didn't actually ask for.

Training happens ONCE, offline (see train_single_stock_model /
train_pooled_model below) — these strategies are plain, stateless callables
at inference time: observation -> weights, matching the Strategy type
expected by run_backtest.

No-lookahead convention: both training helpers only ever see days BEFORE
split_day (the same day-index masking build_pooled_dataset uses internally
for the whole-universe case). Whoever calls run_backtest with one of these
strategies should pass start=split_day, so the strategy is only ever
evaluated on days its model never trained on.
"""
from __future__ import annotations
import numpy as np
import torch

from tradinglab.features import feature_columns, build_pooled_dataset, N_FEATURES
from tradinglab.models import MLP
from tradinglab.ml import train_model, predict

SPLIT_FRAC = 0.7   # same 70/30 convention as every notebook
TOP_N = 5           # how many stocks the universe strategy goes long on
EPOCHS = 300
LR = 0.01
HIDDEN = 32


# ------------------------------------------------------------------
# Training (called once, at dashboard startup — see main.py)
# ------------------------------------------------------------------

def _build_single_asset_by_day(feed, asset, split_day):
    """Day-based train/test split for ONE stock — the calendar-cutoff
    equivalent of build_dataset + train_test_split, aligned exactly to
    split_day (same per-asset masking build_pooled_dataset uses)."""
    X_full = feature_columns(feed, asset)
    y_full = np.full(feed.n_days, np.nan)
    y_full[:-1] = feed.returns[1:, asset]
    days = np.arange(feed.n_days)
    valid = ~np.isnan(X_full).any(axis=1) & ~np.isnan(y_full)
    train_mask = valid & (days < split_day)
    test_mask = valid & (days >= split_day)
    return (X_full[train_mask].astype(np.float32), y_full[train_mask].astype(np.float32),
            X_full[test_mask].astype(np.float32), y_full[test_mask].astype(np.float32))


def train_single_stock_model(feed, asset_idx, split_day, epochs=EPOCHS, lr=LR, hidden=HIDDEN):
    """Train one MLP on one stock's history, up to (not including) split_day."""
    Xtr, ytr, Xte, yte = _build_single_asset_by_day(feed, asset_idx, split_day)
    torch.manual_seed(0)
    model = MLP(n_features=N_FEATURES, hidden=hidden)
    train_model(model, Xtr, ytr, Xte, yte, epochs=epochs, lr=lr)
    return model


def train_pooled_model(feed, split_day, epochs=EPOCHS, lr=LR, hidden=HIDDEN):
    """Train one MLP pooled across every stock's history, up to split_day."""
    Xtr, ytr, Xte, yte = build_pooled_dataset(feed, split_day)
    torch.manual_seed(0)
    model = MLP(n_features=N_FEATURES, hidden=hidden)
    train_model(model, Xtr, ytr, Xte, yte, epochs=epochs, lr=lr)
    return model


# ------------------------------------------------------------------
# Strategies (called once per backtest day by run_backtest)
# ------------------------------------------------------------------

class MLPSingleStockStrategy:
    """All-in on one stock when its model predicts a positive next-day
    return; hold nothing (cash) otherwise. Stateless — one instance can be
    reused across backtests safely."""

    def __init__(self, model, asset_idx: int, n_assets: int):
        self.model = model
        self.asset_idx = asset_idx
        self.n_assets = n_assets

    def __call__(self, observation: np.ndarray) -> np.ndarray:
        feats = observation[self.asset_idx, -1, :].astype(np.float32).reshape(1, -1)
        pred = predict(self.model, feats)[0]
        weights = np.zeros(self.n_assets)
        if pred > 0:
            weights[self.asset_idx] = 1.0
        return weights   # all-zero (cash) if pred <= 0 — see module docstring


class MLPUniverseStrategy:
    """Score every stock daily with one pooled model; go long the top_n with
    a positive predicted return, equal-weighted. Hold nothing if none
    qualify. Stateless — one instance can be reused across backtests."""

    def __init__(self, model, n_assets: int, top_n: int = TOP_N):
        self.model = model
        self.n_assets = n_assets
        self.top_n = top_n

    def __call__(self, observation: np.ndarray) -> np.ndarray:
        feats = observation[:, -1, :].astype(np.float32)   # (n_assets, N_FEATURES)
        preds = predict(self.model, feats)                  # (n_assets,)
        weights = np.zeros(self.n_assets)
        ranked = np.argsort(preds)[::-1][:self.top_n]
        positive = ranked[preds[ranked] > 0]
        if len(positive) > 0:
            weights[positive] = 1.0 / len(positive)
        return weights   # all-zero (cash) if nothing qualifies