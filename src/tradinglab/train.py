"""
train.py — WEEK 3. Train an RL agent to beat the benchmark, honestly.

The whole point of RL here: the agent is just another `state -> weights`
function, but LEARNED from reward instead of hand-coded. Everything else (env,
simulator, benchmark) is what you built in week 1.

Honest evaluation is non-negotiable:
    - TRAIN on the early period. The agent learns here.
    - TEST  on a later period it never saw. This is the only number that counts.
An agent that looks great on train and loses on test has memorized noise. That
failure is a lesson, not a bug.
"""
from __future__ import annotations

import numpy as np
from stable_baselines3 import PPO

from .data_feed import DataFeed
from .env import PortfolioEnv


def split_day(feed: DataFeed, train_frac: float = 0.7) -> int:
    """Day index that splits history into train (early) and test (late)."""
    return int(feed.n_days * train_frac)


def make_envs(feed: DataFeed, split: int, **env_kwargs):
    """A train env (early days) and a test env (later days), same everything else."""
    train_env = PortfolioEnv(feed, end_day=split, **env_kwargs)
    test_env = PortfolioEnv(feed, start_day=split, **env_kwargs)
    return train_env, test_env


def evaluate(model, env) -> dict:
    """Run the trained policy through an env once; return equity curves."""
    obs, _ = env.reset()
    done = False
    port, bench = [], []
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, _, info = env.step(action)
        port.append(info["portfolio_return"])
        bench.append(info["benchmark_return"])
    port, bench = np.array(port), np.array(bench)
    return {
        "portfolio": np.cumprod(1 + port),
        "benchmark": np.cumprod(1 + bench),
        "portfolio_returns": port,
        "benchmark_returns": bench,
        "final_portfolio": float(np.cumprod(1 + port)[-1]),
        "final_benchmark": float(np.cumprod(1 + bench)[-1]),
    }


def train(
    data_dir: str = "data/egx",
    timesteps: int = 50_000,
    reward: str = "excess",
    top_k: int = 2,
    lookback: int = 30,
    seed: int = 0,
    **env_kwargs,
):
    """Train PPO on the train period, report train vs test performance."""
    feed = DataFeed.from_dir(data_dir)
    split = split_day(feed)
    train_env, test_env = make_envs(
        feed, split, reward=reward, top_k=top_k, lookback=lookback, **env_kwargs
    )

    model = PPO("MlpPolicy", train_env, verbose=0, seed=seed, n_steps=512)
    model.learn(total_timesteps=timesteps)

    train_res = evaluate(model, train_env)
    test_res = evaluate(model, test_env)
    return model, train_res, test_res
