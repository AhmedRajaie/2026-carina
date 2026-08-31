from __future__ import annotations

import numpy as np


def tiktok_weights(observation: np.ndarray, top_k: int = 5) -> np.ndarray:
    """A simple momentum rule: buy the strongest recent trend assets,
    equally weighted among the top K.

    The strategy only buys assets with positive recent momentum. Anything with
    negative or flat momentum is sold/cash, which keeps the rule aligned with a
    buy/sell decision rather than forcing a bet on losers.
    """
    n_assets = observation.shape[0]
    if observation.size == 0 or top_k <= 0:
        return np.zeros(n_assets)

    rets = np.asarray(observation[:, :, 0], dtype=float)
    trend = rets.mean(axis=1)
    positive = np.where(trend > 0)[0]

    if len(positive) == 0:
        return np.zeros(n_assets)

    ranked = positive[np.argsort(trend[positive])[::-1]]
    chosen = ranked[: min(top_k, len(ranked))]

    weights = np.zeros(n_assets)
    weights[chosen] = 1.0 / len(chosen)
    return weights
