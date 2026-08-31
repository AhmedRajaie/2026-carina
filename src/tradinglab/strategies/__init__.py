"""Strategy functions: observation -> weights. Each is just a different way to
produce the weight vector the simulator consumes. SMA and MPT are coded; the RL
agent (week 3) is the learned version of the same interface."""

from .sample_strategy import SampleStrategy, make_sample_strategy  # noqa: F401
