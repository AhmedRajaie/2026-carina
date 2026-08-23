"""
run_train.py — train the RL agent locally (laptop or GPU PC).

Cleaner than the Colab notebook when you're on your own machine. From the repo
root:

    uv run python scripts/run_train.py

Change the settings below and re-run to experiment.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tradinglab.train import train

if __name__ == "__main__":
    model, tr, te = train(
        data_dir="data/egx",
        timesteps=100_000,   # more = longer; try 200k on a GPU PC
        reward="excess",     # "return" | "excess" | "risk_adjusted"
        top_k=2,             # how many stocks the agent holds (raise with universe)
        lookback=30,
        # commission=0.001,  # uncomment to train under trading costs
    )
    print("TRAIN  agent %.3f  benchmark %.3f" % (tr["final_portfolio"], tr["final_benchmark"]))
    print("TEST   agent %.3f  benchmark %.3f" % (te["final_portfolio"], te["final_benchmark"]))
    print("beat benchmark on TEST:", te["final_portfolio"] > te["final_benchmark"])

    os.makedirs("models", exist_ok=True)
    model.save("models/ppo_agent")
    print("saved -> models/ppo_agent.zip")
