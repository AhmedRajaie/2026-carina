"""
predictor.py — WEEK 2. Turn a trained model into a strategy the backtester runs.

Two functions you build here:
  1. predictions_to_weights — rank stocks by predicted return, hold the top few.
  2. model_to_strategy      — wrap a trained model so the backtester can trade it.

Together they are the bridge from "a model that predicts numbers" to "a strategy
that trades and can be scored on the real env."
"""
from __future__ import annotations
import numpy as np


def predictions_to_weights(predicted_returns: np.ndarray, top_k: int = 2) -> np.ndarray:
    """Rank stocks by predicted return, hold the top_k the model expects to RISE,
    equal-weight. If the model is bearish on everything (no positive prediction),
    hold nothing — an all-zero vector, which the simulator treats as a cash day
    (zero return) rather than forcing a bet on stocks you expect to lose money on.

    predicted_returns: (n_assets,) the model's guess for each stock.
    returns: (n_assets,) weights, non-negative, summing to 1 (or to 0 if nothing
    is worth holding), with at most top_k non-zero entries.
    """
    n = len(predicted_returns)
    w = np.zeros(n)
    # ---8<--- solution
    positive = np.where(predicted_returns > 0)[0]        # only stocks expected to rise
    if len(positive) == 0:
        return w                                          # bearish on all -> hold cash
    k = min(top_k, len(positive))
    best = positive[np.argsort(predicted_returns[positive])[-k:]]
    w[best] = 1.0 / k
    return w
    # ---8<--- end


def model_to_strategy(model, top_k: int = 2):
    """Wrap a trained model as a backtester strategy: observation -> weights.

    The backtester calls strategy(observation) each day, where observation is
    (n_assets, lookback, n_features). The LAST timestep of that window is exactly
    the feature row the model was trained on, so we predict from it and turn the
    predictions into weights.
    """
    from ..ml import predict

    def strategy(observation: np.ndarray) -> np.ndarray:
        # ---8<--- solution
        feats = observation[:, -1, :].astype("float32")   # latest features per asset
        preds = predict(model, feats)                      # one prediction per stock
        return predictions_to_weights(preds, top_k)
        # ---8<--- end

    return strategy
