"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma 
import math 
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.strategies.sample_strategy import SampleStrategy, DISPLAY_NAME as SAMPLE_STRATEGY_DISPLAY_NAME
import tradinglab.metrics as metrics

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}

# TASK_02+ : add /universe, /prices/{symbol}, /indicators, /backtest here.

# Two universes, built once at startup: "core" is the original 5-symbol
# shortlist (default, unchanged behavior), "full" is every CSV in data/egx
# (33 assets). Callers pick one per request via ?universe=core|full.
CORE_SYMBOLS = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]

FEEDS = {
    "core": DataFeed.from_dir("data/egx", symbols=CORE_SYMBOLS),
    "full": DataFeed.from_dir("data/egx"),
}

DEFAULT_COMMISSION = 0.005  # 0.5% per unit of turnover

BENCHMARK_LABELS = {
    "equal_weight": "Equal-Weight Market",
    "egx30": "EGX30",
}

def get_feed(universe: str) -> DataFeed:
    if universe not in FEEDS:
        raise HTTPException(status_code=400, detail=f"unknown universe '{universe}'. use 'core' or 'full'.")
    return FEEDS[universe]

@app.get("/universe")
def universe_endpoint(universe: str = "core"):
    return get_feed(universe).symbols

@app.get("/prices/{symbol}")
def prices(symbol: str, universe: str = "core"):
    feed = get_feed(universe)
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    idx = feed.symbols.index(symbol)
    close_col = feed.close[:, idx]
    return {
        "dates": feed.dates.strftime("%Y-%m-%d").tolist(),
        "close": [float(c) for c in close_col],
    }

# TASK_03+ : add /indicators, /backtest here.
@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20, universe: str = "core"):
    feed = get_feed(universe)
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    idx = feed.symbols.index(symbol)
    close_col = feed.close[:, idx]
    sma_vals = sma(close_col, window)  # assumes sma(array, window) -> array, check signature
    return {
        "dates": feed.dates.strftime("%Y-%m-%d").tolist(),
        "sma": [None if (isinstance(v, float) and math.isnan(v)) else float(v) for v in sma_vals],
    }
    
# TASK_04+ : add /backtest here.
@app.get("/backtest")
def backtest(universe: str = "core", benchmark: str = "equal_weight", commission: float = DEFAULT_COMMISSION):
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, sma_crossover_weights, lookback=30)
    return {
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in result["dates"]],
        "portfolio": [float(v) * 1000 for v in result["portfolio"]],
        "benchmark": [float(v) * 1000 for v in result["benchmark"]],
        "benchmark_label": BENCHMARK_LABELS[benchmark],
        "commission": commission,
    }
    
# TASK_05+ : add /optimize here.
@app.get("/metrics")
def metrics_endpoint(universe: str = "core", benchmark: str = "equal_weight", commission: float = DEFAULT_COMMISSION):
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, sma_crossover_weights, lookback=30)
    returns = result["portfolio_returns"]
    return {
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }


@app.get("/metrics/sma")
def metrics_sma(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Performance metrics for the SMA Crossover strategy."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, sma_crossover_weights, lookback=30)
    returns = result["portfolio_returns"]
    return {
        "strategy_label": "SMA Crossover",
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }


# ── Sample Strategy (Mean Reversion) ─────────────────────────────────────────
# The sample_strategy is stateful: each call to run_backtest needs a fresh
# SampleStrategy instance so the dollar-position ledger starts at zero.

@app.get("/backtest/sample_strategy")
def backtest_sample_strategy(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Run the Mean Reversion Strategy backtest and return equity curves."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    strategy = SampleStrategy(feed.n_assets)          # fresh ledger every request
    result = run_backtest(sim, strategy, lookback=10)  # 10-day lookback covers return_5d
    return {
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in result["dates"]],
        "portfolio": [float(v) * 1000 for v in result["portfolio"]],
        "benchmark": [float(v) * 1000 for v in result["benchmark"]],
        "strategy_label": SAMPLE_STRATEGY_DISPLAY_NAME,
        "benchmark_label": BENCHMARK_LABELS[benchmark],
        "commission": commission,
    }


@app.get("/metrics/sample_strategy")
def metrics_sample_strategy(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Performance metrics for the Mean Reversion Strategy."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    strategy = SampleStrategy(feed.n_assets)
    result = run_backtest(sim, strategy, lookback=10)
    returns = result["portfolio_returns"]
    return {
        "strategy_label": SAMPLE_STRATEGY_DISPLAY_NAME,
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }