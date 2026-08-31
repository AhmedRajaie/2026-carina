"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import importlib.util
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np

from tradinglab.indicators import sma
from tradinglab.data_feed import DataFeed
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.metrics import total_return, sharpe, max_drawdown


DEFAULT_SYMBOLS = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]
feed = DataFeed.from_dir("data/egx", symbols=DEFAULT_SYMBOLS)
FULL_MARKET_SYMBOLS = DataFeed.from_dir("data/egx").symbols

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universe")
def universe():
    return feed.symbols


@app.get("/prices/{symbol}")
def prices(symbol: str):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    symbol_index = feed.symbols.index(symbol)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "close": feed.close[:, symbol_index].tolist(),
    }


@app.get("/market")
def market(universe: str = "default"):
    chosen = resolve_feed(universe)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in chosen.dates],
        "close": chosen.close.mean(axis=1).tolist(),
    }


@app.get("/full_market_universe")
def full_market_universe():
    return list(FULL_MARKET_SYMBOLS)


@app.get("/indicators/full_market")
def market_indicators(window: int = 20, universe: str = "default"):
    chosen = resolve_feed(universe)
    values = sma(chosen.close.mean(axis=1), window)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in chosen.dates],
        "sma": [None if np.isnan(value) else float(value) for value in values],
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    symbol_index = feed.symbols.index(symbol)
    values = sma(feed.close[:, symbol_index], window)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "sma": [None if np.isnan(value) else float(value) for value in values],
    }


@app.get("/backtest")
def backtest(
    universe: str = "full_market",
    benchmark: str = "equal_weight",
    initial_capital: float = 1000.0,
    commission: float = 0.005,
):
    result = run_strategy_backtest(
        universe=universe,
        benchmark=benchmark,
        initial_capital=float(initial_capital),
        commission=float(commission),
    )
    portfolio = result["portfolio"]
    benchmark_curve = result["benchmark"]
    float_initial_capital = float(initial_capital)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in result["dates"]],
        "portfolio": portfolio.tolist(),
        "benchmark": benchmark_curve.tolist(),
        "final_portfolio_value": float(portfolio[-1]),
        "final_benchmark_value": float(benchmark_curve[-1]),
        "profit": float(portfolio[-1] - float_initial_capital),
        "return_percentage": float((portfolio[-1] / float_initial_capital - 1.0) * 100.0),
    }


def resolve_feed(universe: str = "default") -> DataFeed:
    if universe in ("default", "task_02", "task_03"):
        return feed
    if universe in ("full_market", "all", "33"):
        return DataFeed.from_dir("data/egx")
    if universe in FULL_MARKET_SYMBOLS:
        return DataFeed.from_dir("data/egx", symbols=[universe])
    return feed


def load_tiktok_strategy():
    module_path = Path(__file__).resolve().parents[2] / "week1" / "06-tiktok-strategy" / "tiktok_strategy.py"
    spec = importlib.util.spec_from_file_location("tiktok_strategy_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader is not None
    spec.loader.exec_module(module)
    return module.make_tiktok_guru_strategy(week_days=5, sensitivity=1.0)


def run_strategy_backtest(
    universe: str = "full_market",
    benchmark: str = "equal_weight",
    initial_capital: float = 1000.0,
    commission: float = 0.005,
):
    chosen_feed = resolve_feed(universe)
    simulator = PortfolioSimulator(
        chosen_feed,
        benchmark=benchmark,
        commission=float(commission),
        initial_capital=float(initial_capital),
    )
    return run_backtest(simulator, load_tiktok_strategy(), lookback=30)


@app.get("/metrics")
def metrics():
    result = run_strategy_backtest()
    returns = result["portfolio_returns"]
    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }
