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
from tradinglab.strategies.mlp_strategy import (
    MLPSingleStockStrategy,
    MLPUniverseStrategy,
    train_single_stock_model,
    train_pooled_model,
    SPLIT_FRAC,
    TOP_N,
)
from tradinglab.strategies.lstm_strategy import (
    LSTMUniverseStrategy,
    train_pooled_lstm_model,
    SEQ_LEN,
    TOP_N as LSTM_TOP_N,
)
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
        "strategy_label": "SMA Crossover",  # was missing -- caused a blank legend entry
        # and a nameless tooltip on the frontend, since Chart.js falls back to the
        # dataset index when `label` comes through as undefined.
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


# ── MLP strategies: trained ONCE per universe at startup ─────────────────────
# Training here (not per-request) keeps the dashboard responsive -- retraining
# on every button click would make each click take several seconds. Each
# model only ever trains on days BEFORE split_day; every MLP backtest below
# starts exactly at that same cutoff, so the equity curve you see for an MLP
# strategy is genuinely out-of-sample, never data the model trained on. That
# also means an MLP curve on the chart only spans the LAST ~30% of history --
# the frontend aligns it to the correct dates rather than the start.
#
# NOTE: this trains 4 small MLPs (single-stock + universe, x2 universes) at
# import time, so the first `uvicorn --reload` after a code change will take
# a few seconds longer to come up than before.
MLP_SINGLE = {}     # universe -> (model, asset_idx, ticker, split_day)
MLP_UNIVERSE = {}   # universe -> (model, split_day)

for _universe, _feed in FEEDS.items():
    _split_day = int(_feed.n_days * SPLIT_FRAC)
    _asset_idx = 0
    _ticker = _feed.symbols[_asset_idx]

    _single_model = train_single_stock_model(_feed, _asset_idx, _split_day)
    MLP_SINGLE[_universe] = (_single_model, _asset_idx, _ticker, _split_day)

    _pooled_model = train_pooled_model(_feed, _split_day)
    MLP_UNIVERSE[_universe] = (_pooled_model, _split_day)


@app.get("/backtest/mlp_single")
def backtest_mlp_single(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Run the single-stock MLP strategy backtest and return equity curves."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    model, asset_idx, ticker, split_day = MLP_SINGLE[universe]
    strategy = MLPSingleStockStrategy(model, asset_idx, feed.n_assets)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, strategy, lookback=1, start=split_day)
    return {
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in result["dates"]],
        "portfolio": [float(v) * 1000 for v in result["portfolio"]],
        "benchmark": [float(v) * 1000 for v in result["benchmark"]],
        "strategy_label": f"MLP Single-Stock ({ticker})",
        "benchmark_label": BENCHMARK_LABELS[benchmark],
        "commission": commission,
    }


@app.get("/metrics/mlp_single")
def metrics_mlp_single(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Performance metrics for the single-stock MLP strategy."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    model, asset_idx, ticker, split_day = MLP_SINGLE[universe]
    strategy = MLPSingleStockStrategy(model, asset_idx, feed.n_assets)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, strategy, lookback=1, start=split_day)
    returns = result["portfolio_returns"]
    return {
        "strategy_label": f"MLP Single-Stock ({ticker})",
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }


@app.get("/backtest/mlp_universe")
def backtest_mlp_universe(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Run the whole-universe MLP strategy backtest and return equity curves."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    model, split_day = MLP_UNIVERSE[universe]
    top_n = min(TOP_N, feed.n_assets)
    strategy = MLPUniverseStrategy(model, feed.n_assets, top_n=top_n)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, strategy, lookback=1, start=split_day)
    return {
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in result["dates"]],
        "portfolio": [float(v) * 1000 for v in result["portfolio"]],
        "benchmark": [float(v) * 1000 for v in result["benchmark"]],
        "strategy_label": f"MLP Whole-Universe (Top {top_n})",
        "benchmark_label": BENCHMARK_LABELS[benchmark],
        "commission": commission,
    }


@app.get("/metrics/mlp_universe")
def metrics_mlp_universe(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Performance metrics for the whole-universe MLP strategy."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    model, split_day = MLP_UNIVERSE[universe]
    top_n = min(TOP_N, feed.n_assets)
    strategy = MLPUniverseStrategy(model, feed.n_assets, top_n=top_n)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, strategy, lookback=1, start=split_day)
    returns = result["portfolio_returns"]
    return {
        "strategy_label": f"MLP Whole-Universe (Top {top_n})",
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }


# ── LSTM strategy: trained ONCE per universe at startup ──────────────────────
# Same split_day / out-of-sample convention as the MLP strategies above, but
# the LSTM needs SEQ_LEN days of trailing history per prediction (not just
# the latest day), so its backtest is called with lookback=SEQ_LEN instead
# of lookback=1.
LSTM_UNIVERSE = {}   # universe -> (model, split_day)

for _universe, _feed in FEEDS.items():
    print(f"[startup] training LSTM for universe='{_universe}' ({_feed.n_assets} assets, {_feed.n_days} days)...")
    _split_day = int(_feed.n_days * SPLIT_FRAC)
    _lstm_model = train_pooled_lstm_model(_feed, _split_day)
    LSTM_UNIVERSE[_universe] = (_lstm_model, _split_day)


@app.get("/backtest/lstm")
def backtest_lstm(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Run the LSTM whole-universe strategy backtest and return equity curves."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    model, split_day = LSTM_UNIVERSE[universe]
    top_n = min(LSTM_TOP_N, feed.n_assets)
    strategy = LSTMUniverseStrategy(model, feed.n_assets, seq_len=SEQ_LEN, top_n=top_n)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, strategy, lookback=SEQ_LEN, start=split_day)
    return {
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in result["dates"]],
        "portfolio": [float(v) * 1000 for v in result["portfolio"]],
        "benchmark": [float(v) * 1000 for v in result["benchmark"]],
        "strategy_label": f"LSTM Whole-Universe (Top {top_n})",
        "benchmark_label": BENCHMARK_LABELS[benchmark],
        "commission": commission,
    }


@app.get("/metrics/lstm")
def metrics_lstm(
    universe: str = "core",
    benchmark: str = "equal_weight",
    commission: float = DEFAULT_COMMISSION,
):
    """Performance metrics for the LSTM whole-universe strategy."""
    if benchmark not in BENCHMARK_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown benchmark '{benchmark}'. use 'equal_weight' or 'egx30'.",
        )
    feed = get_feed(universe)
    model, split_day = LSTM_UNIVERSE[universe]
    top_n = min(LSTM_TOP_N, feed.n_assets)
    strategy = LSTMUniverseStrategy(model, feed.n_assets, seq_len=SEQ_LEN, top_n=top_n)
    sim = PortfolioSimulator(feed, benchmark=benchmark, commission=commission)
    result = run_backtest(sim, strategy, lookback=SEQ_LEN, start=split_day)
    returns = result["portfolio_returns"]
    return {
        "strategy_label": f"LSTM Whole-Universe (Top {top_n})",
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }