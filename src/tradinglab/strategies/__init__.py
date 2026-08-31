"""Strategy functions: observation -> weights. Each is just a different way to
produce the weight vector the simulator consumes. SMA and MPT are coded; the RL
agent (week 3) is the learned version of the same interface."""

from .mpt import mpt_window_strategy
from .sma import sma_crossover_weights
from .tiktok import tiktok_weights

__all__ = ["sma_crossover_weights", "mpt_window_strategy", "tiktok_weights"]
