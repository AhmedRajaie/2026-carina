def fetch_data(tickers, start_date, end_date):
    import yfinance as yf
    data = yf.download(tickers, start=start_date, end=end_date)
    return data['Adj Close']

def resample_weekly(data):
    return data.resample('W').ffill().pct_change() * 100

def generate_signals(weekly_returns, drop_threshold, rise_threshold):
    signals = {}
    for ticker in weekly_returns.columns:
        signals[ticker] = []
        for return_value in weekly_returns[ticker]:
            if return_value <= -drop_threshold:
                signals[ticker].append('LONG')
            elif return_value >= rise_threshold:
                signals[ticker].append('SHORT')
            else:
                signals[ticker].append('HOLD')
    return signals

def simulate_positions(signals, prices, long_notionals, short_notionals):
    positions = {}
    for ticker in signals:
        positions[ticker] = []
        position = 0
        for signal, price in zip(signals[ticker], prices[ticker]):
            if signal == 'LONG':
                position += long_notionals / price
            elif signal == 'SHORT':
                position -= short_notionals / price
            positions[ticker].append(position * price)
    return positions

def calculate_performance(positions):
    performance = {}
    for ticker, position_values in positions.items():
        total_return = (position_values[-1] - position_values[0]) / position_values[0] * 100
        performance[ticker] = {
            'total_return': total_return,
            'win_rate': sum(1 for x in position_values if x > 0) / len(position_values),
            'longest_losing_streak': max(len(list(g)) for k, g in groupby(position_values) if k < 0),
            'monthly_pnl': calculate_monthly_pnl(position_values)
        }
    return performance

def calculate_monthly_pnl(position_values):
    import pandas as pd
    monthly_pnl = pd.Series(position_values).resample('M').sum()
    return monthly_pnl

def plot_equity_curve(positions):
    import matplotlib.pyplot as plt
    for ticker, position_values in positions.items():
        plt.plot(position_values, label=ticker)
    plt.title('Equity Curve')
    plt.xlabel('Time')
    plt.ylabel('Portfolio Value')
    plt.legend()
    plt.show()

def backtest(tickers, start_date, end_date, drop_threshold=5, rise_threshold=10, long_notionals=5, short_notionals=10):
    prices = fetch_data(tickers, start_date, end_date)
    weekly_returns = resample_weekly(prices)
    signals = generate_signals(weekly_returns, drop_threshold, rise_threshold)
    positions = simulate_positions(signals, prices, long_notionals, short_notionals)
    performance = calculate_performance(positions)
    plot_equity_curve(positions)
    return performance

# Note: This is a naive backtest — no slippage, transaction costs, or execution-latency modeling.