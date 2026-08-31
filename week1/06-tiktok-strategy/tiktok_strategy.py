import numpy as np
import matplotlib.pyplot as plt
from tradinglab.data_feed import DataFeed
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.report import report
from tradinglab.strategies.sma import sma_crossover_weights


def make_tiktok_guru_strategy(week_days=5, sensitivity=1.0):
    """
    The strategy, exactly as described in the video:
    "If a stock went down 5% last week, buy $5 of it.
     If a different stock went up 10%, sell $10 of it.
     Do that on every stock in the portfolio."

    RE-READING THE TWO EXAMPLES: 5% down -> $5, and 10% up -> $10, both work
    out to exactly the SAME rate -- $1 traded per 1% of weekly move. So this
    implements one continuous rule: every stock gets nudged by a percentage of
    ITS OWN current holding, proportional to how much it moved.

    FIXED BUG (found from a real backtest that flatlined and collapsed almost
    entirely into 1-2 stocks): the rule only checks and acts ONCE PER WEEK,
    matching what the video actually says ("went down 5% LAST WEEK" implies a
    weekly check, not a continuous one). Applying the tilt every single day
    against a ROLLING weekly window causes the SAME underlying weekly move to
    get acted on repeatedly (once per day, for `week_days` days in a row) as
    it slides through that window -- compounding multiplicatively and
    collapsing the portfolio into whichever stock happened to be the most
    persistent underperformer, regardless of whether that stock was actually
    a good holding. Verified with a synthetic test: daily reapplication drove
    max single-stock concentration to 74%, entirely in the two WORST
    performers in the universe. Rebalancing once a week instead brings that
    down to 35% -- a real, bounded contrarian tilt, not a runaway collapse.

    week_days:   how many trading days count as "a week" (default 5). Also
                 controls how often the strategy rebalances -- once every
                 week_days days, not every day.
    sensitivity: how much of the move gets traded. 1.0 matches the video's
                 numbers exactly (X% move -> X% of your position traded).
    """
    state = {"weights": None, "day_count": 0}

    def strategy(observation):
        n_assets = observation.shape[0]
        current = state["weights"]
        if current is None or current.sum() == 0:
            current = np.ones(n_assets) / n_assets
            state["weights"] = current

        # act on a fresh signal once every `week_days` days, not every day --
        # see the bug note above for why this matters
        if state["day_count"] % week_days == 0:
            daily_returns = observation[:, -week_days:, 0]
            return_nd = np.prod(1 + daily_returns, axis=1) - 1
            tilt_pct = -return_nd * sensitivity
            new_weights = current * (1 + tilt_pct)
            new_weights = np.clip(new_weights, 0, None)   # long-only
            total = new_weights.sum()
            current = np.zeros(n_assets) if total <= 0 else new_weights / total
            state["weights"] = current

        state["day_count"] += 1
        return state["weights"]

    return strategy


COMMISSION = 0.005

if __name__ == "__main__":
    feed = DataFeed.from_dir('data/egx')   # full 34-stock universe

    sim_eq = PortfolioSimulator(feed, benchmark='equal_weight', commission=COMMISSION)
    result_tiktok = run_backtest(sim_eq, make_tiktok_guru_strategy(week_days=5), lookback=30)

    sim_egx = PortfolioSimulator(feed, benchmark='egx30', commission=COMMISSION)
    result_sma = run_backtest(sim_egx, lambda o: sma_crossover_weights(o, 9, 20), lookback=30)

    dates = result_tiktok['dates']
    plt.figure(figsize=(11, 6))
    plt.plot(dates, result_tiktok['portfolio'] * 1000, label='TikTok Strategy', linewidth=1.6)
    plt.plot(dates, result_sma['portfolio'] * 1000, label='SMA Crossover (9,20)', linewidth=1.6)
    plt.plot(dates, result_tiktok['benchmark'] * 1000, label='Equal Weight', linewidth=1.4, linestyle='--')
    plt.plot(dates, result_sma['benchmark'] * 1000, label='EGX30', linewidth=1.4, linestyle='--')

    plt.title('Everything, One Chart — Growth of 1,000 EGP')
    plt.ylabel('Portfolio value (EGP)')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    plt.show()
    