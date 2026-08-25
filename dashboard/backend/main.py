"""FastAPI backend for the dashboard.

Builds the DataFeed and runs the SMA + MPT backtests ONCE at startup, then
serves cached, read-only endpoints to the frontend.

Run from the repo root:
    uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tradinglab.data_feed import DataFeed
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.strategies.mpt import mpt_window_strategy
from tradinglab.metrics import (
    total_return,
    sharpe,
    max_drawdown,
    volatility,
)
from tradinglab.features import FEATURE_NAMES, features_at
from tradinglab.observation import build_observation
from tradinglab.indicators import sma

# ---------------------------------------------------------------------------
# Constants — the single source of truth for the whole dashboard.
# ---------------------------------------------------------------------------
UNIVERSE = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]
LOOKBACK = 30
SMA_FAST, SMA_SLOW = 9, 20
EGP_SCALE = 1000.0  # scale equity curves to start near 1000 EGP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"  # dashboard/data/

app = FastAPI(title="Trading dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup build — run once, cache forever.
# ---------------------------------------------------------------------------
def _build_state() -> dict:
    feed = DataFeed.from_dir("data/egx", symbols=UNIVERSE)
    sim = PortfolioSimulator(feed, benchmark="egx30")
    sma_bt = run_backtest(
        sim, lambda o: sma_crossover_weights(o, SMA_FAST, SMA_SLOW), lookback=LOOKBACK
    )
    mpt_bt = run_backtest(sim, lambda o: mpt_window_strategy(o), lookback=LOOKBACK)
    return {"feed": feed, "sim": sim, "sma_bt": sma_bt, "mpt_bt": mpt_bt}


STATE = _build_state()
FEED = STATE["feed"]
SMA_BT = STATE["sma_bt"]
MPT_BT = STATE["mpt_bt"]


def _dates_str(dates) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in dates]


def _asset_index(symbol: str) -> int | None:
    return FEED.symbols.index(symbol) if symbol in FEED.symbols else None


def _is_nan(x) -> bool:
    try:
        return x != x  # NaN check without importing math on every call
    except TypeError:
        return False


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Universe + prices + indicators
# ---------------------------------------------------------------------------
@app.get("/universe")
def universe():
    return FEED.symbols


@app.get("/prices/{symbol}")
def prices(symbol: str):
    idx = _asset_index(symbol)
    if idx is None:
        return JSONResponse(status_code=404, content={"error": f"unknown symbol '{symbol}'"})
    return {
        "symbol": symbol,
        "dates": _dates_str(FEED.dates),
        "close": [round(float(x), 4) for x in FEED.close[:, idx]],
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    idx = _asset_index(symbol)
    if idx is None:
        return JSONResponse(status_code=404, content={"error": f"unknown symbol '{symbol}'"})
    close = FEED.close[:, idx]
    sma_vals = sma(close, window)
    return {
        "symbol": symbol,
        "window": window,
        "dates": _dates_str(FEED.dates),
        "sma": [None if _is_nan(v) else round(float(v), 4) for v in sma_vals],
    }


# ---------------------------------------------------------------------------
# Backtest (SMA strategy) + metrics
# ---------------------------------------------------------------------------
@app.get("/backtest")
def backtest():
    return {
        "dates": _dates_str(SMA_BT["dates"]),
        "portfolio": [round(float(x) * EGP_SCALE, 2) for x in SMA_BT["portfolio"]],
        "benchmark": [round(float(x) * EGP_SCALE, 2) for x in SMA_BT["benchmark"]],
    }


@app.get("/metrics")
def metrics():
    r = SMA_BT["portfolio_returns"]
    return {
        "total_return": round(float(total_return(r)), 3),
        "sharpe": round(float(sharpe(r)), 3),
        "max_drawdown": round(float(max_drawdown(r)), 3),
        "volatility": round(float(volatility(r)), 3),
    }


# ---------------------------------------------------------------------------
# Features (model input) — live feature vector at the last day.
# ---------------------------------------------------------------------------
@app.get("/features/{symbol}")
def features(symbol: str):
    idx = _asset_index(symbol)
    if idx is None:
        return JSONResponse(status_code=404, content={"error": f"unknown symbol '{symbol}'"})
    last_day = FEED.n_days - 1
    row = features_at(FEED, last_day)[idx]
    return {
        "symbol": symbol,
        "date": _dates_str(FEED.dates)[last_day],
        "features": [
            {"name": name, "value": round(float(v), 4)} for name, v in zip(FEATURE_NAMES, row)
        ],
    }


# ---------------------------------------------------------------------------
# Leaderboard (SMA + MPT + benchmark) + risk
# ---------------------------------------------------------------------------
@app.get("/leaderboard")
def leaderboard():
    return {
        "dates": _dates_str(SMA_BT["dates"]),
        "sma": [round(float(x) * EGP_SCALE, 2) for x in SMA_BT["portfolio"]],
        "mpt": [round(float(x) * EGP_SCALE, 2) for x in MPT_BT["portfolio"]],
        "benchmark": [round(float(x) * EGP_SCALE, 2) for x in SMA_BT["benchmark"]],
    }


@app.get("/risk")
def risk():
    def block(returns) -> dict:
        return {
            "volatility": round(float(volatility(returns)), 3),
            "max_drawdown": round(float(max_drawdown(returns)), 3),
            "sharpe": round(float(sharpe(returns)), 3),
            "total_return": round(float(total_return(returns)), 3),
        }

    return {
        "sma": block(SMA_BT["portfolio_returns"]),
        "mpt": block(MPT_BT["portfolio_returns"]),
        "benchmark": block(SMA_BT["benchmark_returns"]),
    }


# ---------------------------------------------------------------------------
# Saved model curves (from dashboard/data/*.json)
# ---------------------------------------------------------------------------
def _read_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@app.get("/models")
def models():
    nn = _read_json("nn_equity.json")
    lstm = _read_json("lstm_equity.json")
    return {"nn": nn, "lstm": lstm}


@app.get("/rl")
def rl():
    return _read_json("rl_equity.json")


@app.get("/qagent")
def qagent():
    return _read_json("qagent.json")


# ---------------------------------------------------------------------------
# Allocations — the SMA strategy's latest weight vector.
# ---------------------------------------------------------------------------
@app.get("/allocations")
def allocations():
    last_day = FEED.n_days - 1
    obs = build_observation(FEED, last_day, LOOKBACK)
    weights = sma_crossover_weights(obs, SMA_FAST, SMA_SLOW)
    return {
        "date": _dates_str(FEED.dates)[last_day],
        "weights": [
            {"symbol": s, "weight": round(float(w), 4)}
            for s, w in zip(FEED.symbols, weights)
        ],
    }
