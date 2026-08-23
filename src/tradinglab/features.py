"""
features.py — THE single feature definition for the whole program.

This is the one place features are defined. Both the week-2 predictor AND the
week-3 RL agent build their state from these exact columns, in this exact order.
That is what makes "the state you build is the state the agent uses" literally
true: observation.py stacks these same features over a time window.

Feature order (index matters — it is the contract everything relies on):
    0: return        daily simple return
    1: p/sma_fast    (close / SMA_fast) - 1     price vs short average
    2: p/sma_slow    (close / SMA_slow) - 1     price vs long average
    3: rsi           RSI / 100                  momentum, scaled to ~[0,1]
    4: volatility    rolling std of returns     risk
    5: macd_hist     MACD line minus its own signal line
    6: return_5d     5-day cumulative return    medium-term momentum
    7: return_10d    10-day cumulative return   longer-term momentum
    8: volume_ratio  today's volume / 20-day average volume

Each feature is defined ONCE, as a small @feature("name") function below. The
registry is the single source of truth: FEATURE_NAMES and N_FEATURES are derived
from it, so adding, removing or commenting out one function resizes every
consumer — the datasets, the observation tensor and the RL env's observation
space. Append new features at the END: some code hardcodes positions (e.g. RSI
at index 3, in strategies/mean_reversion.py).
"""
from __future__ import annotations
from typing import Callable
import numpy as np
from .data_feed import DataFeed
from .indicators import sma, ema, rsi, rolling_volatility

SMA_FAST, SMA_SLOW = 10, 30

# name -> function(close, ret, volume) -> (days,) column. Insertion-ordered.
_REGISTRY: dict[str, Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]] = {}


def feature(name: str):
    """Register one feature column under `name`, in definition order."""
    def register(fn):
        _REGISTRY[name] = fn
        return fn
    return register


@feature("return")
def _f_return(close, ret, volume):
    return ret


@feature("p/sma_fast")
def _f_p_sma_fast(close, ret, volume):
    return close / sma(close, SMA_FAST) - 1.0


@feature("p/sma_slow")
def _f_p_sma_slow(close, ret, volume):
    return close / sma(close, SMA_SLOW) - 1.0


@feature("rsi")
def _f_rsi(close, ret, volume):
    return rsi(close, 14) / 100.0


@feature("volatility")
def _f_volatility(close, ret, volume):
    return rolling_volatility(ret, 20)


@feature("macd_hist")
def _f_macd_hist(close, ret, volume):
    macd_line = ema(close, 12) - ema(close, 26)
    # macd_line itself starts with NaN (ema26 needs 26 days of warm-up).
    # Feeding that straight into ema() would poison every value forever --
    # its recursive formula seeds from prices[:window].mean(), and one NaN in
    # the seed propagates through every subsequent step. Fix: compute the
    # signal line only on the valid tail, then pad the front back with NaN.
    first_valid = np.argmax(~np.isnan(macd_line))
    macd_signal = np.full_like(macd_line, np.nan)
    macd_signal[first_valid:] = ema(macd_line[first_valid:], 9)
    return macd_line - macd_signal


@feature("return_5d")
def _f_return_5d(close, ret, volume):
    out = np.full(len(close), np.nan)
    out[5:] = close[5:] / close[:-5] - 1.0
    return out


@feature("return_10d")
def _f_return_10d(close, ret, volume):
    out = np.full(len(close), np.nan)
    out[10:] = close[10:] / close[:-10] - 1.0
    return out


@feature("volume_ratio")
def _f_volume_ratio(close, ret, volume):
    avg20 = np.full(len(volume), np.nan)
    for i in range(19, len(volume)):
        avg20[i] = volume[i-19:i+1].mean()
    return volume / avg20


FEATURE_NAMES = list(_REGISTRY)
N_FEATURES = len(FEATURE_NAMES)


def feature_columns(feed: DataFeed, asset: int) -> np.ndarray:
    """(days, N_FEATURES) for one stock, with NaNs where history is too short.
    GIVEN — the canonical feature computation used everywhere."""
    close = feed.close[:, asset]
    ret = feed.returns[:, asset]
    volume = feed.volume[:, asset]
    return np.column_stack([fn(close, ret, volume) for fn in _REGISTRY.values()])


def features_at(feed: DataFeed, day: int) -> np.ndarray:
    """(n_assets, N_FEATURES) for a single calendar day — for trading the model.
    Same definition as build_dataset and observation.py. NaNs -> 0."""
    rows = [feature_columns(feed, a)[day] for a in range(feed.n_assets)]
    return np.nan_to_num(np.array(rows, dtype=np.float32))


def clean(X_full, y_full):
    """Drop every row where a feature OR the label is missing (NaN).

    Features are NaN early on (an SMA needs N days before it produces a value),
    and the last label is NaN (there is no 'next day' after the final row). A
    model cannot train on NaN, so we keep only fully-present rows.

    Returns (X, y) with matching rows and no NaNs.
    """
    # ---8<--- solution
    mask = ~np.isnan(X_full).any(axis=1) & ~np.isnan(y_full)
    return X_full[mask], y_full[mask]
    # ---8<--- end


def build_dataset(feed: DataFeed, asset: int):
    """Training table for one stock. X: features at day t; y: return t -> t+1."""
    X_full = feature_columns(feed, asset)
    y_full = np.full(feed.n_days, np.nan)
    y_full[:-1] = feed.returns[1:, asset]
    X, y = clean(X_full, y_full)          # <-- your graduated function runs here
    return X.astype(np.float32), y.astype(np.float32)


