"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import math

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma, rsi as calc_rsi
from tradinglab.features import features_at
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.strategies.dip_buy import DipBuyStrategy
from tradinglab.metrics import total_return, sharpe, max_drawdown

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

feed = DataFeed.from_dir("data/egx")  # loads all 34 symbols automatically


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universe")
def universe():
    return feed.symbols


@app.get("/prices/{symbol}")
def prices(symbol: str):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    idx = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    close = feed.close[:, idx].tolist()

    return {"dates": dates, "close": close}


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    idx = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    close = feed.close[:, idx]

    sma_values = sma(close, window)
    sma_clean = [None if (v is None or math.isnan(v)) else float(v) for v in sma_values]

    return {"dates": dates, "sma": sma_clean}


@app.get("/indicators/{symbol}/rsi")
def indicator_rsi(symbol: str, window: int = 14):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    idx = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    close = feed.close[:, idx]

    rsi_values = calc_rsi(close, window)
    rsi_clean = [None if math.isnan(v) else round(float(v), 2) for v in rsi_values]

    return {"dates": dates, "rsi": rsi_clean}


@app.get("/signals")
def signals():
    """Live signals for every asset based on the last available day."""
    last_day = feed.n_days - 2          # -2 so we have a valid next-day return
    obs_day  = last_day

    # Pre-compute RSI for all assets (last value)
    rsi_today = []
    for i in range(feed.n_assets):
        r = calc_rsi(feed.close[:, i], 14)
        val = r[obs_day]
        rsi_today.append(None if math.isnan(val) else round(float(val), 1))

    # SMA signal: fast > slow = uptrend
    sma_signals = []
    for i in range(feed.n_assets):
        close = feed.close[:, i]
        fast = sma(close, 9)
        slow = sma(close, 20)
        fv, sv = fast[obs_day], slow[obs_day]
        if math.isnan(fv) or math.isnan(sv):
            sma_signals.append("—")
        else:
            sma_signals.append("BUY" if fv > sv else "CASH")

    # Dip-buy signal: today's return <= -5%
    today_ret = feed.returns[obs_day]
    dip_signals = ["BUY" if r <= -0.05 else "HOLD" for r in today_ret]

    date_str = feed.dates[obs_day].strftime("%Y-%m-%d")

    rows = []
    for i, sym in enumerate(feed.symbols):
        ret = feed.returns[obs_day, i]
        rows.append({
            "symbol":     sym,
            "date":       date_str,
            "return_pct": round(float(ret) * 100, 2),
            "rsi":        rsi_today[i],
            "sma_signal": sma_signals[i],
            "dip_signal": dip_signals[i],
        })

    return rows


COMMISSION = 0.005  # 50 bps per unit of turnover


def _run_both_benchmarks():
    """Run the SMA crossover backtest once per benchmark and return all curves."""
    sim_egx30 = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim_egx30, sma_crossover_weights, lookback=30)

    sim_eq = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    result_eq = run_backtest(sim_eq, sma_crossover_weights, lookback=30)

    return result, result_eq


@app.get("/backtest")
def backtest():
    result, result_eq = _run_both_benchmarks()
    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    portfolio       = [v * 1000 for v in result["portfolio"]]
    benchmark_egx30 = [v * 1000 for v in result["benchmark"]]
    benchmark_eq    = [v * 1000 for v in result_eq["benchmark"]]

    return {
        "dates": dates,
        "portfolio": portfolio,
        "benchmark_egx30": benchmark_egx30,
        "benchmark_equal": benchmark_eq,
    }


@app.get("/backtest/dip")
def backtest_dip():
    """Dip-buy strategy: buy on -5% drop, sell at +10% gain."""
    strategy = DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)
    sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim, strategy, lookback=1)

    sim_eq = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    strategy_eq = DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)
    result_eq = run_backtest(sim_eq, strategy_eq, lookback=1)

    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    return {
        "dates": dates,
        "portfolio":       [v * 1000 for v in result["portfolio"]],
        "benchmark_egx30": [v * 1000 for v in result["benchmark"]],
        "benchmark_equal": [v * 1000 for v in result_eq["benchmark"]],
    }


@app.get("/leaderboard")
def leaderboard():
    """Run all strategies and return a ranked comparison table."""
    strategies = [
        {"key": "sma",   "name": "SMA Crossover",       "lookback": 30,
         "factory": lambda: sma_crossover_weights},
        {"key": "dip",   "name": "Dip-Buy (−5% / +10%)", "lookback": 1,
         "factory": lambda: DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)},
    ]

    rows = []
    for s in strategies:
        sim    = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
        result = run_backtest(sim, s["factory"](), lookback=s["lookback"])

        equity  = np.array(result["portfolio"])
        rets    = np.diff(equity) / equity[:-1]
        final   = round(float(equity[-1]) * 1000, 1)

        rows.append({
            "name":         s["name"],
            "final_value":  final,
            "total_return": round(total_return(rets), 3),
            "sharpe":       round(sharpe(rets), 3),
            "max_drawdown": round(max_drawdown(rets), 3),
        })

    # Rank by Sharpe (highest = best)
    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    return rows


@app.get("/metrics")
def metrics(strategy: str = "sma"):
    """Return metrics for the selected strategy. ?strategy=sma or ?strategy=dip"""
    if strategy == "dip":
        sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
        strat = DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)
        result = run_backtest(sim, strat, lookback=1)
    else:
        sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
        result = run_backtest(sim, sma_crossover_weights, lookback=30)

    equity = np.array(result["portfolio"])
    returns = np.diff(equity) / equity[:-1]

    return {
        "total_return": round(total_return(returns), 3),
        "sharpe":       round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
        "commission":   COMMISSION,
    }