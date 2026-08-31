import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy import run_backtest, walk_forward_test, run_period_robustness_check


def make_test_prices():
    idx = pd.date_range("2020-01-02", periods=60, freq="B")
    prices = pd.DataFrame(index=idx)
    base = 100.0
    series = []
    for i in range(len(idx)):
        if i < 10:
            base *= 0.995
        elif 10 <= i < 15:
            base *= 1.015
        elif i == 20:
            base *= 0.92
        elif 20 < i < 30:
            base *= 1.008
        elif i >= 30:
            base *= 0.996
        series.append(base)

    prices["AAA"] = series
    prices["BBB"] = np.linspace(120, 150, len(idx))
    return prices


def test_run_backtest_has_realistic_metrics_and_report():
    prices = make_test_prices()

    result = run_backtest(
        prices,
        drop_threshold=4,
        rise_threshold=4,
        hold_period_days=3,
        max_positions=1,
        max_capital_allocation=0.35,
        capital=10_000,
        trade_cost_per_share=0.0,
        slippage_bps=0,
        verbose=False,
    )

    assert "equity_curve" in result
    assert "metrics" in result
    assert "trades" in result
    assert set(result["metrics"]).issuperset({"total_return", "sharpe", "sortino", "max_drawdown", "calmar", "average_holding_period_days", "turnover_rate"})
    assert len(result["equity_curve"]) == len(prices)
    assert result["metrics"]["average_holding_period_days"] >= 0
    assert result["metrics"]["turnover_rate"] >= 0


def test_walk_forward_test_returns_training_and_validation_results():
    prices = make_test_prices()
    summary = walk_forward_test(
        prices,
        candidate_drop_thresholds=[3, 5],
        candidate_rise_thresholds=[5, 8],
        candidate_hold_periods=[2, 3],
        max_positions=1,
        max_capital_allocation=0.3,
        capital=10_000,
        trade_cost_per_share=0.0,
        slippage_bps=0,
    )

    assert "best_params" in summary
    assert "train_metrics" in summary
    assert "validation_metrics" in summary
    assert set(summary["best_params"]).issuperset({"drop_threshold", "rise_threshold", "hold_period_days"})
    assert summary["validation_metrics"]["total_return"] is not None


def test_period_robustness_check_runs_multiple_periods():
    prices = make_test_prices()
    midpoint = prices.index[int(len(prices.index) / 2)]
    results = run_period_robustness_check(
        prices,
        periods=[
            ("early-window", prices.index[0].strftime("%Y-%m-%d"), midpoint.strftime("%Y-%m-%d")),
            ("late-window", midpoint.strftime("%Y-%m-%d"), prices.index[-1].strftime("%Y-%m-%d")),
        ],
        drop_threshold=4,
        rise_threshold=4,
        hold_period_days=3,
        max_positions=1,
        max_capital_allocation=0.35,
        capital=10_000,
        trade_cost_per_share=0.0,
        slippage_bps=0,
    )

    assert len(results) == 2
    assert set(results["period"]) == {"early-window", "late-window"}
