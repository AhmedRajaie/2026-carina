"""
observation.py — the STATE, for both a week-1 strategy and the week-3 agent.

It stacks the SAME features defined in features.py over a lookback window:
    shape (n_assets, lookback, N_FEATURES)

Because it uses features.feature_columns, the last timestep of an observation is
exactly what the week-2 predictor sees:
    build_observation(feed, day, lookback)[asset, -1, :] == features_at(feed, day)[asset]

One feature definition. One state. Used end to end.

Performance: the per-asset feature tables don't change during a backtest, so we
compute them ONCE per feed and cache them. Every day is then just a fast slice.
Without this, a backtest recomputes every indicator over all history on every day.
"""
from __future__ import annotations
import numpy as np
from .data_feed import DataFeed
from .features import feature_columns, N_FEATURES  # re-exported for the env

# Cache the full (n_assets, days, N_FEATURES) feature tensor per feed, computed once.
_CACHE: dict[int, np.ndarray] = {}


def _all_features(feed: DataFeed) -> np.ndarray:
    key = id(feed)
    tensor = _CACHE.get(key)
    if tensor is None:
        tensor = np.stack([feature_columns(feed, a) for a in range(feed.n_assets)])
        _CACHE[key] = tensor
    return tensor


def build_observation(feed: DataFeed, day_index: int, lookback: int) -> np.ndarray:
    """Observation window ending at (and including) day_index. Uses only data up
    to day_index — never the future. NaNs (short history) -> 0."""
    tensor = _all_features(feed)                      # (n_assets, days, N_FEATURES)
    window = tensor[:, day_index - lookback + 1 : day_index + 1, :]
    return np.nan_to_num(window).astype(np.float64)
