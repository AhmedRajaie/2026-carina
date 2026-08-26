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
import tradinglab.metrics as metrics

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}

# TASK_02+ : add /universe, /prices/{symbol}, /indicators, /backtest here.

# Initialize universe feed
feed = DataFeed.from_dir("data/egx", symbols=["COMI", "HRHO", "TMGH", "SWDY", "FWRY"])

@app.get("/universe")
def universe():
    return feed.symbols

@app.get("/prices/{symbol}")
def prices(symbol: str):
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
def indicators(symbol: str, window: int = 20):
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
def backtest():
    sim = PortfolioSimulator(feed, benchmark="egx30")
    result = run_backtest(sim, sma_crossover_weights, lookback=30)
    return {
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in result["dates"]],
        "portfolio": [float(v) * 1000 for v in result["portfolio"]],
        "benchmark": [float(v) * 1000 for v in result["benchmark"]],
    }
    
# TASK_05+ : add /optimize here.
@app.get("/metrics")
def metrics_endpoint():
    sim = PortfolioSimulator(feed, benchmark="egx30")
    result = run_backtest(sim, sma_crossover_weights, lookback=30)
    returns = result["portfolio_returns"]
    return {
        "total_return": round(float(metrics.total_return(returns)), 3),
        "sharpe": round(float(metrics.sharpe(returns)), 3),
        "max_drawdown": round(float(metrics.max_drawdown(returns)), 3),
    }