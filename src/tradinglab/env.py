"""
env.py — WEEK 3 face of the simulator. A Gymnasium env for Stable-Baselines3.

PROGRESSIVE DISCLOSURE: every realism knob defaults to its IDEAL setting, so

    env = PortfolioEnv(feed)

is a clean, frictionless world — no commission, daily rebalance, fractional
shares, excess-return reward. Students meet the knobs ONE AT A TIME, on the day
you teach each concept, by adding a single named argument in the notebook:

    PortfolioEnv(feed, commission=0.001)        # costs day
    PortfolioEnv(feed, rebalance_every=5)       # turnover day
    PortfolioEnv(feed, integer_shares=True)     # lot-size day
    PortfolioEnv(feed, reward="risk_adjusted")  # objective-as-a-choice day

The env source never changes. Only the arguments do. Each knob lives in its own
labeled block in step(), so you can point at exactly what one keyword turns on.

The core is still PortfolioSimulator.step_return — the SAME call the week-1
backtester makes. Strip the gym boilerplate and this IS the backtester.
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .data_feed import DataFeed
from .observation import N_FEATURES, build_observation
from .rewards import REWARDS, RewardContext
from .simulator import PortfolioSimulator


def action_to_weights(action: np.ndarray, top_k: int) -> np.ndarray:
    """Raw policy vector -> long-only weights over exactly top_k assets.

    The agent outputs a raw score per stock. We keep the top_k highest, softmax
    them into weights that sum to 1, and zero the rest. That is the "pick k stocks
    and weight them" action, learned instead of coded.
    """
    idx = np.argsort(action)[-top_k:]
    weights = np.zeros_like(action, dtype=np.float64)
    # ---8<--- solution
    top = action[idx]
    top = top - top.max()  # softmax stability
    exp = np.exp(top)
    weights[idx] = exp / exp.sum()
    # ---8<--- end
    return weights


class PortfolioEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        feed: DataFeed,
        *,
        lookback: int = 30,
        top_k: int = 2,
        reward: str = "excess",
        # --- realism knobs, all default to IDEAL ---
        commission: float = 0.0,        # 0.001 = 10 bps on turnover
        rebalance_every: int = 1,       # 1 = daily; 5 = weekly; 20 = monthly
        integer_shares: bool = False,   # True = floor weights to whole lots
        capital: float = 100_000.0,     # only used when integer_shares=True
        benchmark: str = "equal_weight",   # "equal_weight" or "egx30"
        benchmark_returns: np.ndarray | None = None,  # override either built-in
        # --- train/test slicing: restrict the env to a day range ---
        start_day: int | None = None,   # first tradable day (default: lookback)
        end_day: int | None = None,     # last day + 1 (default: n_days - 1)
        randomize_start: bool = False,  # True: each episode starts on a random day
        min_episode_len: int = 20,      # only used when randomize_start=True
    ):
        super().__init__()
        self.feed = feed
        self.sim = PortfolioSimulator(feed, benchmark=benchmark, benchmark_returns=benchmark_returns)
        self.lookback = lookback
        self.top_k = min(top_k, feed.n_assets)

        if reward not in REWARDS:
            raise ValueError(f"unknown reward '{reward}'. options: {list(REWARDS)}")
        self.reward_fn = REWARDS[reward]

        self.commission = commission
        self.rebalance_every = rebalance_every
        self.integer_shares = integer_shares
        self.capital = capital
        self.randomize_start = randomize_start
        self.min_episode_len = min_episode_len

        # A train env and a test env are just the same feed with different
        # day ranges. Train on the early years, test on the later ones — the
        # agent never sees the test period during learning.
        self.start = max(lookback, lookback if start_day is None else start_day)
        self.end = (feed.n_days - 1) if end_day is None else min(end_day, feed.n_days - 1)

        self.action_space = spaces.Box(
            low=-10.0, high=10.0, shape=(feed.n_assets,), dtype=np.float32
        )
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(feed.n_assets, lookback, N_FEATURES), dtype=np.float32,
        )
        self._reset_state()

    def _reset_state(self):
        if self.randomize_start:
            # WHY: a fixed start day means every training episode replays the
            # exact same historical sequence, over and over -- exactly the
            # setup that lets an agent memorize "day 312 of this one path"
            # instead of learning something that generalizes. Randomizing
            # where each episode begins turns one fixed sequence into
            # effectively thousands of different overlapping ones, using the
            # SAME underlying data.
            latest_possible = max(self.start, self.end - self.min_episode_len)
            self.t = int(self.np_random.integers(self.start, latest_possible + 1))
        else:
            self.t = self.start
        self.current_weights = np.zeros(self.feed.n_assets)
        self.steps_since_rebalance = self.rebalance_every  # trade on first step
        self.port_history = []

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._reset_state()
        obs = build_observation(self.feed, self.t, self.lookback).astype(np.float32)
        return obs, {}

    def _round_to_lots(self, weights):
        """INTEGER-SHARES block: you can only buy whole shares. Floor each
        holding to a whole number of shares, then re-derive the achieved weight.
        Expensive stocks drift further from target — that's the lesson."""
        prices = self.feed.close[self.t]
        shares = np.floor(weights * self.capital / prices)
        value = shares * prices
        return value / self.capital

    def step(self, action):
        target = action_to_weights(np.asarray(action, dtype=np.float64), self.top_k)

        # --- REBALANCE GATE: only act on rebalance days; otherwise hold. ---
        # (We hold the previous target between rebalances; intra-period drift is
        #  ignored to keep the mental model simple.)
        if self.steps_since_rebalance < self.rebalance_every:
            target = self.current_weights
        else:
            self.steps_since_rebalance = 0

        # --- INTEGER SHARES (default off) ---
        if self.integer_shares:
            target = self._round_to_lots(target)

        # --- COMMISSION on turnover (default 0) ---
        turnover = np.abs(target - self.current_weights).sum() / 2
        cost = self.commission * turnover

        # --- CORE: the SAME simulator call the week-1 backtester makes ---
        port_ret = self.sim.step_return(target, self.t) - cost
        bench_ret = self.sim.benchmark_step_return(self.t)
        self.port_history.append(port_ret)

        # --- REWARD (pluggable, chosen by name) ---
        reward = self.reward_fn(
            RewardContext(
                port_ret=port_ret,
                bench_ret=bench_ret,
                weights=target,
                prev_weights=self.current_weights,
                port_history=self.port_history,
            )
        )

        self.current_weights = target
        self.steps_since_rebalance += 1
        self.t += 1
        terminated = self.t >= self.end
        obs = build_observation(self.feed, self.t, self.lookback).astype(np.float32)
        info = {"portfolio_return": port_ret, "benchmark_return": bench_ret, "cost": cost}
        return obs, float(reward), terminated, False, info