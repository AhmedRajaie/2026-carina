"""
report.py — one honest verdict for any backtest. GIVEN.

This reuses what YOU built in week 1: the equity chart from `charting` and the
numbers from `metrics`. Call it at the end of every experiment to see, in one
place, whether a strategy actually worked — a curve vs the benchmark and four
numbers that matter.
"""
from __future__ import annotations
import matplotlib.pyplot as plt
from . import charting, metrics


def report(result: dict, title: str = "Strategy vs benchmark", start_capital: float = 1.0):
    portfolio = result["portfolio"] * start_capital
    benchmark = result["benchmark"] * start_capital
    dates = result.get("dates")

    charting.plot_equity(portfolio, benchmark, dates=dates, title=title)
    plt.show()

    r = result["portfolio_returns"]
    final = portfolio[-1]
    bench = benchmark[-1]
    print(f"total return   : {metrics.total_return(r):+.1%}")
    print(f"sharpe         : {metrics.sharpe(r):.2f}")
    print(f"max drawdown   : {metrics.max_drawdown(r):.1%}")
    print(f"final value    : {final:.2f}   (benchmark {bench:.2f})")
    print(f"beat benchmark : {'YES' if final > bench else 'no'}")

    if start_capital != 1.0:
        diff = abs(final - bench)
        who = "beat the benchmark" if final > bench else "lost to the benchmark"
        print(f"                 you {who} by {diff:,.0f} EGP")
        