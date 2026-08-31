# backtest.py

from src.strategy import (
    fetch_data,
    run_backtest,
    walk_forward_test,
    parameter_sensitivity_analysis,
    run_period_robustness_check,
)

# Configurable parameters
# These tickers are available in the repo's bundled sample data under data/egx/.
TICKER_UNIVERSE = ["COMI", "HRHO", "TMGH", "SWDY"]
DROP_THRESHOLD = 5.0
RISE_THRESHOLD = 10.0
HOLD_PERIOD_DAYS = 5
MAX_POSITIONS = 3
MAX_CAPITAL_ALLOCATION = 0.20
CAPITAL = 100000.0
TRADE_COST_PER_SHARE = 0.005
SLIPPAGE_BPS = 10.0


def main():
    price_data = fetch_data(TICKER_UNIVERSE, "2015-01-01", "2024-12-31")
    results = run_backtest(
        price_data,
        drop_threshold=DROP_THRESHOLD,
        rise_threshold=RISE_THRESHOLD,
        hold_period_days=HOLD_PERIOD_DAYS,
        max_positions=MAX_POSITIONS,
        max_capital_allocation=MAX_CAPITAL_ALLOCATION,
        capital=CAPITAL,
        trade_cost_per_share=TRADE_COST_PER_SHARE,
        slippage_bps=SLIPPAGE_BPS,
    )

    print("\n=== Main Backtest ===")
    print(f"Total Return      : {results['metrics']['total_return']:.2%}")
    print(f"Sharpe Ratio      : {results['metrics']['sharpe']:.3f}")
    print(f"Sortino Ratio     : {results['metrics']['sortino']:.3f}")
    print(f"Max Drawdown      : {results['metrics']['max_drawdown']:.2%}")
    print(f"Calmar Ratio      : {results['metrics']['calmar']:.3f}")
    print(f"Avg Holding       : {results['metrics']['average_holding_period_days']:.1f} days")
    print(f"Turnover Rate     : {results['metrics']['turnover_rate']:.3f}")

    print("\n=== Period Robustness ===")
    print(run_period_robustness_check(
        price_data,
        periods=[
            ("2015-2019", "2015-01-01", "2019-12-31"),
            ("2020-2024", "2020-01-01", "2024-12-31"),
        ],
        drop_threshold=DROP_THRESHOLD,
        rise_threshold=RISE_THRESHOLD,
        hold_period_days=HOLD_PERIOD_DAYS,
        max_positions=MAX_POSITIONS,
        max_capital_allocation=MAX_CAPITAL_ALLOCATION,
        capital=CAPITAL,
        trade_cost_per_share=TRADE_COST_PER_SHARE,
        slippage_bps=SLIPPAGE_BPS,
    ))

    print("\n=== Walk-Forward ===")
    print(walk_forward_test(
        price_data,
        candidate_drop_thresholds=[3.0, 5.0, 7.0],
        candidate_rise_thresholds=[6.0, 10.0, 12.0],
        candidate_hold_periods=[3, 5, 7],
        max_positions=MAX_POSITIONS,
        max_capital_allocation=MAX_CAPITAL_ALLOCATION,
        capital=CAPITAL,
        trade_cost_per_share=TRADE_COST_PER_SHARE,
        slippage_bps=SLIPPAGE_BPS,
    ))

    print("\n=== Sensitivity ===")
    print(parameter_sensitivity_analysis(
        price_data,
        candidate_drop_thresholds=[3.0, 5.0, 7.0],
        candidate_rise_thresholds=[6.0, 10.0, 12.0],
        candidate_hold_periods=[3, 5, 7],
        max_positions=MAX_POSITIONS,
        max_capital_allocation=MAX_CAPITAL_ALLOCATION,
        capital=CAPITAL,
        trade_cost_per_share=TRADE_COST_PER_SHARE,
        slippage_bps=SLIPPAGE_BPS,
    ).head(10))


if __name__ == "__main__":
    main()