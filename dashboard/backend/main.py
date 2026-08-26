"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from tradinglab.backtester import run_backtest
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.metrics import max_drawdown, sharpe, total_return
from tradinglab.simulator import PortfolioSimulator
from tradinglab.strategies.sma import sma_crossover_weights


feed = DataFeed.from_dir(
    "data/egx", symbols=["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]
)
FEATURES_PATH = Path("dashboard/data/features.json")

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

    asset = feed.symbols.index(symbol)
    return {
        "dates": feed.dates.strftime("%Y-%m-%d").tolist(),
        "close": feed.close[:, asset].tolist(),
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    if window < 1:
        raise HTTPException(status_code=400, detail="Window must be positive")

    asset = feed.symbols.index(symbol)
    values = sma(feed.close[:, asset], window)
    return {
        "dates": feed.dates.strftime("%Y-%m-%d").tolist(),
        "sma": [None if value != value else float(value) for value in values],
    }


def run_sma_backtest():
    simulator = PortfolioSimulator(feed, benchmark="egx30")
    return run_backtest(
        simulator, strategy=sma_crossover_weights, lookback=30
    )


@app.get("/backtest")
def backtest():
    result = run_sma_backtest()
    return {
        "dates": result["dates"].strftime("%Y-%m-%d").tolist(),
        "portfolio": (result["portfolio"] * 1000).tolist(),
        "benchmark": (result["benchmark"] * 1000).tolist(),
    }


@app.get("/metrics")
def metrics():
    returns = run_sma_backtest()["portfolio_returns"]
    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }


@app.get("/features")
def features():
    return json.loads(FEATURES_PATH.read_text(encoding="utf-8"))


# TASK_07+ : add later dashboard endpoints here.
