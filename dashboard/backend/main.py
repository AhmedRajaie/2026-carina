"""FastAPI backend for the dashboard.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import json
from pathlib import Path

from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab import metrics as m

app = FastAPI(title="Trading Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Constants ─────────────────────────────────────────────────────────────────
CORE_SYMBOLS = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]
COMMISSION   = 0.005

# ── TikTok contrarian strategy ────────────────────────────────────────────────
def make_tiktok_guru_strategy(week_days: int = 5, sensitivity: float = 1.0):
    state = {"weights": None, "day_count": 0}
    def strategy(observation):
        n_assets = observation.shape[0]
        current  = state["weights"]
        if current is None or current.sum() == 0:
            current = np.ones(n_assets) / n_assets
            state["weights"] = current
        if state["day_count"] % week_days == 0:
            daily_returns = observation[:, -week_days:, 0]
            return_nd     = np.prod(1 + daily_returns, axis=1) - 1
            tilt_pct      = -return_nd * sensitivity
            new_weights   = current * (1 + tilt_pct)
            new_weights   = np.clip(new_weights, 0, None)
            total         = new_weights.sum()
            current       = np.zeros(n_assets) if total <= 0 else new_weights / total
            state["weights"] = current
        state["day_count"] += 1
        return state["weights"]
    return strategy

# ── Build universes ───────────────────────────────────────────────────────────
_universes: dict[str, dict] = {}

def _build_universe(symbols: list[str] | None, key: str):
    feed      = DataFeed.from_dir("data/egx", symbols=symbols)
    sim_gross = PortfolioSimulator(feed, benchmark="egx30")
    bt_gross  = run_backtest(sim_gross, sma_crossover_weights, lookback=30)
    sim_net   = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    bt_net    = run_backtest(sim_net, sma_crossover_weights, lookback=30)
    sim_tik   = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    bt_tiktok = run_backtest(sim_tik, make_tiktok_guru_strategy(week_days=5), lookback=30)

    # Equal-weight buy-and-hold
    start   = bt_gross["dates"][0]
    mask    = feed.dates >= start
    ew_rets = feed.returns[mask].mean(axis=1)
    bt_gross["equal_weight"]         = np.cumprod(1.0 + ew_rets)
    bt_gross["equal_weight_returns"] = ew_rets

    _universes[key] = {
        "feed":      feed,
        "bt_gross":  bt_gross,
        "bt_net":    bt_net,
        "bt_tiktok": bt_tiktok,
    }

_build_universe(CORE_SYMBOLS, "core")
_build_universe(None, "full")

# ── Load ML model curves ──────────────────────────────────────────────────────
def _load_model_curves() -> dict:
    data_dir = Path("dashboard/data")
    out = {}
    for name, fname in [("lstm", "lstm_equity.json"), ("mlp", "nn_equity.json")]:
        path = data_dir / fname
        if path.exists():
            out[name] = json.loads(path.read_text())["portfolio"]
    return out

_model_curves = _load_model_curves()
_MODEL_LEN    = len(next(iter(_model_curves.values()))) if _model_curves else 0

# ── Helpers ───────────────────────────────────────────────────────────────────
U = Query(default="core", description="'core' (5 stocks) or 'full' (all 34)")

def _get(key: str) -> dict:
    if key not in _universes:
        raise HTTPException(status_code=400, detail=f"Unknown universe '{key}'.")
    return _universes[key]

def _row(rets):
    return {
        "total_return": round(m.total_return(rets), 3),
        "sharpe":       round(m.sharpe(rets), 3),
        "max_drawdown": round(m.max_drawdown(rets), 3),
    }

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/universe")
def universe(universe: str = U):
    return {"symbols": _get(universe)["feed"].symbols}

@app.get("/prices/{symbol}")
def prices(symbol: str, universe: str = U):
    feed   = _get(universe)["feed"]
    symbol = symbol.upper()
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol '{symbol}'.")
    idx   = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    return {"dates": dates, "close": feed.close[:, idx].tolist()}

@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20, universe: str = U):
    feed   = _get(universe)["feed"]
    symbol = symbol.upper()
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol '{symbol}'.")
    idx      = feed.symbols.index(symbol)
    sv       = sma(feed.close[:, idx], window)
    dates    = [d.strftime("%Y-%m-%d") for d in feed.dates]
    sma_json = [None if (v != v) else float(v) for v in sv]
    return {"dates": dates, "sma": sma_json}

@app.get("/backtest")
def backtest(universe: str = U):
    ctx    = _get(universe)
    gross  = ctx["bt_gross"]
    net    = ctx["bt_net"]
    tiktok = ctx["bt_tiktok"]
    dates  = [d.strftime("%Y-%m-%d") for d in gross["dates"]]
    return {
        "dates":         dates,
        "portfolio":     [round(v * 1000, 4) for v in gross["portfolio"].tolist()],
        "portfolio_net": [round(v * 1000, 4) for v in net["portfolio"].tolist()],
        "tiktok":        [round(v * 1000, 4) for v in tiktok["portfolio"].tolist()],
        "benchmark":     [round(v * 1000, 4) for v in gross["benchmark"].tolist()],
        "equal_weight":  [round(v * 1000, 4) for v in gross["equal_weight"].tolist()],
    }

@app.get("/metrics")
def metrics(universe: str = U):
    ctx    = _get(universe)
    gross  = ctx["bt_gross"]
    net    = ctx["bt_net"]
    tiktok = ctx["bt_tiktok"]
    return {
        "portfolio":     _row(gross["portfolio_returns"]),
        "portfolio_net": _row(net["portfolio_returns"]),
        "tiktok":        _row(tiktok["portfolio_returns"]),
        "benchmark":     _row(gross["benchmark_returns"]),
        "equal_weight":  _row(gross["equal_weight_returns"]),
    }

@app.get("/models")
def model_curves():
    if not _model_curves:
        raise HTTPException(status_code=404, detail="No model files found.")
    gross      = _universes["core"]["bt_gross"]
    all_dates  = [d.strftime("%Y-%m-%d") for d in gross["dates"]]
    tail_dates = all_dates[-_MODEL_LEN:]
    result: dict = {"dates": tail_dates}
    for name, curve in _model_curves.items():
        result[name] = [round(v * 1000, 4) for v in curve[-_MODEL_LEN:]]

    def _model_metrics(curve):
        arr  = np.array(curve)
        rets = np.zeros(len(arr))
        rets[1:] = arr[1:] / arr[:-1] - 1.0
        return _row(rets)

    result["metrics"] = {name: _model_metrics(curve) for name, curve in _model_curves.items()}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# NEW PANELS — Correlation, Rolling Sharpe, Monthly Returns, Drawdown, Trades
# ══════════════════════════════════════════════════════════════════════════════

import pandas as pd

@app.get("/correlation")
def correlation(universe: str = U):
    """Pearson correlation matrix of daily returns across all assets."""
    feed    = _get(universe)["feed"]
    symbols = feed.symbols
    rets    = feed.returns          # (T, n_assets)
    # compute correlation matrix
    corr = np.corrcoef(rets.T)     # (n_assets, n_assets)
    return {
        "symbols": symbols,
        "matrix":  [[round(float(v), 3) for v in row] for row in corr],
    }


@app.get("/rolling-sharpe")
def rolling_sharpe(universe: str = U, window: int = 90):
    """Rolling Sharpe ratio (annualised) over `window` trading days."""
    gross   = _get(universe)["bt_gross"]
    rets    = gross["portfolio_returns"]   # (T,)
    dates   = [d.strftime("%Y-%m-%d") for d in gross["dates"]]
    values  = []
    for i in range(len(rets)):
        if i < window:
            values.append(None)
        else:
            w   = rets[i - window: i]
            sd  = float(np.std(w))
            val = float(np.mean(w) / sd * np.sqrt(252)) if sd > 1e-10 else 0.0
            values.append(round(val, 4))
    return {"dates": dates, "sharpe": values}


@app.get("/monthly-returns")
def monthly_returns(universe: str = U):
    """Portfolio monthly returns as a year × month grid."""
    gross = _get(universe)["bt_gross"]
    dates = gross["dates"]          # pd.DatetimeIndex
    rets  = gross["portfolio_returns"]

    df = pd.DataFrame({"ret": rets}, index=dates)
    df["year"]  = df.index.year
    df["month"] = df.index.month

    # compound within each month
    def compound(r): return float(np.prod(1 + r) - 1)
    pivot = df.groupby(["year", "month"])["ret"].apply(compound).unstack(fill_value=0)

    years  = [int(y) for y in pivot.index.tolist()]
    months = [int(mo) for mo in pivot.columns.tolist()]
    matrix = [[round(float(v) * 100, 2) for v in row] for row in pivot.values]
    return {"years": years, "months": months, "matrix": matrix}


@app.get("/drawdown")
def drawdown(universe: str = U):
    """Per-day drawdown from peak for both portfolio and benchmark."""
    gross  = _get(universe)["bt_gross"]
    dates  = [d.strftime("%Y-%m-%d") for d in gross["dates"]]
    port   = gross["portfolio"]
    bench  = gross["benchmark"]

    def dd_series(curve):
        peak = np.maximum.accumulate(curve)
        return [round(float((p - c) / p * 100), 3) for p, c in zip(peak, curve)]

    return {
        "dates":     dates,
        "portfolio": dd_series(port),
        "benchmark": dd_series(bench),
    }


@app.get("/trades")
def trades(universe: str = U, max_rows: int = 50):
    ctx       = _get(universe)
    gross     = ctx["bt_gross"]
    feed      = ctx["feed"]
    weights   = gross["weights"]      # (T, n_assets)
    dates     = gross["dates"]
    symbols   = feed.symbols
    close_arr = feed.close            # (all_days, n_assets)

    # weights starts at backtest start day (lookback=30)
    # dates array length == weights length
    n_bt      = len(weights)
    n_all     = feed.n_days
    offset    = n_all - n_bt          # index into close_arr for weights[0]

    events = []
    for t in range(1, n_bt):
        for a, sym in enumerate(symbols):
            prev, curr = weights[t - 1, a], weights[t, a]
            if prev == 0 and curr > 0:
                action = "BUY"
            elif prev > 0 and curr == 0:
                action = "SELL"
            else:
                continue
            price_idx = offset + t
            price = round(float(close_arr[price_idx, a]), 2) if price_idx < n_all else None
            events.append({
                "date":   dates[t].strftime("%Y-%m-%d"),
                "symbol": sym,
                "action": action,
                "price":  price,
            })

    events.sort(key=lambda x: x["date"], reverse=True)
    return {"trades": events[:max_rows], "total": len(events)}


# ══════════════════════════════════════════════════════════════════════════════
# PRO PANELS — Comparison Table, Win Rate, Volatility, Parametric Backtest
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/comparison")
def comparison(universe: str = U):
    """
    Bloomberg-style comparison table: one row per strategy, all key metrics.
    Includes annualized return alongside total return.
    """
    ctx    = _get(universe)
    gross  = ctx["bt_gross"]
    net    = ctx["bt_net"]
    tiktok = ctx["bt_tiktok"]

    def _full_row(rets, label):
        tr  = m.total_return(rets)
        n_years = len(rets) / 252
        ann = float((1 + tr) ** (1 / n_years) - 1) if n_years > 0 else 0.0
        return {
            "strategy":       label,
            "total_return":   round(tr * 100, 1),
            "ann_return":     round(ann * 100, 1),
            "sharpe":         round(m.sharpe(rets), 2),
            "max_drawdown":   round(m.max_drawdown(rets) * 100, 1),
            "volatility":     round(float(np.std(rets) * np.sqrt(252) * 100), 1),
        }

    ew_rets = gross["equal_weight_returns"]
    rows = [
        _full_row(gross["portfolio_returns"],  "SMA Crossover (gross)"),
        _full_row(net["portfolio_returns"],    "SMA Crossover (net)"),
        _full_row(tiktok["portfolio_returns"], "TikTok Contrarian"),
        _full_row(gross["benchmark_returns"],  "EGX30"),
        _full_row(ew_rets,                     "Equal Weight"),
    ]
    return {"rows": rows}


@app.get("/winrate")
def winrate(universe: str = U):
    """
    Win rate, avg win, avg loss, and profit factor for each strategy.
    A 'win' is any day with positive portfolio return.
    """
    ctx    = _get(universe)
    gross  = ctx["bt_gross"]
    net    = ctx["bt_net"]
    tiktok = ctx["bt_tiktok"]

    def _stats(rets, label):
        r     = np.asarray(rets)
        wins  = r[r > 0]
        losses= r[r < 0]
        win_rate = len(wins) / len(r) if len(r) > 0 else 0
        avg_win  = float(np.mean(wins))  if len(wins)   > 0 else 0.0
        avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        pf = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        return {
            "strategy":    label,
            "win_rate":    round(win_rate * 100, 1),
            "avg_win":     round(avg_win * 100, 3),
            "avg_loss":    round(avg_loss * 100, 3),
            "profit_factor": round(pf, 2),
            "total_trades": len(r),
        }

    return {"rows": [
        _stats(gross["portfolio_returns"],  "SMA Crossover (gross)"),
        _stats(net["portfolio_returns"],    "SMA Crossover (net)"),
        _stats(tiktok["portfolio_returns"], "TikTok Contrarian"),
        _stats(gross["benchmark_returns"],  "EGX30"),
    ]}


@app.get("/volatility")
def volatility_chart(universe: str = U, window: int = 30):
    """Rolling annualised volatility (std of returns × √252) over `window` days."""
    gross = _get(universe)["bt_gross"]
    dates = [d.strftime("%Y-%m-%d") for d in gross["dates"]]
    port  = gross["portfolio_returns"]
    bench = gross["benchmark_returns"]

    def rolling_vol(rets):
        out = []
        for i in range(len(rets)):
            if i < window:
                out.append(None)
            else:
                w = rets[i - window: i]
                out.append(round(float(np.std(w) * np.sqrt(252) * 100), 3))
        return out

    return {
        "dates":     dates,
        "portfolio": rolling_vol(port),
        "benchmark": rolling_vol(bench),
    }


@app.get("/backtest/custom")
def backtest_custom(universe: str = U, fast: int = 9, slow: int = 20):
    """
    Run SMA crossover with custom fast/slow windows.
    Used by the Strategy Parameters panel in the frontend.
    """
    if fast >= slow:
        raise HTTPException(status_code=400, detail="fast must be less than slow.")
    feed = _get(universe)["feed"]

    from functools import partial
    custom_strategy = partial(sma_crossover_weights, fast=fast, slow=slow)

    sim    = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim, custom_strategy, lookback=max(slow + 5, 30))

    dates     = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    portfolio = [round(v * 1000, 4) for v in result["portfolio"].tolist()]
    benchmark = [round(v * 1000, 4) for v in result["benchmark"].tolist()]
    rets      = result["portfolio_returns"]
    return {
        "dates":     dates,
        "portfolio": portfolio,
        "benchmark": benchmark,
        "metrics": {
            "total_return": round(m.total_return(rets) * 100, 1),
            "sharpe":       round(m.sharpe(rets), 2),
            "max_drawdown": round(m.max_drawdown(rets) * 100, 1),
        },
        "params": {"fast": fast, "slow": slow},
    }
