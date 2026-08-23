# Task 11 — Final leaderboard + allocations (Week 3, Day 4)

**Goal:** the finished product — every strategy on one board, plus what the agent
is holding.

**Prompt (frontend):**
> Combine the curves into ONE leaderboard chart: SMA, MPT, RL agent, and benchmark.
> Add a small bar panel showing the agent's current weights across stocks (you can
> save these from the notebook to dashboard/data/allocations.json and add a
> /allocations endpoint).

**Prompt (backend, allocations):**
> Add `/allocations` returning dashboard/data/allocations.json — a mapping of
> symbol -> weight for the agent's latest decision.

**Verify:** one clean board comparing everything, plus a "what the agent holds now"
panel. This is what you demo. Then FREEZE.
