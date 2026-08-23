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


def predictions_to_weights_sticky(predicted_returns, current_weights, top_k=2, switch_margin=0.003):
    """Same idea as predictions_to_weights, but with MEMORY: it knows what you
    already hold, and only switches a position out if a new candidate beats the
    worst-held stock by more than switch_margin. Small, noisy rank flips no
    longer force a trade -- only real, meaningful changes do.

    This exists because predictions_to_weights re-decides from scratch every
    single day. Two stocks with nearly identical predicted returns can swap
    ranks purely from noise, forcing a sell-and-buy that pays commission for
    zero real information. This function fixes that.

    predicted_returns: (n_assets,) today's predictions.
    current_weights:   (n_assets,) what you held YESTERDAY (from the previous
                        call -- the strategy wrapper is responsible for tracking
                        this and passing it back in).
    Returns: (n_assets,) new weights, non-negative, summing to 1 (or 0 for cash).
    """
    n = len(predicted_returns)
    currently_held = np.where(current_weights > 0)[0]

    positive = np.where(predicted_returns > 0)[0]
    if len(positive) == 0:
        return np.zeros(n)                     # bearish on everything -> cash

    # ---8<--- solution
    ranked = positive[np.argsort(predicted_returns[positive])[::-1]]   # best first
    ideal = list(ranked[:min(top_k, len(ranked))])

    keep = [i for i in currently_held if i in positive]     # still allowed to hold these
    candidates = [i for i in ideal if i not in keep]

    while len(keep) < top_k and candidates:
        new_i = candidates.pop(0)
        if len(keep) == 0:
            keep.append(new_i)
            continue
        worst_held = min(keep, key=lambda i: predicted_returns[i])
        if predicted_returns[new_i] - predicted_returns[worst_held] > switch_margin:
            keep.remove(worst_held)
            keep.append(new_i)
        else:
            break   # not worth paying commission to switch

    keep = keep[:top_k]
    w = np.zeros(n)
    if keep:
        w[keep] = 1.0 / len(keep)
    return w
    # ---8<--- end


def model_to_strategy_sticky(model, top_k=2, switch_margin=0.003):
    """Same bridge as model_to_strategy, but stateful: it remembers what it
    held yesterday and feeds that into predictions_to_weights_sticky, so the
    strategy only trades when a switch is actually worth it."""
    from ..ml import predict
    state = {"weights": None}

    def strategy(observation):
        n_assets = observation.shape[0]
        if state["weights"] is None:
            state["weights"] = np.zeros(n_assets)

        feats = observation[:, -1, :].astype("float32")
        preds = predict(model, feats)
        w = predictions_to_weights_sticky(preds, state["weights"], top_k, switch_margin)
        state["weights"] = w
        return w

    return strategy
