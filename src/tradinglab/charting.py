"""
charting.py — plotting helpers reused in notebooks and the dashboard.
Kept in one place so every chart looks the same everywhere.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt


def plot_price(dates, close, overlays: dict | None = None, title: str = "Price"):
    """Line chart of close price with optional overlays, e.g. {'SMA20': array}."""
    fig, ax = plt.subplots(figsize=(11, 5))
    # ---8<--- solution
    ax.plot(dates, close, label="close", linewidth=1.2)
    for name, series in (overlays or {}).items():
        ax.plot(dates, series, label=name, linewidth=1.0)
    # ---8<--- end
    ax.set_title(title); ax.legend(); ax.grid(alpha=0.3)
    return ax


def plot_candles(dates, o, h, l, c, title: str = "Candlesticks"):
    """Minimal candlestick chart (no external libraries)."""
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(c))
    up = c >= o
    ax.vlines(x, l, h, color="black", linewidth=0.6)                      # wick
    ax.bar(x[up],  (c - o)[up],  bottom=o[up],  width=0.7, color="green")  # up
    ax.bar(x[~up], (o - c)[~up], bottom=c[~up], width=0.7, color="red")    # down
    ax.set_title(title); ax.grid(alpha=0.3)
    return ax


def plot_equity(portfolio, benchmark, dates=None, title: str = "Strategy vs Benchmark"):
    """Two equity curves, both starting at 1.0. Pass `dates` (real calendar dates,
    same length as the curves) for a proper time axis — falls back to a plain
    index if you don't have them."""
    fig, ax = plt.subplots(figsize=(11, 5))
    x = dates if dates is not None else np.arange(len(portfolio))
    ax.plot(x, portfolio, label="strategy", linewidth=1.4)
    ax.plot(x, benchmark, label="benchmark", linewidth=1.4)
    ax.set_title(title); ax.set_ylabel("growth of 1.0"); ax.legend(); ax.grid(alpha=0.3)
    if dates is not None:
        fig.autofmt_xdate()   # angle the date labels so they don't overlap
    return ax


def plot_portfolio_composition(weights, dates, symbols, title="Portfolio composition over time"):
    """Heatmap: one row per stock, one column per day, color = weight held that
    day. Sparse top-k portfolios (mostly zeros) show up clearly as blank space —
    easier to read than a stacked area chart when few stocks are held at once.
    """
    fig, ax = plt.subplots(figsize=(12, 0.4 * len(symbols) + 2))
    im = ax.imshow(weights.T, aspect="auto", cmap="YlOrRd", vmin=0, vmax=weights.max() or 1,
                   extent=[0, len(dates), len(symbols), 0])
    ax.set_yticks(np.arange(len(symbols)) + 0.5)
    ax.set_yticklabels(symbols)

    # a handful of x-axis date labels, not one per day
    n_ticks = min(8, len(dates))
    tick_pos = np.linspace(0, len(dates) - 1, n_ticks).astype(int)
    ax.set_xticks(tick_pos + 0.5)
    ax.set_xticklabels([str(dates[i])[:10] for i in tick_pos], rotation=45, ha="right")

    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="weight")
    return ax


def turnover_summary(weights, trade_threshold=1e-6):
    """How much trading actually happened. Turnover on day t = how much of the
    portfolio changed since day t-1 (0 = held everything unchanged, 2.0 = sold
    everything and bought a completely different set). A "trade" is counted
    whenever one stock's weight changes by more than `trade_threshold`.

    Returns a dict: daily turnover array, total trades, and average holdings.
    """
    diffs = np.diff(weights, axis=0, prepend=weights[:1])
    daily_turnover = np.abs(diffs).sum(axis=1) / 2   # /2: a swap counts once, not twice
    n_trades = int((np.abs(diffs) > trade_threshold).sum())
    avg_holdings = float((weights > trade_threshold).sum(axis=1).mean())
    return {
        "daily_turnover": daily_turnover,
        "total_trades": n_trades,
        "avg_stocks_held": avg_holdings,
    }


def plot_portfolio_composition_discrete(weights, dates, symbols,
                                         title="Portfolio composition over time"):
    """Same idea as plot_portfolio_composition, but with DISCRETE color bands
    instead of a continuous gradient: 0 (not held) is white, then five bands
    (0-20%, 20-40%, ..., 80-100%). Reads more easily than a continuous scale,
    especially with many days squeezed into a fixed-width figure — the eye can
    tell bands apart much better than shades of the same color.
    """
    import matplotlib.colors as mcolors

    bounds = [0, 1e-6, 0.2, 0.4, 0.6, 0.8, 1.0]
    colors = ["white", "#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#d7301f"]
    cmap = mcolors.ListedColormap(colors)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(12, 0.4 * len(symbols) + 2))
    im = ax.imshow(weights.T, aspect="auto", cmap=cmap, norm=norm,
                   extent=[0, len(dates), len(symbols), 0])
    ax.set_yticks(np.arange(len(symbols)) + 0.5)
    ax.set_yticklabels(symbols)

    n_ticks = min(8, len(dates))
    tick_pos = np.linspace(0, len(dates) - 1, n_ticks).astype(int)
    ax.set_xticks(tick_pos + 0.5)
    ax.set_xticklabels([str(dates[i])[:10] for i in tick_pos], rotation=45, ha="right")

    ax.set_title(title)
    cbar = fig.colorbar(im, ax=ax, ticks=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
    cbar.set_label("weight")
    return ax


def plot_portfolio_dots(weights, dates, symbols, title="Portfolio holdings (dot grid)"):
    """Zoomed-in view: one dot per (day, stock) where something was actually
    held (zero-weight days are just blank). Dot SIZE and color both scale with
    weight. Gridlines make it easy to read "was stock X held on day Y" exactly.

    Best on a LIMITED window (a few dozen to ~100 days) — cram in a full
    multi-year backtest and the dots blur together the same way pixels would.
    """
    n_days, n_assets = weights.shape
    fig, ax = plt.subplots(figsize=(max(10, n_days * 0.15), 0.5 * n_assets + 2))

    day_idx, asset_idx, w_vals = [], [], []
    for d in range(n_days):
        for a in range(n_assets):
            if weights[d, a] > 1e-6:
                day_idx.append(d); asset_idx.append(a); w_vals.append(weights[d, a])

    sizes = 40 + 260 * np.array(w_vals)          # bigger dot = bigger position
    sc = ax.scatter(day_idx, asset_idx, s=sizes, c=w_vals, cmap="YlOrRd",
                    vmin=0, vmax=max(weights.max(), 1e-6), edgecolors="black", linewidths=0.4, zorder=3)

    # gridlines: one per day (vertical) and one per stock (horizontal)
    for d in range(n_days + 1):
        ax.axvline(d - 0.5, color="lightgray", linewidth=0.4, zorder=1)
    for a in range(n_assets):
        ax.axhline(a, color="lightgray", linewidth=0.4, zorder=1)

    ax.set_yticks(range(n_assets)); ax.set_yticklabels(symbols)
    ax.set_ylim(-0.5, n_assets - 0.5); ax.invert_yaxis()

    n_ticks = min(10, n_days)
    tick_pos = np.linspace(0, n_days - 1, n_ticks).astype(int)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([str(dates[i])[:10] for i in tick_pos], rotation=45, ha="right")
    ax.set_xlim(-0.5, n_days - 0.5)

    ax.set_title(title)
    fig.colorbar(sc, ax=ax, label="weight")
    return ax

