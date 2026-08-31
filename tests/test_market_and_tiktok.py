from pathlib import Path

import numpy as np

from tradinglab.data_feed import DataFeed
from tradinglab.simulator import PortfolioSimulator
from tradinglab.strategies.tiktok import tiktok_weights


def test_full_market_loading_uses_all_symbols():
    feed = DataFeed.from_dir("data/egx")
    expected_symbols = sorted(p.stem for p in Path("data/egx").glob("*.csv"))
    assert feed.n_assets == len(expected_symbols)
    assert len(feed.symbols) == len(expected_symbols)
    assert feed.n_assets >= 30


def test_equal_balance_benchmark_alias_and_commission():
    feed = DataFeed.from_dir("data/egx")
    sim = PortfolioSimulator(feed, benchmark="equal_balance", commission=0.005)
    assert sim.initial_capital == 1000.0

    weights = np.full(feed.n_assets, 1.0 / feed.n_assets)
    weights_by_day = np.tile(weights, (feed.n_days, 1))
    result = sim.run(weights_by_day, start=30, end=feed.n_days - 1)
    assert result["portfolio"].shape[0] > 0
    assert np.isfinite(result["portfolio"]).all()
    assert np.isfinite(result["benchmark"]).all()
    assert result["portfolio"][0] >= 1000.0 * 0.5


def test_tiktok_weights_selects_top_momentum_assets():
    observation = np.zeros((3, 20, 1), dtype=float)
    observation[0, :, 0] = np.linspace(0.002, 0.05, 20)
    observation[1, :, 0] = np.linspace(0.001, 0.03, 20)
    observation[2, :, 0] = np.linspace(-0.01, -0.001, 20)

    weights = tiktok_weights(observation, top_k=2)

    assert np.isclose(weights.sum(), 1.0)
    assert weights[0] > 0.45
    assert weights[1] > 0.45
    assert weights[2] == 0.0
