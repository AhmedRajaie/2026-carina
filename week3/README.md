# Week 3 — reinforcement learning: an agent that learns to allocate

Five parts, named by idea. RL comes early so you have days to play with it. All
tests live in `week3/tests/`.  Run them:  `uv run pytest week3/tests/`

## The arc
1. **01-rl-concept** — RL you can *read*: a 4-state Q-table learns to hold vs cash.
   You write the two lines that are the heart of RL (`epsilon_greedy`, `q_update`).
2. **02-rl-env-and-agent** — the reveal (the RL env IS your week-1 simulator), then
   a real PPO agent that allocates across the universe. You build `action_to_weights`
   and `evaluate_agent`.
3. **03-reward-shaping** — the deepest lesson: the objective shapes the agent. Write
   a custom reward, compare behaviors. `reward_drawdown_penalized`, `compare_rewards`.
4. **04-dashboard-final** — vibe-code the agent panel + leaderboard, then FREEZE.
5. **05-demo** — present. Show the dashboard, tell the story, be honest.

## Every notebook ends on a result
Q-table, deep agent, reward comparison — each is scored with `report()` (your
week-1 chart + metrics) against the benchmark. Same loop as weeks 1 and 2.

## Rough day mapping (flexible)
Day 1 → NB1 · Day 2 → NB2 · Day 3 → NB3 · Day 4 → dashboard · Day 5 → demo.
Longer training runs go to `notebooks/colab_train.ipynb` (Colab or Kaggle).

## Concepts
`learn/03-quant-and-ai/mdp-and-agents`, `.../reinforcement-learning`.
