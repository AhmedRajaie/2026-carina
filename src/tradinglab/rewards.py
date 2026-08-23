"""
rewards.py — the objective is a CHOICE. Each reward is a small function with the
same signature, registered by name. Adding a new one = write a function + add a
line to REWARDS. The env never changes.

Every reward receives the same RewardContext, and uses only the parts it needs.
That is what lets pure-return, excess, and risk-adjusted all share one interface.

Swap them and watch behavior change:
    - "return"        chases whatever went up. Ignores risk and the index.
    - "excess"        tries to beat EGX30 specifically. Hugs the benchmark.
    - "risk_adjusted" gives up some return to avoid volatile bets.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class RewardContext:
    """Everything any reward function might need for one step."""

    port_ret: float            # portfolio return this step (after costs)
    bench_ret: float           # benchmark return this step
    weights: np.ndarray        # weights held this step
    prev_weights: np.ndarray   # weights held the previous step
    port_history: list[float]  # portfolio returns so far (for volatility, etc.)


def reward_return(ctx: RewardContext) -> float:
    """Pure profit: just today's portfolio return. The naive first instinct."""
    return ctx.port_ret


def reward_excess(ctx: RewardContext) -> float:
    """Beat the index: portfolio return minus benchmark return."""
    return ctx.port_ret - ctx.bench_ret


def reward_risk_adjusted(
    ctx: RewardContext, window: int = 20, penalty: float = 0.5
) -> float:
    """Return, penalized by recent volatility. A crude Sharpe in reward form."""
    if len(ctx.port_history) < 2:
        return ctx.port_ret
    vol = float(np.std(ctx.port_history[-window:]))
    return ctx.port_ret - penalty * vol


# The registry. To add a reward: define it above, add one line here.
REWARDS = {
    "return": reward_return,
    "excess": reward_excess,
    "risk_adjusted": reward_risk_adjusted,
}


def reward_drawdown_penalized(ctx: RewardContext, penalty: float = 0.5) -> float:
    """Excess return, but PENALIZED when the portfolio is underwater. Teaches the
    agent to avoid deep losses, not just chase return. A custom reward you write in
    week 3 to see how the objective changes behavior."""
    excess = ctx.port_ret - ctx.bench_ret
    # ---8<--- solution
    curve = np.cumprod(1 + np.array(ctx.port_history + [ctx.port_ret]))
    peak = np.maximum.accumulate(curve)
    drawdown = (peak[-1] - curve[-1]) / peak[-1] if peak[-1] > 0 else 0.0
    return excess - penalty * drawdown
    # ---8<--- end


# add it to the registry so the env can select it by name
REWARDS["drawdown_penalized"] = reward_drawdown_penalized