def build_pooled_dataset(feed: DataFeed, split_day: int):
    """Build a TRAIN/TEST dataset pooled across every stock, split by CALENDAR
    DAY — not by row count after pooling.

    Why this matters: build_dataset() drops NaN rows per stock, so after
    pooling several stocks with vstack, row *position* no longer lines up with
    calendar day. Cutting by row-count (train_test_split) after pooling can
    put one stock's ENTIRE history — including days the backtest later calls
    "the test period" — into training. This function avoids that by masking
    each stock's rows against `split_day` before pooling, so no stock ever
    contributes a late-period row to the training set.

    Returns X_train, y_train, X_test, y_test — each pooled across all stocks,
    with every row's calendar day correctly respecting the split.
    """
    Xtr_list, ytr_list, Xte_list, yte_list = [], [], [], []
    for a in range(feed.n_assets):
        X_full = feature_columns(feed, a)
        y_full = np.full(feed.n_days, np.nan)
        y_full[:-1] = feed.returns[1:, a]

        days = np.arange(feed.n_days)
        valid = ~np.isnan(X_full).any(axis=1) & ~np.isnan(y_full)
        train_mask = valid & (days < split_day)
        test_mask = valid & (days >= split_day)

        Xtr_list.append(X_full[train_mask]); ytr_list.append(y_full[train_mask])
        Xte_list.append(X_full[test_mask]); yte_list.append(y_full[test_mask])

    X_train = np.vstack(Xtr_list).astype(np.float32)
    y_train = np.concatenate(ytr_list).astype(np.float32)
    X_test = np.vstack(Xte_list).astype(np.float32)
    y_test = np.concatenate(yte_list).astype(np.float32)
    return X_train, y_train, X_test, y_test


def train_test_split(X, y, train_frac=0.7):
    """Split by TIME. Test = the LATER period the model never trained on."""
    cut = int(len(X) * train_frac)
    return X[:cut], y[:cut], X[cut:], y[cut:]


def train_test_validation_split(X, y, train_frac=0.5, test_frac=0.25):
    """Split by TIME into three groups: train, test, validation.

    Same idea as train_test_split, one step further: TEST is for choosing between
    candidates (different seeds, different hyperparameters), VALIDATION is opened
    only ONCE, after you've already committed to your final choice, to report the
    honest result. If you pick your candidate by peeking at validation, it isn't
    validation anymore — it's just a second test set you've contaminated.
    """
    n = len(X)
    # ---8<--- solution
    train_end = int(n * train_frac)
    test_end = train_end + int(n * test_frac)
    return (X[:train_end], y[:train_end],
            X[train_end:test_end], y[train_end:test_end],
            X[test_end:], y[test_end:])
    # ---8<--- end


def to_sequences(X, y, seq_len: int = 5):
    """Reshape a (samples, features) table into overlapping sequences for an LSTM:
    (samples-seq_len, seq_len, features). Each label is the return AFTER the window."""
    # ---8<--- solution
    xs, ys = [], []
    for i in range(seq_len, len(X)):
        xs.append(X[i - seq_len : i])
        ys.append(y[i])
    return np.array(xs, dtype="float32"), np.array(ys, dtype="float32")
    # ---8<--- end


def build_pooled_sequences(feed: DataFeed, split_day: int, seq_len: int = 5):
    """Like build_pooled_dataset, but for sequence models (LSTM): sequences
    are built PER STOCK first, then pooled — never the other way around.

    Why this matters: build_pooled_dataset's train/test rows, once pooled
    across stocks with vstack, are stock 0's rows then stock 1's rows then
    stock 2's, etc, one after another. If you slide a sequence window across
    that pooled array directly, windows near a stock boundary splice together
    days from two different companies as if they were one continuous series —
    and, separately, a window near the train/test boundary within one stock
    could quietly straddle into the other split. Sequencing each stock's
    train portion and test portion SEPARATELY, before pooling, avoids both.

    A side effect worth knowing: each stock loses its first `seq_len` rows
    within test (and within train) as unavoidable warm-up, since a sequence
    needs `seq_len` prior rows that don't reach across the split.
    """
    Xtr_list, ytr_list, Xte_list, yte_list = [], [], [], []
    for a in range(feed.n_assets):
        X_full = feature_columns(feed, a)
        y_full = np.full(feed.n_days, np.nan)
        y_full[:-1] = feed.returns[1:, a]

        days = np.arange(feed.n_days)
        valid = ~np.isnan(X_full).any(axis=1) & ~np.isnan(y_full)
        train_mask = valid & (days < split_day)
        test_mask = valid & (days >= split_day)

        X_tr_stock, y_tr_stock = X_full[train_mask], y_full[train_mask]
        X_te_stock, y_te_stock = X_full[test_mask], y_full[test_mask]

        if len(X_tr_stock) > seq_len:
            xs, ys = to_sequences(X_tr_stock, y_tr_stock, seq_len)
            Xtr_list.append(xs); ytr_list.append(ys)
        if len(X_te_stock) > seq_len:
            xs, ys = to_sequences(X_te_stock, y_te_stock, seq_len)
            Xte_list.append(xs); yte_list.append(ys)

    X_train = np.vstack(Xtr_list).astype(np.float32)
    y_train = np.concatenate(ytr_list).astype(np.float32)
    X_test = np.vstack(Xte_list).astype(np.float32)
    y_test = np.concatenate(yte_list).astype(np.float32)
    return X_train, y_train, X_test, y_test


