"""
qlearn.py — WEEK 3, notebook 1. Reinforcement learning you can SEE.

Deep RL is a black box. This isn't. A tiny table learns, by trial and error, when
to be IN a stock and when to sit in CASH. You can print the table and read what it
learned. Every idea in RL — state, action, reward, exploring vs exploiting, and the
update rule — lives here, small enough to hold in your head.

State  (4): trend (fast vs slow average) x momentum (yesterday up/down)
Action (2): 0 = cash, 1 = hold the stock
Reward: if holding, tomorrow's return; if cash, 0.
"""
from __future__ import annotations
import numpy as np
from .data_feed import DataFeed

N_STATES = 4
N_ACTIONS = 2
FAST, SLOW = 10, 30


def state_of(feed: DataFeed, asset: int, t: int) -> int:
    """Map the market at day t into one of 4 discrete states. GIVEN."""
    if t < SLOW:
        return 0
    close = feed.close[:, asset]
    fast_sma = close[t - FAST + 1 : t + 1].mean()
    slow_sma = close[t - SLOW + 1 : t + 1].mean()
    trend = 1 if fast_sma > slow_sma else 0
    momentum = 1 if feed.returns[t, asset] > 0 else 0
    return trend * 2 + momentum


def epsilon_greedy(Q, state, epsilon, rng):
    """Choose an action: explore a random one with probability epsilon, otherwise
    exploit the best-known action for this state. This one choice IS the explore/
    exploit trade-off at the heart of RL."""
    # ---8<--- solution
    if rng.random() < epsilon:
        return int(rng.integers(N_ACTIONS))      # explore
    return int(np.argmax(Q[state]))              # exploit
    # ---8<--- end


def q_update(Q, s, a, reward, s_next, alpha=0.1, gamma=0.95):
    """THE reinforcement-learning update. Nudge the value of the action you took
    toward the reward you got PLUS the best you can do from the next state.
    Updates Q in place.

        Q[s,a]  <-  Q[s,a] + alpha * ( reward + gamma * max(Q[s_next]) - Q[s,a] )
    """
    # ---8<--- solution
    Q[s, a] += alpha * (reward + gamma * Q[s_next].max() - Q[s, a])
    # ---8<--- end


def train_qtable(feed, asset, split, episodes=50, alpha=0.1, gamma=0.95,
                 epsilon=0.1, seed=0):
    """Learn a Q-table on the TRAIN period (days SLOW..split). GIVEN — it just
    loops your two functions over history."""
    rng = np.random.default_rng(seed)
    Q = np.zeros((N_STATES, N_ACTIONS))
    for _ in range(episodes):
        for t in range(SLOW, split - 1):
            s = state_of(feed, asset, t)
            a = epsilon_greedy(Q, s, epsilon, rng)
            reward = feed.returns[t + 1, asset] if a == 1 else 0.0
            s2 = state_of(feed, asset, t + 1)
            q_update(Q, s, a, reward, s2, alpha, gamma)
    return Q


def evaluate_qtable(Q, feed, asset, split):
    """Follow the learned (greedy) policy on the TEST period. Returns a
    report()-compatible dict so you can score it with the same tools as any
    other strategy."""
    agent, hold = [], []
    for t in range(split, feed.n_days - 1):
        a = int(np.argmax(Q[state_of(feed, asset, t)]))
        r = feed.returns[t + 1, asset]
        agent.append(r if a == 1 else 0.0)
        hold.append(r)
    agent, hold = np.array(agent), np.array(hold)
    return {
        "portfolio": np.cumprod(1 + agent),
        "benchmark": np.cumprod(1 + hold),
        "portfolio_returns": agent,
        "benchmark_returns": hold,
    }
